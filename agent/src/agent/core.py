import time
from typing import List, Dict, Any, Tuple
from src.config import Config
from src.providers.gemini import GeminiProvider
from src.providers.groq import GroqProvider
from src.tools.router import TOOLS_DECLARATIONS, execute_tool
from src.agent.memory import memory
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.validator import validate_agent_response

# Verify and create database tables at startup
try:
    from src.db_connection import execute_query
    execute_query("""
        CREATE TABLE IF NOT EXISTS customer_interests (
            mobile VARCHAR(20) PRIMARY KEY,
            interest VARCHAR(50),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    execute_query("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            mobile VARCHAR(20) NOT NULL,
            session_id VARCHAR(50) NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_mobile_timestamp (mobile, timestamp)
        ) ENGINE=InnoDB
    """)
    print("[Database] Verified customer_interests and chat_logs tables exist.")
except Exception as e:
    print(f"[Database Error] Failed to verify database tables: {e}")

# Helper to instantiate providers dynamically based on config
def get_provider_instance(provider_name: str, model_name: str):
    if str(provider_name).lower() == "groq":
        return GroqProvider(Config.GROQ_API_KEY, model_name)
    else:
        return GeminiProvider(Config.GEMINI_API_KEY, model_name)

# Instantiate providers dynamically
primary_provider = get_provider_instance(Config.PRIMARY_PROVIDER, Config.PRIMARY_MODEL)
secondary_provider = get_provider_instance(Config.SECONDARY_PROVIDER, Config.SECONDARY_MODEL)

def call_llm_with_routing(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    system_instruction: str,
    timeline: List[Dict[str, Any]]
) -> Tuple[Any, Any, Dict[str, Any], str, str, float, bool, Any]:
    """
    Executes model routing: Primary Gemini -> Secondary Gemini -> Groq.
    Updates the timeline list with precise timestamps and latency.
    """
    # Dynamically build providers queue: Gemini Primary -> Gemini Secondary -> 10 Groq Fallbacks
    providers_queue = [
        ("primary_gemini", primary_provider, 10.0),
        ("secondary_gemini", secondary_provider, 10.0)
    ]
    
    # Groq Active Models in priority order
    groq_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "llama3-70b-8192",
        "llama-3.1-70b-versatile"
    ]
    
    for idx, model_id in enumerate(groq_models):
        if Config.GROQ_API_KEY:
            providers_queue.append((
                f"groq_fallback_{idx+1}_{model_id}", 
                GroqProvider(Config.GROQ_API_KEY, model_id), 
                8.0
            ))
            
    last_error = None
    
    for idx, (p_type, provider, timeout) in enumerate(providers_queue):
        start_time = time.time()
        timestamp_str = time.strftime("%H:%M:%S", time.localtime(start_time))
        
        timeline.append({
            "timestamp": timestamp_str,
            "event": f"Attempting call to {p_type} model: {provider.model_name}"
        })
        
        try:
            content, tool_calls, raw_response = provider.generate_response(
                messages=messages,
                tools=tools,
                system_instruction=system_instruction,
                timeout=timeout
            )
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # in ms
            timeline.append({
                "timestamp": time.strftime("%H:%M:%S", time.localtime(end_time)),
                "event": f"Success: {provider.model_name} responded in {latency:.1f}ms"
            })
            
            fallback_used = (idx > 0)
            fallback_reason = None
            if fallback_used:
                fallback_reason = f"Previous models failed. Last error: {str(last_error)}"
                
            return (
                content,
                tool_calls,
                raw_response,
                provider.__class__.__name__,
                provider.model_name,
                latency,
                fallback_used,
                fallback_reason
            )
            
        except Exception as e:
            last_error = e
            end_time = time.time()
            err_msg = f"Failed {provider.model_name} (Timeout/Error): {str(e)}"
            timeline.append({
                "timestamp": time.strftime("%H:%M:%S", time.localtime(end_time)),
                "event": err_msg
            })
            print(f"\n[Fallback Alert] {provider.model_name} failed: {str(e)}. Switching to next backup model...\n")
            # Continue to next model in queue
            
    # If all providers fail, we raise the final exception
    raise RuntimeError(
        f"All model providers in the fallback queue failed! \n"
        f"Primary Gemini: {Config.PRIMARY_MODEL}\n"
        f"Secondary Gemini: {Config.SECONDARY_MODEL}\n"
        f"Tried 10 Groq Fallbacks. Last technical error: {str(last_error)}"
    )

