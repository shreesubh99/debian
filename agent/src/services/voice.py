import os
import re
import csv
import azure.cognitiveservices.speech as speechsdk
from src.config import Config

_station_cache = {}

def load_stations():
    """
    Loads railway stations from the generated CSV file into memory cache.
    """
    global _station_cache
    if _station_cache:
        return
    csv_path = "indian_railway_stations.csv"
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("station_code", "").strip().upper()
                    name = row.get("station_name", "").strip()
                    if code and name:
                        # Clean name to expand common railway abbreviations for natural pronunciation
                        cleaned_name = name.upper()
                        cleaned_name = cleaned_name.replace(" JN", " JUNCTION")
                        cleaned_name = cleaned_name.replace(" HLT", " HALT")
                        cleaned_name = cleaned_name.replace("S M V D ", "SHRI MATA VAISHNO DEVI ")
                        
                        # Convert to Title Case for natural pronunciation
                        _station_cache[code] = cleaned_name.title()
        except Exception as e:
            print(f"Error loading station cache: {e}")

def preprocess_text_for_speech(text: str) -> str:
    """
    Preprocesses message text for TTS readout:
    1. Removes markdown symbols (*, _, `, ~).
    2. Replaces station codes (HWH, ASR, etc.) with their full station names.
    """
    load_stations()
    
    # 1. Clean markdown formatting
    clean_text = text.replace("*", "").replace("_", "").replace("`", "").replace("~", "")
    
    # 2. Match uppercase words of length 2 to 6 and lookup in station cache
    def replace_code(match):
        word = match.group(0)
        return _station_cache.get(word.upper(), word)
        
    # Match candidate station codes (e.g. HWH, ASR, NDLS)
    clean_text = re.sub(r"\b[A-Z]{2,6}\b", replace_code, clean_text)
    
    return clean_text

def generate_voice_audio(processed_text: str, session_id: str) -> str:
    """
    Synthesizes preprocessed text to speech using Azure Speech SDK.
    Formats 5-10 digit numbers to read digit-by-digit.
    Injects custom break tags for punctuation and word limits.
    Writes output to a WAV file and returns the static URL.
    """
    if not Config.AZURE_SPEECH_KEY or not Config.AZURE_SPEECH_REGION:
        raise ValueError(
            "Azure Speech credentials (AZURE_SPEECH_KEY, AZURE_SPEECH_REGION) are not configured in your .env file."
        )

    # Clean text to apply explicit break tags for Azure SSML
    # Format 5-10 digit numbers (Train numbers, PNRs, Mobile numbers) to read digit-by-digit
    speech_text = re.sub(r"(\d{5,10})", r'<say-as interpret-as="digits">\1</say-as>', processed_text)

    # Replace pause markers and punctuation with Azure SSML break tags
    speech_text = speech_text.replace("[PAUSE_700]", '<break time="700ms"/>')
    speech_text = speech_text.replace(".", '. <break time="700ms"/>')
    speech_text = speech_text.replace("?", '? <break time="700ms"/>')
    speech_text = speech_text.replace("।", '। <break time="700ms"/>')
    speech_text = speech_text.replace(",", ', <break time="400ms"/>')

    # Ensure audio directory exists inside static frontend folder
    audio_dir = os.path.join("testing", "frontend", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f"{session_id}_{os.urandom(8).hex()}.wav"
    filepath = os.path.join(audio_dir, filename)
    
    # Setup Azure speech config
    speech_config = speechsdk.SpeechConfig(
        subscription=Config.AZURE_SPEECH_KEY, 
        region=Config.AZURE_SPEECH_REGION
    )
    
    # Output to file
    audio_config = speechsdk.audio.AudioOutputConfig(filename=filepath)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    
    pitch = "-0.82876%"
    rate = "0%"
    
    ssml_string = f"""
    <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='hi-IN'>
        <voice name='hi-IN-AnanyaNeural'>
            <prosody pitch='{pitch}' rate='{rate}'>
                {speech_text}
            </prosody>
        </voice>
    </speak>
    """
    
    result = synthesizer.speak_ssml_async(ssml_string).get()
    
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return f"/static/audio/{filename}"
    else:
        cancellation_details = result.cancellation_details
        error_msg = f"Azure TTS synthesis failed: {result.reason}"
        if cancellation_details and cancellation_details.error_details:
            error_msg += f" - {cancellation_details.error_details}"
        raise RuntimeError(error_msg)
