import traceback
import time
import threading
import datetime
import requests
import base64
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from src.agent.core import process_agent_message, generate_admin_report
from src.agent.memory import memory
from src.db_connection import execute_query
from src.services.voice import generate_voice_audio
from src.config import Config

app = FastAPI(title="Shree Shubh Travel AI Agent Testing API")

# Background thread to generate and send daily report to Admin at 9:00 PM (21:00)
def schedule_admin_report():
    admin_mobile = "9415345750"
    last_sent_date = None
    
    print("[Scheduler] Started daily report scheduler thread.")
    
    # Wait 60 seconds on startup to make sure all services are fully initialized before running checks
    time.sleep(60)
    
    while True:
        try:
            now = datetime.datetime.now()
            # Run every day at 9:00 PM (21:00)
            if now.hour == 21 and now.minute == 0 and last_sent_date != now.date():
                print(f"[Scheduler] Time is {now.strftime('%H:%M:%S')}. Compiling daily admin report...")
                report_text = generate_admin_report()
                report_base64 = base64.b64encode(report_text.encode('utf-8')).decode('utf-8')
                
                headers = {
                    "x-api-token": Config.SECRET_TOKEN,
                    "Content-Type": "application/json"
                }
                payload = {
                    "token": Config.SECRET_TOKEN,
                    "mobile": admin_mobile,
                    "file_content_base64": report_base64,
                    "filename": f"Daily_Report_{now.strftime('%Y-%m-%d')}.txt",
                    "mime_type": "text/plain"
                }
                
                # Derive Node URL dynamically
                node_url = "http://127.0.0.1:3333/send-document"
                if hasattr(Config, "WA_API_URL") and Config.WA_API_URL:
                    node_url = f"{Config.WA_API_URL.rstrip('/')}/send-document"
                    
                res = requests.post(node_url, json=payload, headers=headers, timeout=30)
                print(f"[Scheduler] Daily report sent to admin. Node response: {res.text}")
                last_sent_date = now.date()
        except Exception as e:
            print(f"[Scheduler Error] Failed to compile or send daily report: {e}")
            
        time.sleep(30) # Check every 30 seconds

threading.Thread(target=schedule_admin_report, daemon=True).start()

# Mount testing frontend static files
# We mount the path 'testing/frontend' so we can serve HTML, CSS and JS files
app.mount("/static", StaticFiles(directory="testing/frontend"), name="static")

# Serve the main index.html at root
@app.get("/")
def read_root():
    return FileResponse("testing/frontend/index.html")

# Chat request Pydantic model
class ChatRequest(BaseModel):
    session_id: str
    message: str
    customer_id: Optional[str] = None

class ClearSessionRequest(BaseModel):
    session_id: str

class TTSRequest(BaseModel):
    text: str
    session_id: str

# 1. Main Chat Endpoint
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # As requested: do not suppress errors. If an error occurs in Agent Core,
    # let it raise, catch it in a global handler, and return the FULL technical traceback.
    try:
        result = process_agent_message(
            session_id=request.session_id,
            user_message=request.message,
            customer_id=request.customer_id
        )
        model_used = result.get("model", "Unknown Model")
        print(f"\n==========================================================")
        print(f"Sent From {model_used}")
        print(f"==========================================================\n")
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        tb = traceback.format_exc()
        # Return a 500 status code with detailed traceback
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_class": e.__class__.__name__,
                "error_message": str(e),
                "traceback": tb
            }
        )

# 1.5. Text-To-Speech (TTS) Endpoint
@app.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    # Preprocess the text to expand station codes first
    processed_text = request.text
    try:
        from src.services.voice import preprocess_text_for_speech
        processed_text = preprocess_text_for_speech(request.text)
    except Exception as e:
        print(f"Text preprocessing failed: {e}")
        
    try:
        audio_url = generate_voice_audio(processed_text, request.session_id)
        # Format the text returned to the browser so pause markers become natural ellipsis pauses
        browser_text = processed_text.replace("[PAUSE_700]", "... ")
        return {
            "status": "success",
            "audio_url": audio_url,
            "processed_text": browser_text
        }
    except Exception as e:
        tb = traceback.format_exc()
        browser_text = processed_text.replace("[PAUSE_700]", "... ")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_class": e.__class__.__name__,
                "error_message": str(e),
                "traceback": tb,
                "processed_text": browser_text
            }
        )

# 2. Get list of customers from local ytsk database to populate UI dropdown
@app.get("/api/customers")
def get_customers_endpoint():
    try:
        # Fetch customers for UI dropdown selection
        query = "SELECT id, customer_code, name, mobile, origin_sector FROM customers ORDER BY id DESC LIMIT 50"
        customers = execute_query(query)
        return {
            "status": "success",
            "customers": customers
        }
    except Exception as e:
        tb = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_class": e.__class__.__name__,
                "error_message": str(e),
                "traceback": tb
            }
        )

# 3. Active sessions listing
@app.get("/api/sessions")
def get_sessions_endpoint():
    sessions = memory.get_all_sessions()
    return {
        "status": "success",
        "sessions": sessions
    }

# 4. Clear memory session
@app.post("/api/sessions/clear")
def clear_session_endpoint(request: ClearSessionRequest):
    memory.clear_session(request.session_id)
    return {
        "status": "success",
        "message": f"Session {request.session_id} has been cleared."
    }

# 5. Live Provider Status Checker
@app.get("/api/provider-status")
def provider_status_endpoint():
    # Simple check endpoint for providers. It tries a fast ping/health check
    # or just returns static configured variables. We'll return the configured primary, secondary, and fallback
    # with online indicator.
    return {
        "status": "success",
        "providers": {
            "primary": {
                "name": "Google Gemini 2.5 Flash",
                "status": "configured"
            },
            "secondary": {
                "name": "Google Gemini 2.5 Flash-Lite",
                "status": "configured"
            },
            "fallback": {
                "name": "Groq Llama 3.3 70b",
                "status": "configured"
            }
        }
    }