def save_conversation_to_file(session_id: str):
    """
    Saves and appends the complete chat history of a session into a file named
    after the customer's mobile number inside the 'conversations/' directory.
    Stores entries chronologically with timestamps. If file size exceeds 1GB, 
    truncates the oldest entries from the top of the file to preserve space.
    """
    import os
    import json
    
    context = memory.get_context(session_id)
    mobile = context.get("customer_mobile")
    
    # Try to scan history if mobile is not yet in context
    if not mobile:
        history = memory.get_history(session_id)
        for msg in history:
            if msg.get("role") == "tool" and msg.get("tool_name") == "get_customer":
                res = msg.get("tool_response")
                if isinstance(res, dict) and res.get("mobile"):
                    mobile = res.get("mobile")
                    memory.update_context(session_id, "customer_mobile", mobile)
                    break
                    
    # If still not found, fallback to session_id to ensure the log is created immediately
    is_temp_session_file = False
    if not mobile:
        mobile = f"session_{session_id}"
        is_temp_session_file = True
        
    if mobile:
        clean_mobile = "".join(c for c in str(mobile) if c.isalnum() or c in "-_")
        if clean_mobile:
            dir_path = os.path.join(os.getcwd(), "conversations")
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, f"{clean_mobile}.json")
            
            # Clean up temp file if a real mobile is now resolved
            if not is_temp_session_file:
                temp_file = os.path.join(dir_path, f"session_{session_id}.json")
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception as e:
                        print(f"Error removing temp session file: {e}")
            
            # Read existing history if file exists
            existing_data = {
                "mobile": clean_mobile,
                "conversations": []
            }
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict) and "conversations" in loaded:
                            existing_data = loaded
                except Exception as e:
                    print(f"Error reading existing file: {e}")
            
            # Append new turn
            history = memory.get_history(session_id)
            current_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Filter new entries not already in stored conversations for this session
            stored_session_messages = [
                msg for conv in existing_data["conversations"] 
                if conv.get("session_id") == session_id 
                for msg in conv.get("history", [])
            ]
            
            # Check for new messages
            new_messages = []
            for msg in history:
                if msg not in stored_session_messages:
                    new_messages.append(msg)
            
            if new_messages:
                existing_data["conversations"].append({
                    "session_id": session_id,
                    "timestamp": current_timestamp,
                    "history": new_messages
                })
                
                # Save new messages to DB chat_logs table for high-performance indexing
                if not is_temp_session_file:
                    try:
                        from src.db_connection import execute_query
                        for msg in new_messages:
                            role = msg.get("role")
                            content = msg.get("content") or ""
                            if role in ["user", "model", "assistant"] and content:
                                db_role = "assistant" if role == "model" else role
                                execute_query("""
                                    INSERT INTO chat_logs (mobile, session_id, role, content)
                                    VALUES (%s, %s, %s, %s)
                                """, (clean_mobile, session_id, db_role, content))
                    except Exception as db_err:
                        print(f"Error logging message to database: {db_err}")
            
            # 1GB Size Check & Truncation (1GB = 1,073,741,824 bytes)
            # To test we simulate with a safe limit, but apply logic to drop first items
            max_size_bytes = 1024 * 1024 * 1024  # 1GB
            
            # Serialize to check size
            serialized = json.dumps(existing_data, indent=2, ensure_ascii=False)
            
            while len(serialized.encode('utf-8')) > max_size_bytes and len(existing_data["conversations"]) > 1:
                # Remove the oldest conversation from the top
                existing_data["conversations"].pop(0)
                serialized = json.dumps(existing_data, indent=2, ensure_ascii=False)
            
            # Save updated list
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(serialized)
            except Exception as e:
                print(f"Error saving conversation to file: {e}")

