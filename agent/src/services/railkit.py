import time
import secrets
import hashlib
import hmac
import httpx
from typing import Dict, Any, Optional, List
from src.config import Config

BASE_URL = "https://railkit-api.rajivdubey.dev"
SIGNING_SECRET = "97c56e08b27b161124f88acd4f24d1bd50f48075f11dc23b9ea6c0bc9b2f8794"

def make_railkit_request(path: str, params: Optional[dict] = None) -> Dict[str, Any]:
    """
    Sends an authenticated request to the RailKit REST API using the API key
    configured in the environment. Computes the required Node SDK HMAC-SHA256 headers.
    """
    api_key = getattr(Config, "RAILKIT_API_KEY", "")
    if not api_key:
        return {"success": False, "error": "RAILKIT_API_KEY is not configured in .env file."}
        
    timestamp = str(int(time.time() * 1000))
    nonce = secrets.token_hex(32)
    payload_hash = hashlib.sha256(b"").hexdigest()
    
    # Sig: METHOD + PATH + TS + NONCE + PAYLOAD_HASH + API_KEY
    sig_input = f"GET\n{path}\n{timestamp}\n{nonce}\n{payload_hash}\n{api_key}"
    
    signature = hmac.new(
        SIGNING_SECRET.encode("utf-8"),
        sig_input.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "x-api-key": api_key,
        "Accept": "application/json",
        "x-irctc-sdk-ts": timestamp,
        "x-irctc-sdk-nonce": nonce,
        "x-irctc-sdk-payload-sha256": payload_hash,
        "x-irctc-sdk-signature": signature,
        "x-irctc-sdk-version": "1"
    }
    
    url = f"{BASE_URL}{path}"
    
    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"API returned status code {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"Connection failed: {str(e)}"}


# Fallback Simulation Handlers when API Key is missing in .env
def get_mock_trains(from_stn: str, to_stn: str) -> List[Dict[str, Any]]:
    # Mock some realistic trains for major routes
    from_stn = from_stn.upper()
    to_stn = to_stn.upper()
    return [
        {
            "trainNumber": "13005",
            "trainName": "HWH ASR MAIL",
            "from": from_stn,
            "to": to_stn,
            "departure": "19:15",
            "arrival": "08:40",
            "duration": "13h 25m",
            "runningDays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "classes": ["1A", "2A", "3A", "SL"]
        },
        {
            "trainNumber": "12301",
            "trainName": "HOWRAH RAJDHANI",
            "from": from_stn,
            "to": to_stn,
            "departure": "16:50",
            "arrival": "09:55",
            "duration": "17h 05m",
            "runningDays": ["Mon", "Tue", "Wed", "Thu", "Sat", "Sun"],
            "classes": ["1A", "2A", "3A"]
        }
    ]

def get_mock_live_status(train_no: str) -> Dict[str, Any]:
    return {
        "trainNumber": train_no,
        "trainName": "HWH ASR MAIL" if train_no == "13005" else "EXP-TRAIN",
        "currentStation": "Lucknow Charbagh (LKO)",
        "status": "Running 25 mins late",
        "lastUpdated": time.strftime("%H:%M:%S"),
        "delayMinutes": 25,
        "upcomingStops": [
            {"stationName": "Bareilly (BE)", "scheduledArrival": "03:15", "delayMinutes": 20},
            {"stationName": "Moradabad (MB)", "scheduledArrival": "05:05", "delayMinutes": 15}
        ]
    }

def get_mock_availability(train_no: str, travel_class: str) -> Dict[str, Any]:
    import random
    random.seed(train_no + travel_class)
    avail_status = random.choice([
        f"AVAILABLE-{random.randint(12, 140)}",
        f"AVAILABLE-00{random.randint(1, 9)}",
        f"RAC {random.randint(1, 10)}",
        f"WL {random.randint(1, 24)}"
    ])
    return {
        "trainNumber": train_no,
        "class": travel_class,
        "quota": "GN",
        "status": avail_status,
        "fare": random.choice([1250.0, 740.0, 2450.0, 380.0]),
        "lastUpdated": time.strftime("%H:%M:%S")
    }
