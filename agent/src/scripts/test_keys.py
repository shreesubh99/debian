import os
import sys
import httpx

# Resolve paths
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PARENT_DIR)

from src.config import Config

def test_gemini():
    print("==========================================================")
    print("Testing Google Gemini API Key...")
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        print("[ERROR] Gemini API Key is missing in .env!")
        return
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "ping"}]}]
    }
    try:
        r = httpx.post(url, json=payload, timeout=10.0)
        print(f"HTTP Status: {r.status_code}")
        if r.status_code == 200:
            print("[SUCCESS] Gemini API Key is valid and working!")
        else:
            print(f"[FAILED] Gemini API returned error: {r.text}")
    except Exception as e:
        print(f"[ERROR] Failed to make request to Gemini: {e}")

def test_groq():
    print("\n==========================================================")
    print("Testing Groq API Key...")
    api_key = Config.GROQ_API_KEY
    if not api_key:
        print("[ERROR] Groq API Key is missing in .env!")
        return
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5
    }
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        print(f"HTTP Status: {r.status_code}")
        if r.status_code == 200:
            print("[SUCCESS] Groq API Key is valid and working!")
        else:
            print(f"[FAILED] Groq API returned error: {r.text}")
    except Exception as e:
        print(f"[ERROR] Failed to make request to Groq: {e}")
    print("==========================================================\n")

if __name__ == "__main__":
    test_gemini()
    test_groq()