def get_last_n_messages_from_log(mobile: str, n: int = 30) -> list:
    """
    Reads the conversation log for the given mobile number (first from DB for speed and scalability,
    with JSON file fallback) and returns up to the last N messages.
    """
    import os
    import json
    
    clean_mobile = "".join(c for c in str(mobile) if c.isalnum() or c in "-_")
    
    # 1. High-Performance DB query
    try:
        from src.db_connection import execute_query
        rows = execute_query("""
            SELECT role, content FROM chat_logs
            WHERE mobile = %s
            ORDER BY timestamp DESC, id DESC
            LIMIT %s
        """, (clean_mobile, n))
        if rows:
            # The query returns most recent messages first, so we reverse it
            messages = []
            for r in reversed(rows):
                messages.append({
                    "role": r["role"],
                    "content": r["content"]
                })
            return messages
    except Exception as db_err:
        print(f"[DB Logs Warning] Failed to query database chat logs: {db_err}. Falling back to file logs.")
        
    # 2. File fallback
    file_path = os.path.join(os.getcwd(), "conversations", f"{clean_mobile}.json")
    messages = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "conversations" in data:
                    for conv in data["conversations"]:
                        if "history" in conv:
                            for msg in conv["history"]:
                                if msg.get("role") in ["user", "assistant", "model"] and msg.get("content"):
                                    messages.append({
                                        "role": "assistant" if msg["role"] == "model" else msg["role"],
                                        "content": msg["content"]
                                    })
        except Exception as e:
            print(f"Error loading conversation logs from file: {e}")
            
    return messages[-n:]

def analyze_customer_interest(messages: list) -> str:
    """
    Analyzes conversation history (last 30 messages) to identify the customer's primary travel interest.
    Returns one of: 'Railway Ticket Booking', 'Currency Exchange', 'Flight Booking', 'Hotel Reservation', 'Holiday Tour & Visas', 'Car Rental', or 'None'.
    """
    if not messages:
        return "None"
        
    history_text = ""
    for msg in messages:
        history_text += f"{msg['role'].upper()}: {msg['content']}\n"
        
    analysis_prompt = [
        {
            "role": "user",
            "content": (
                "You are an expert customer profiling AI.\n"
                "Analyze the following conversation history between a customer and our travel support agent.\n"
                "Determine if the customer has a primary interest in one of these specific travel service sectors:\n"
                "- 'Railway Ticket Booking' (if they ask about train times, PNR, train tickets, bookings)\n"
                "- 'Currency Exchange' (if they ask about exchanging currency, rates, foreign money)\n"
                "- 'Flight Booking' (if they ask about flight tickets, timings, flight status)\n"
                "- 'Hotel Reservation' (if they ask about hotel stays, bookings)\n"
                "- 'Holiday Tour & Visas' (if they ask about packages, holiday trips, visa processing)\n"
                "- 'Car Rental' (if they ask about renting cabs, cars, travels)\n\n"
                "Rules:\n"
                "1. If the customer has shown interest in one of these sectors, return ONLY the exact category name from the list above.\n"
                "2. If there is no clear interest in these specific services in the chat history, or they are just asking general help/support, return 'None'.\n"
                "3. Your output must be exactly one of the category names or 'None', with no other text, explanation, or punctuation.\n\n"
                "Conversation History:\n" + history_text
            )
        }
    ]
    
    try:
        # We call the LLM to get the category
        content, _, _, _, _, _, _, _ = call_llm_with_routing(
            messages=analysis_prompt,
            tools=[],
            system_instruction="You are a precise classifier. Return only the category or 'None'.",
            timeline=[]
        )
        if content:
            result = str(content).strip().replace('"', '').replace("'", "")
            valid_categories = ['Railway Ticket Booking', 'Currency Exchange', 'Flight Booking', 'Hotel Reservation', 'Holiday Tour & Visas', 'Car Rental']
            for cat in valid_categories:
                if cat.lower() in result.lower():
                    return cat
        return "None"
    except Exception as e:
        print(f"[Interest Analysis Error] Failed: {e}")
        return "None"

def is_devanagari(text: str) -> bool:
    """
    Returns True if the text contains Devanagari characters (indicating Hindi script).
    """
    for char in text:
        if 0x0900 <= ord(char) <= 0x097F:
            return True
    return False

