import httpx
from typing import List, Dict, Any, Tuple, Optional
from src.providers.base import AIProvider

class GeminiProvider(AIProvider):
    """
    Implements the Gemini API integration (3.5 Flash and 3.5 Flash-lite).
    Uses raw httpx calls to v1beta API to ensure full control over timeouts, headers, and exceptions.
    Also handles thoughtSignature and functionCall IDs to prevent bad requests.
    """
    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        timeout: float = 10.0
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        
        # Build API URL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        # Format the chat history into Gemini contents
        contents = []
        for msg in messages:
            role = msg.get("role")
            if role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg.get("content", "")}]
                })
            elif role == "assistant":
                parts = []
                if msg.get("content"):
                    parts.append({"text": msg["content"]})
                
                # Check for cached tool calls mapping back
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fc_obj = {
                            "name": tc["name"],
                            "args": tc["args"]
                        }
                        if tc.get("id"):
                            fc_obj["id"] = tc["id"]
                            
                        part_obj = {"functionCall": fc_obj}
                        if tc.get("thoughtSignature"):
                            part_obj["thoughtSignature"] = tc["thoughtSignature"]
                            
                        parts.append(part_obj)
                        
                # Gemini contents must have parts
                if not parts:
                    parts = [{"text": ""}]
                contents.append({
                    "role": "model",
                    "parts": parts
                })
            elif role == "tool":
                # Find matching function call ID if possible
                func_obj = {
                    "name": msg.get("tool_name", ""),
                    "response": msg.get("tool_response", {})
                }
                if msg.get("tool_call_id"):
                    func_obj["id"] = msg["tool_call_id"]
                    
                contents.append({
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": func_obj
                        }
                    ]
                })

        # Construct payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048
            }
        }

        # Add system instruction if provided
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Format tool declarations
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["parameters"]
                        } for tool in tools
                    ]
                }
            ]

        headers = {"Content-Type": "application/json"}

        # Make the request synchronously. No try-catch blocks here so HTTP status errors or timeouts
        # propagate to show raw errors.
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse output
        content_text = None
        tool_calls = None
        
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            content_part = candidate.get("content", {})
            parts = content_part.get("parts", [])
            
            for part in parts:
                if "text" in part:
                    content_text = (content_text or "") + part["text"]
                elif "functionCall" in part:
                    if tool_calls is None:
                        tool_calls = []
                    fc = part["functionCall"]
                    
                    tc_item = {
                        "name": fc.get("name"),
                        "args": fc.get("args")
                    }
                    if fc.get("id"):
                        tc_item["id"] = fc.get("id")
                    if part.get("thoughtSignature"):
                        tc_item["thoughtSignature"] = part.get("thoughtSignature")
                        
                    tool_calls.append(tc_item)
                    
        return content_text, tool_calls, data
