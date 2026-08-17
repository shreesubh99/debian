import os
import sys
import json
import datetime
import google.generativeai as genai

# Resolve paths
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PARENT_DIR)

from src.config import Config

def load_user_corrections():
    corrections_path = os.path.join(PARENT_DIR, "conversations", "user_corrections.json")
    if not os.path.exists(corrections_path):
        return []
    try:
        with open(corrections_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error loading corrections: {e}")
        return []

def load_conversation_sessions():
    conversations_dir = os.path.join(PARENT_DIR, "conversations")
    if not os.path.exists(conversations_dir):
        return []
    
    sessions_data = []
    for fname in os.listdir(conversations_dir):
        if fname.startswith("session_") and fname.endswith(".json") and fname != "user_corrections.json":
            fpath = os.path.join(conversations_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                    if isinstance(messages, list) and len(messages) >= 2:
                        sessions_data.append(messages)
            except Exception:
                pass
    return sessions_data

def prepare_gemini_tuning_dataset():
    print("[Trainer] Preparing dataset from user corrections and chat sessions...")
    
    dataset = []
    
    # 1. Process Corrections
    corrections = load_user_corrections()
    approved_corrections = [c for c in corrections if c.get("status") in ["approved", "pending_verification"]]
    
    for c in approved_corrections:
        dataset.append({
            "text_input": f"Correction Context: {c.get('incorrect_fact')}. Correct it to: {c.get('user_correction_suggestion')}",
            "output": f"Understood. The correct fact is indeed: {c.get('user_correction_suggestion')}."
        })
        
    # 2. Process chat sessions (Only high-quality dialogs)
    sessions = load_conversation_sessions()
    for session in sessions:
        # Convert alternating messages to prompt/response format
        for i in range(len(session) - 1):
            msg = session[i]
            next_msg = session[i+1]
            if msg.get("role") == "user" and next_msg.get("role") == "model":
                dataset.append({
                    "text_input": msg.get("content", ""),
                    "output": next_msg.get("content", "")
                })
                
    print(f"[Trainer] Total training samples prepared: {len(dataset)}")
    return dataset

def trigger_gemini_fine_tuning(dataset):
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        print("[Trainer Error] GEMINI_API_KEY is not defined in .env. Cannot start fine-tuning.")
        return False
        
    if len(dataset) < 20:
        print("[Trainer Warning] Gemini requires at least 20 examples to perform fine-tuning.")
        print("[Trainer Info] Please generate more conversation logs or corrections first.")
        return False
        
    print("[Trainer] Configuring Gemini SDK...")
    genai.configure(api_key=api_key)
    
    # Generate unique suffix
    suffix = datetime.datetime.now().strftime("%Y%m%d%H%M")
    tuned_model_id = f"shree-shubh-travel-tuned-{suffix}"
    
    print(f"[Trainer] Launching Gemini Fine-Tuning Job: {tuned_model_id}...")
    try:
        # Call create_tuned_model using the prepared dataset list
        operation = genai.create_tuned_model(
            source_model="models/gemini-1.5-flash-001-tuning",
            training_data=dataset,
            id=tuned_model_id,
            epoch_count=20,
            batch_size=4,
            learning_rate=0.001
        )
        print(f"[Trainer] Tuning operation created successfully!")
        print(f"[Trainer] Model Name: tunedModels/{tuned_model_id}")
        print("[Trainer] Note: Tuning runs asynchronously on Google servers. It usually takes 5-10 minutes.")
        print("[Trainer] The script will now wait for the model to be ACTIVE before switching the configuration.")
        
        # Wait for the model to become ACTIVE
        import time
        tuned_model_name = f"tunedModels/{tuned_model_id}"
        max_retries = 30  # 15 minutes max
        retries = 0
        model_ready = False
        
        while retries < max_retries:
            try:
                model_info = genai.get_tuned_model(tuned_model_name)
                state = model_info.state.name if hasattr(model_info.state, "name") else str(model_info.state)
                print(f"[Trainer] Current model state: {state} (Check {retries+1}/{max_retries})")
                if state == "ACTIVE":
                    model_ready = True
                    break
                elif state in ["FAILED", "CANCELLED"]:
                    print(f"[Trainer Error] Fine-tuning job failed with state: {state}")
                    return False
            except Exception as e:
                print(f"[Trainer Warning] Failed to fetch model state (will retry): {e}")
            
            time.sleep(30)
            retries += 1
            
        if not model_ready:
            print("[Trainer Error] Tuning took too long. Not updating .env configuration.")
            return False
            
        # Write the model name to .env to switch automatically once ready
        env_path = os.path.join(PARENT_DIR, ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = []
            model_line_found = False
            for line in lines:
                if line.startswith("PRIMARY_MODEL="):
                    new_lines.append(f"PRIMARY_MODEL=tunedModels/{tuned_model_id}\n")
                    model_line_found = True
                else:
                    new_lines.append(line)
                    
            if not model_line_found:
                new_lines.append(f"\nPRIMARY_MODEL=tunedModels/{tuned_model_id}\n")
                
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print("[Trainer] Updated .env file to use the new tuned model automatically.")
            
        return True
    except Exception as e:
        print(f"[Trainer Error] Failed to trigger Gemini tuning: {e}")
        return False

if __name__ == "__main__":
    dataset = prepare_gemini_tuning_dataset()
    if dataset:
        trigger_gemini_fine_tuning(dataset)
    else:
        print("[Trainer] No training data found. Make sure you have chat sessions under agent/conversations/ directory.")
