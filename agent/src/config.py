import os
from dotenv import load_dotenv

# Resolve paths dynamically
agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_dir = os.path.dirname(agent_dir)
env_path = os.path.join(root_dir, ".env")

print(f"\n[Config] Scanning for .env file at: {env_path}")
if os.path.exists(env_path):
    print(f"[Config] Found .env file. Loading variables...")
    load_dotenv(dotenv_path=env_path)
else:
    print(f"[Config] WARNING: .env file NOT found at {env_path}!")

def _get_clean_env(key: str, default: str = "") -> str:
    val = os.getenv(key, default)
    if val:
        cleaned = str(val).strip().replace("\r", "").replace('"', '').replace("'", "")
        # Print masked key on startup for visual confirmation
        if "KEY" in key or "PASSWORD" in key:
            if len(cleaned) > 10:
                masked = f"{cleaned[:6]}...{cleaned[-4:]}"
            else:
                masked = "********"
            print(f"[Config] Loaded {key}: {masked}")
        else:
            print(f"[Config] Loaded {key}: {cleaned}")
        return cleaned
    else:
        if "KEY" in key or "PASSWORD" in key:
            print(f"[Config] Loaded {key}: [EMPTY/MISSING]")
        return default

def _ensure_gemini_api_key() -> str:
    key = _get_clean_env("GEMINI_API_KEY", "")
    placeholder_values = ["your_gemini_api_key", "your_gemini_api_key_here", ""]
    
    is_incomplete = "___" in key or not key or key.strip().lower() in placeholder_values
    
    if is_incomplete:
        import sys
        if sys.stdin.isatty():
            print("\n" + "="*60)
            print("🔑 GEMINI_API_KEY is incomplete or not configured in .env!")
            print(f"Current value in .env: {key}")
            print("Please paste your COMPLETE Google Gemini API key to continue setup.")
            print("="*60 + "\n")
            try:
                user_key = input("Enter Complete Gemini API Key: ").strip().replace('"', '').replace("'", "")
                if user_key and user_key.lower() not in placeholder_values and "___" not in user_key:
                    if os.path.exists(env_path):
                        lines = open(env_path, "r", encoding="utf-8").read().splitlines()
                        updated = False
                        for i, line in enumerate(lines):
                            if line.startswith("GEMINI_API_KEY="):
                                lines[i] = f"GEMINI_API_KEY={user_key}"
                                updated = True
                        if not updated:
                            lines.append(f"GEMINI_API_KEY={user_key}")
                        open(env_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
                        print(f"✅ Success! Gemini API Key written permanently to: {env_path}")
                        return user_key
            except Exception as e:
                print(f"Error saving key: {e}")
        else:
            print("\n[Config ERROR] GEMINI_API_KEY is not configured and stdin is not a terminal.")
            print("Please set GEMINI_API_KEY in your .env file manually or run the setup interactively.\n")
            
    return key

class Config:
    GEMINI_API_KEY = _ensure_gemini_api_key()
    GROQ_API_KEY = _get_clean_env("GROQ_API_KEY", "")

    PRIMARY_PROVIDER = _get_clean_env("PRIMARY_PROVIDER", "gemini")
    PRIMARY_MODEL = _get_clean_env("PRIMARY_MODEL", "gemini-1.5-flash")

    SECONDARY_PROVIDER = _get_clean_env("SECONDARY_PROVIDER", "gemini")
    SECONDARY_MODEL = _get_clean_env("SECONDARY_MODEL", "gemini-1.5-flash")

    FALLBACK_PROVIDER = _get_clean_env("FALLBACK_PROVIDER", "groq")
    GROQ_MODEL = _get_clean_env("GROQ_MODEL", "qwen/qwen3.6-27b")

    NODE_ENV = _get_clean_env("NODE_ENV", "development")
    AGENT_MODE = _get_clean_env("AGENT_MODE", "testing") # "testing" or "production"

    DB_HOST = _get_clean_env("DB_HOST", "srv841.hstgr.io")
    DB_PORT = int(_get_clean_env("DB_PORT", "3306"))
    DB_USER = _get_clean_env("DB_USER", "u488903298_root")
    DB_PASSWORD = _get_clean_env("DB_PASSWORD", "ShreeShubh@234")
    DB_NAME = _get_clean_env("DB_NAME", "u488903298_ytsk")

    AZURE_SPEECH_KEY = _get_clean_env("AZURE_SPEECH_KEY", "")
    AZURE_SPEECH_REGION = _get_clean_env("AZURE_SPEECH_REGION", "eastus")
    RAILKIT_API_KEY = _get_clean_env("RAILKIT_API_KEY", "")

    @classmethod
    def validate(cls):
        # Validate that API keys are set
        if not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in environment.")
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in environment.")
        if not cls.AZURE_SPEECH_KEY:
            # We raise a warning/error when synthesis is triggered rather than blocking boot,
            # but let's check it.
            pass
        
        # Verify db credentials are basic-checked
        if not cls.DB_NAME:
            raise ValueError("DB_NAME is not set in environment.")
