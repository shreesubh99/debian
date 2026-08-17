import httpx
import json
from typing import List, Dict, Any, Tuple, Optional
from src.providers.base import AIProvider

class GroqProvider(AIProvider):
    """
    Implements the Groq API integration using OpenAI-compatible HTTP endpoints.
    Uses raw httpx calls to ensure timeout controls and clear error propagation.
    """
    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        timeout: float = 10.0
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        # Build message history for OpenAI schema
        oai_messages = []
        
        if system_instruction:
            oai_messages.append({
                "role": "system",
                "content": system_instruction
            })
            
        for msg in messages:
            role = msg.get("role")
            if role == "user":
                oai_messages.append({
                    "role": "user",
                    "content": msg.get("content", "")
                })
            elif role == "assistant":
                oai_msg = {
                    "role": "assistant",
                    "content": msg.get("content")
                }
                if msg.get("tool_calls"):
                    oai_msg["tool_calls"] = [
                        {
                            "id": f"call_{tc['name']}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"])
                            }
                        } for tc in msg["tool_calls"]
                    ]
                oai_messages.append(oai_msg)
            elif role == "tool":
                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{msg.get('tool_name')}",
                    "name": msg.get("tool_name"),
                    "content": json.dumps(msg.get("tool_response", {}))
                })

        # Format tools schema
        oai_tools = None
        if tools:
            oai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"]
                    }
                } for tool in tools
            ]

        # Construct request body
        payload = {
            "model": self.model_name,
            "messages": oai_messages,
            "temperature": 0.2
        }
        
        if oai_tools:
            payload["tools"] = oai_tools
            # We don't force tool choice unless required, let LLM decide (tool_choice="auto" is default)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Make request synchronously. Raise explicit RuntimeError with response body on failure.
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        
        # Parse OpenAI/Groq response
        content_text = None
        tool_calls = None
        
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            content_text = message.get("content")
            
            oai_tc_list = message.get("tool_calls")
            if oai_tc_list:
                tool_calls = []
                for oai_tc in oai_tc_list:
                    func = oai_tc.get("function", {})
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str)
                    except Exception:
                        args = {}
                    
                    tool_calls.append({
                        "name": func.get("name"),
                        "args": args
                    })
                    
        return content_text, tool_calls, data
