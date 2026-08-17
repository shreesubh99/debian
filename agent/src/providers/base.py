from typing import List, Dict, Any, Tuple, Optional

class AIProvider:
    """
    Abstract Base Class for all AI model providers.
    All providers must implement generate_response.
    """
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        timeout: float = 10.0
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Sends the chat messages to the LLM model and returns the response.
        
        Args:
            messages: List of standardized messages:
                      [
                         {"role": "user" | "assistant" | "tool", "content": "text", "tool_name": "name", "tool_response": {}}, ...
                      ]
            tools: List of standardized tool declarations.
            system_instruction: System prompt.
            timeout: Timeout in seconds for the HTTP call.
            
        Returns:
            Tuple of:
              - content: Optional text response from model.
              - tool_calls: Optional list of tool calls requested by model (e.g. [{"name": "func_name", "args": {...}}]).
              - raw_response: Dict containing the raw response payload for debugging.
        """
        raise NotImplementedError("This method must be implemented by the subclass.")