def generate_admin_report() -> str:
    """
    Compiles a status report of all active customers today, their field of interest,
    and the probability of closing deals. Returns the text report.
    """
    import os
    import json
    import datetime
    from src.db_connection import execute_query
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # 1. Fetch interest mappings from DB
    interests_map = {}
    try:
        rows = execute_query("SELECT mobile, interest FROM customer_interests")
        for r in rows:
            interests_map[r["mobile"]] = r["interest"]
    except Exception as e:
        print(f"Error reading interests map: {e}")
        
    # 2. Fetch customer names from DB
    names_map = {}
    try:
        rows = execute_query("SELECT mobile, name FROM customers")
        for r in rows:
            names_map[r["mobile"]] = r["name"]
    except Exception as e:
        print(f"Error reading names map: {e}")

    # 3. Scan conversations directory for customers talked to today
    conv_dir = os.path.join(os.getcwd(), "conversations")
    today_customers = []
    
    if os.path.exists(conv_dir):
        for fname in os.listdir(conv_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(conv_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        mobile = data.get("mobile")
                        if not mobile or mobile.startswith("session_"):
                            continue
                            
                        # Check if they had a conversation today
                        had_chat_today = False
                        messages_today = []
                        for conv in data.get("conversations", []):
                            if conv.get("timestamp", "").startswith(today_str):
                                had_chat_today = True
                                if "history" in conv:
                                    for msg in conv["history"]:
                                        if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                                            messages_today.append(f"{msg['role'].upper()}: {msg['content']}")
                                            
                        if had_chat_today:
                            name = names_map.get(mobile, "Unknown")
                            interest = interests_map.get(mobile, "None")
                            today_customers.append({
                                "mobile": mobile,
                                "name": name,
                                "interest": interest,
                                "chat_history": "\n".join(messages_today[-10:])
                            })
                except Exception as e:
                    print(f"Error parsing conversation file {fname}: {e}")
                    
    # 4. Analyze closing probability using LLM for each today_customer
    high_chance_deals = []
    for cust in today_customers:
        if not cust["chat_history"]:
            continue
            
        deal_prompt = [
            {
                "role": "user",
                "content": (
                    "Analyze this travel chat history. Decide if there is a HIGH chance or 100% chance "
                    "that this customer is ready to close/confirm a booking or deal right now.\n"
                    "Criteria for HIGH/100% chance:\n"
                    "- Customer says: 'book/confirm it', 'haa ticket kar do', 'confirm kar do', 'pay kar raha hoon', 'rates are okay, proceed'.\n"
                    "- Customer is asking for account details to pay, or sent payment confirmation.\n\n"
                    "Respond with exactly one word: 'Yes' (if high/100% chance) or 'No' (if low/medium chance).\n\n"
                    "Chat History:\n" + cust["chat_history"]
                )
            }
        ]
        
        try:
            content, _, _, _, _, _, _, _ = call_llm_with_routing(
                messages=deal_prompt,
                tools=[],
                system_instruction="You are a precise sales opportunity detector. Output ONLY 'Yes' or 'No'.",
                timeline=[]
            )
            if content and "yes" in str(content).lower():
                high_chance_deals.append(cust)
        except Exception as e:
            print(f"Failed to analyze deal chance for {cust['mobile']}: {e}")
            
    # 5. Format the report
    report = f"SHREE SHUBH TRAVEL - DAILY STATUS REPORT ({today_str})\n"
    report += "=" * 50 + "\n\n"
    report += f"Total Customers Talked to Today: {len(today_customers)}\n\n"
    
    report += "CUSTOMER DETAILS & INTERESTS:\n"
    report += "-" * 30 + "\n"
    if today_customers:
        for idx, cust in enumerate(today_customers, 1):
            report += f"{idx}. Name: {cust['name']} | Mobile: {cust['mobile']} | Interest: {cust['interest']}\n"
    else:
        report += "No active conversations today.\n"
        
    report += "\n"
    report += "HIGH PROBABILITY DEALS (100% / Ready to Close):\n"
    report += "-" * 30 + "\n"
    if high_chance_deals:
        for idx, deal in enumerate(high_chance_deals, 1):
            report += f"{idx}. Name: {deal['name']} | Mobile: {deal['mobile']} | Sector: {deal['interest']} (Ready to Close!)\n"
    else:
        report += "No high-probability deals detected today.\n"
        
    report += "\nReport Generated Automatically on " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
    return report

def process_agent_message(session_id: str, user_message: str, customer_id: str = None) -> Dict[str, Any]:
    """
    Coordinates session memory, model routing, tool execution, and response validation.
    """
    mobile_to_check = customer_id or session_id
    
    # 0. Retrieve customer's interest from DB first (instant local fetch)
    detected_interest = "None"
    try:
        from src.db_connection import execute_query
        rows = execute_query("SELECT interest FROM customer_interests WHERE mobile = %s", (mobile_to_check,))
        if rows and rows[0].get("interest"):
            detected_interest = rows[0]["interest"]
    except Exception as e:
        print(f"[Interest Fetch Warning] Failed to fetch interest: {e}")
        
    # Start LLM analysis and DB updates asynchronously in a background daemon thread
    try:
        import threading
        def run_interest_profiling_task(mobile: str, msg: str):
            try:
                last_chats = get_last_n_messages_from_log(mobile, n=30)
                last_chats.append({"role": "user", "content": msg})
                new_interest = analyze_customer_interest(last_chats)
                
                from src.db_connection import execute_query
                execute_query("""
                    INSERT INTO customer_interests (mobile, interest)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE interest = %s
                """, (mobile, new_interest, new_interest))
                print(f"[Interest Logger Async] Saved interest '{new_interest}' for mobile {mobile}")
            except Exception as async_err:
                print(f"[Interest Logger Async Error] {async_err}")
                
        threading.Thread(target=run_interest_profiling_task, args=(mobile_to_check, user_message), daemon=True).start()
    except Exception as ie:
        print(f"[Interest Logger Warning] Failed to start async profiling: {ie}")
    
    # 1. Fetch customer details from database to verify if name exists
    customer = {}
    try:
        from src.tools.read_tools import get_customer
        customer = get_customer(mobile_to_check)
        
        # If the customer is completely new (not in database), create their credentials instantly
        if not customer:
            from src.db_connection import execute_query
            cust_code = f"CUST_{mobile_to_check[-4:]}"
            execute_query("""
                INSERT INTO customers (mobile, name, customer_code)
                VALUES (%s, %s, %s)
            """, (mobile_to_check, "Customer", cust_code))
            print(f"[New Customer Tracker] Auto-created database credentials for new customer: {mobile_to_check}")
            # Re-fetch the newly created customer record
            customer = get_customer(mobile_to_check)
    except Exception as e:
        print(f"[Name Check / Insertion Warning] Failed to query/insert customer: {e}")
        
    has_name = False
    customer_name = ""
    if customer and customer.get("name"):
        customer_name = str(customer.get("name")).strip()
        if customer_name and customer_name.lower() not in ["unknown", "none", "null", "customer", "user"]:
            has_name = True
            
    context = memory.get_context(session_id)
    state = context.get("state")
    
    # Pre-fetch and cache customer mobile if customer_mobile is missing in context
    if not context.get("customer_mobile") and customer and customer.get("mobile"):
        memory.update_context(session_id, "customer_mobile", customer.get("mobile"))
        
    is_hindi_input = is_devanagari(user_message)
    if not has_name:
        # Run name extraction to check if they already provided their name in this message
        timeline = []
        start_time_extract = time.time()
        timeline.append({
            "timestamp": time.strftime("%H:%M:%S", time.localtime(start_time_extract)),
            "event": f"Pre-extracting name from user response: '{user_message}'"
        })
        
        extraction_prompt = [
            {
                "role": "user",
                "content": (
                    "Analyze the user's message. If the user is telling their name (e.g. 'Sajal', 'My name is Amit', 'अमित कुमार'), "
                    "extract ONLY the name itself, with correct capitalization, and absolutely no other text.\n"
                    "If the user is ignoring the name prompt and asking a query, booking a service, or talking about something else "
                    "(e.g. 'ticket price?', 'train timing', 'Hwh to Asr train', 'booking details', 'pnr'), return ONLY the word 'Unrelated'.\n"
                    "Message: '" + user_message + "'"
                )
            }
        ]
        
        extracted_name = "Unknown"
        llm_failed = False
        try:
            content, _, _, _, _, _, _, _ = call_llm_with_routing(
                messages=extraction_prompt,
                tools=[],
                system_instruction="You are a precise name extractor. Extract the name and output nothing else.",
                timeline=timeline
            )
            if content:
                extracted_name = str(content).strip().replace(".", "").replace('"', '').replace("'", "")
        except Exception as e:
            print(f"[Name Extraction Error] Failed: {e}")
            llm_failed = True
            
        if llm_failed:
            if is_hindi_input:
                apology = "क्षमा करें, वर्तमान में कुछ तकनीकी समस्याओं के कारण हम आपके संदेश का उत्तर नहीं दे पा रहे हैं। कृपया कुछ समय बाद पुनः प्रयास करें।"
            else:
                apology = "Sorry, due to some technical issues we are unable to process your request right now. Please try again in a few moments."
                
            memory.add_message(session_id, role="user", content=user_message)
            memory.add_message(session_id, role="model", content=apology)
            save_conversation_to_file(session_id)
            
            return {
                "session_id": session_id,
                "response": apology,
                "provider": "System",
                "model": "System_PreCheck_Failed",
                "response_time_ms": (time.time() - start_time_extract) * 1000,
                "fallback_used": False,
                "fallback_reason": "LLM failed during name extraction",
                "called_tools": [],
                "timeline": timeline
            }
            
        if extracted_name and extracted_name.lower() not in ["unknown", "none", "null", "unrelated"]:
            # Name successfully extracted! Save to DB, greet them, and reset state.
            try:
                from src.db_connection import execute_query
                first_name = extracted_name.split()[0]
                query = "UPDATE customers SET name = %s WHERE mobile = %s"
                execute_query(query, (extracted_name, mobile_to_check))
                print(f"[Name Check] Successfully saved customer name: '{extracted_name}' for mobile {mobile_to_check}")
            except Exception as db_err:
                print(f"[Name Check DB Error] Failed to save name: {db_err}")
                
            memory.update_context(session_id, "state", None)
            
            if is_hindi_input:
                success_reply = f"धन्यवाद {first_name}! आपका नाम दर्ज कर लिया गया है। अब बताइए, मैं आपकी क्या सहायता कर सकता हूँ?"
            else:
                success_reply = f"Thank you {first_name}! Your name has been registered. Now tell me, how can I help you?"
                
            memory.add_message(session_id, role="user", content=user_message)
            memory.add_message(session_id, role="model", content=success_reply)
            save_conversation_to_file(session_id)
            
            return {
                "session_id": session_id,
                "response": success_reply,
                "provider": "System",
                "model": "System_PreCheck",
                "response_time_ms": (time.time() - start_time_extract) * 1000,
                "fallback_used": False,
                "fallback_reason": None,
                "called_tools": [],
                "timeline": timeline
            }
        elif extracted_name and extracted_name.lower() == "unrelated":
            # If the user sent a query instead of their name, don't block them!
            # Set state to waiting_for_name and increment reminder count, but pass through to let agent answer.
            count = context.get("name_reminder_count", 0) + 1
            memory.update_context(session_id, "state", "waiting_for_name")
            memory.update_context(session_id, "name_reminder_count", count)
            print(f"[Name Check] User sent unrelated query: '{user_message}'. Bypassing block. Reminder count: {count}")
            pass
        else:
            # It is a simple greeting (like Hi/Hello) or name could not be extracted.
            if state != "waiting_for_name":
                # Prompt them for their name (State 1)
                memory.update_context(session_id, "state", "waiting_for_name")
                memory.update_context(session_id, "name_reminder_count", 0)
                
                if is_hindi_input:
                    greeting = "नमस्ते! श्री शुभ ट्रेवल्स में आपका स्वागत है। आगे की बातचीत को सुचारू और विश्वासपूर्ण बनाने के लिए कृपया करके अपना नाम बता दीजिए।"
                else:
                    greeting = "Hello! Shree Shubh Travels mein aapka swagat hai. Aage ki baat-jeet ko smooth aur helpful banane ke liye, please mujhe apna naam bata dijiye."
                
                memory.add_message(session_id, role="user", content=user_message)
                memory.add_message(session_id, role="model", content=greeting)
                save_conversation_to_file(session_id)
                
                return {
                    "session_id": session_id,
                    "response": greeting,
                    "provider": "System",
                    "model": "System_PreCheck",
                    "response_time_ms": (time.time() - start_time_extract) * 1000,
                    "fallback_used": False,
                    "fallback_reason": None,
                    "called_tools": [],
                    "timeline": timeline
                }
            else:
                # They were already prompted, but replied with another greeting or invalid name text. Ask again.
                if is_hindi_input:
                    ask_again = "कृपया अपना सही नाम बताएं ताकि हम बातचीत शुरू कर सकें।"
                else:
                    ask_again = "Please apna sahi naam bataiye taaki hum aage baat kar sakein."
                    
                memory.add_message(session_id, role="user", content=user_message)
                memory.add_message(session_id, role="model", content=ask_again)
                save_conversation_to_file(session_id)
                
                return {
                    "session_id": session_id,
                    "response": ask_again,
                    "provider": "System",
                    "model": "System_PreCheck",
                    "response_time_ms": (time.time() - start_time_extract) * 1000,
                    "fallback_used": False,
                    "fallback_reason": None,
                    "called_tools": [],
                    "timeline": timeline
                }

    timeline = []
    start_time = time.time()
    
    timeline.append({
        "timestamp": time.strftime("%H:%M:%S", time.localtime(start_time)),
        "event": f"Message received: '{user_message}'"
    })
    
    # 1. Update session memory with user message
    memory.add_message(session_id, role="user", content=user_message)
    
    # Track metrics for the final response
    called_tools = []
    provider_name = ""
    model_name = ""
    total_model_latency = 0.0
    fallback_used = False
    fallback_reason = None
    
    max_turns = 5
    turn = 0
    
    is_hindi_script = is_devanagari(user_message)
    while turn < max_turns:
        turn += 1
        history = memory.get_history(session_id)
        
        # Inject customer name dynamically in system prompt (using only the first/starting word, without 'ji'/'जी')
        custom_system_instruction = SYSTEM_PROMPT
        if has_name and customer_name:
            first_name = customer_name.split()[0] if customer_name else ""
            custom_system_instruction = (
                f"{SYSTEM_PROMPT}\n"
                f"CRITICAL: The customer's name is '{first_name}'. You MUST greet them using their name "
                f"(e.g., 'Hello {first_name}' or 'नमस्ते {first_name}') in your response, especially on their first greeting (Hi/Hello). "
                f"Do NOT add 'ji' or 'जी' after their name."
            )
            
        # Enforce language instructions based on user message script
        if is_hindi_script:
            lang_instruction = "CRITICAL: The customer is writing in Hindi script (Devanagari). Respond ONLY in Hindi script, using feminine verb endings (e.g., 'karti hoon', 'bataungi')."
        else:
            lang_instruction = (
                "CRITICAL: The customer is writing in Latin script (English/Hinglish). You MUST respond in Hinglish (Hindi written in English alphabet, e.g., 'Haan main check kar leti hoon') "
                "using feminine verb endings (e.g. 'karti hoon', 'dekhungi'). Do NOT respond in Hindi script (Devanagari)."
            )
        custom_system_instruction = f"{custom_system_instruction}\n{lang_instruction}"
            
        # Add dynamic guidelines based on customer interest (analyzed from last 30 messages)
        if detected_interest == "None" or not detected_interest:
            custom_system_instruction = (
                f"{custom_system_instruction}\n"
                f"Note: The customer has no specific service interest detected in the last 30 messages. "
                f"Act as a general, warm, and helpful customer service assistant representing Shree Shubh Travel, "
                f"and address their queries politely without aggressive sales pitches."
            )
        else:
            custom_system_instruction = (
                f"{custom_system_instruction}\n"
                f"Note: The customer is primarily interested in the '{detected_interest}' sector. "
                f"Act as a sales champion for '{detected_interest}' services. "
                f"Steer the conversation towards presenting and closing deals for '{detected_interest}' services enthusiastically!"
            )
            
        # Call model with routing
        content, tool_calls, raw, p_name, m_name, latency, fb_used, fb_reason = call_llm_with_routing(
            messages=history,
            tools=TOOLS_DECLARATIONS,
            system_instruction=custom_system_instruction,
            timeline=timeline
        )
        
        # Accumulate metrics
        provider_name = p_name
        model_name = m_name
        total_model_latency += latency
        if fb_used:
            fallback_used = True
            fallback_reason = fb_reason
            
        if tool_calls:
            # Handle tool calls requested by model
            # Append model message with tool calls to session memory
            memory.add_message(session_id, role="assistant", content=content or "", tool_calls=tool_calls)
            
            for tc in tool_calls:
                t_name = tc["name"]
                t_args = tc["args"]
                t_id = tc.get("id")
                called_tools.append(t_name)
                
                timeline.append({
                    "timestamp": time.strftime("%H:%M:%S"),
                    "event": f"Executing tool: {t_name} with args {t_args}"
                })
                
                # Execute tool - let any exceptions bubble up to the server level
                tool_res = execute_tool(t_name, t_args, session_id=session_id)
                
                timeline.append({
                    "timestamp": time.strftime("%H:%M:%S"),
                    "event": f"Tool {t_name} result received."
                })
                
                # Append tool response message to session memory
                memory.add_message(
                    session_id,
                    role="tool",
                    tool_name=t_name,
                    tool_response=tool_res,
                    tool_call_id=t_id
                )
                
            # Loop continues for next turn
        else:
            # Final text response
            final_content = content or ""
            
            # Validate response
            timeline.append({
                "timestamp": time.strftime("%H:%M:%S"),
                "event": "Validating agent response safety & accuracy..."
            })
            
            history_for_val = memory.get_history(session_id)[:-1] # Exclude final prompt turn if desired, or send full
            validated_content = validate_agent_response(
                response_text=final_content,
                called_tools=called_tools,
                session_history=history_for_val
            )
            
            # Save validated model response in memory
            memory.add_message(session_id, role="assistant", content=validated_content)
            
            total_duration = (time.time() - start_time) * 1000
            timeline.append({
                "timestamp": time.strftime("%H:%M:%S"),
                "event": f"Processing finished. Response ready. Total execution: {total_duration:.1f}ms"
            })
            
            # Check if voice_mode is active in session context
            audio_url = None
            context = memory.get_context(session_id)
            if context.get("voice_mode") is True:
                timeline.append({
                    "timestamp": time.strftime("%H:%M:%S"),
                    "event": "Voice mode is active. Synthesizing response to audio..."
                })
                try:
                    from src.services.voice import preprocess_text_for_speech, generate_voice_audio
                    processed_text = preprocess_text_for_speech(validated_content)
                    audio_url = generate_voice_audio(processed_text, session_id)
                    timeline.append({
                        "timestamp": time.strftime("%H:%M:%S"),
                        "event": f"Voice synthesis completed: {audio_url}"
                    })
                except Exception as ve:
                    timeline.append({
                        "timestamp": time.strftime("%H:%M:%S"),
                        "event": f"Voice auto-synthesis failed: {str(ve)}"
                    })
            
            response_payload = {
                "session_id": session_id,
                "response": validated_content,
                "provider": provider_name,
                "model": model_name,
                "response_time_ms": total_model_latency,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "called_tools": called_tools,
                "timeline": timeline,
                "voice_mode": context.get("voice_mode", False)
            }
            if audio_url:
                response_payload["audio_url"] = audio_url
                
            # If customer name is still missing and they are in the waiting_for_name state (unrelated query processed),
            # append a polite single-line reminder ONLY after 3 unrelated messages (count % 3 == 0) to avoid spamming.
            count = context.get("name_reminder_count", 0)
            if state == "waiting_for_name" and count > 0 and count % 3 == 0 and "response" in response_payload:
                if is_hindi_script:
                    reminder = "\n\n(वैसे, कृपया अपना नाम भी बता दीजिए ताकि आगे की बातचीत को हम आपके नाम के साथ सुचारू बना सकें।)"
                else:
                    reminder = "\n\n(By the way, please apna naam bhi bata dijiye taaki hum aapke naam ke sath aage ki chat continue kar sakein.)"
                
                response_payload["response"] += reminder
                try:
                    history = memory.get_history(session_id)
                    if history and history[-1]["role"] == "assistant":
                        history[-1]["content"] += reminder
                except Exception as e:
                    print(f"Failed to append reminder to memory history: {e}")
                
            # Write dynamic conversation log to file
            save_conversation_to_file(session_id)
            
            return response_payload
            
    # Default fallback if loop limit exceeded
    raise RuntimeError("Agent loop exceeded maximum turns without generating a final text response.")
