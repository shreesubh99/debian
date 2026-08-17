import threading
from typing import List, Dict, Any

class SessionMemory:
    """
    Thread-safe in-memory manager for session chat history and metadata context.
    """
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _ensure_session(self, session_id: str):
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "history": [],
                "context": {}
            }

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            self._ensure_session(session_id)
            # Return a copy of the message history to prevent mutation outside lock
            return list(self._sessions[session_id]["history"])

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str = "",
        tool_calls: List[Dict[str, Any]] = None,
        tool_name: str = None,
        tool_response: Any = None,
        tool_call_id: str = None
    ):
        with self._lock:
            self._ensure_session(session_id)
            msg = {
                "role": role,
                "content": content
            }
            if tool_calls is not None:
                msg["tool_calls"] = tool_calls
            if tool_name is not None:
                msg["tool_name"] = tool_name
            if tool_response is not None:
                msg["tool_response"] = tool_response
            if tool_call_id is not None:
                msg["tool_call_id"] = tool_call_id
                
            self._sessions[session_id]["history"].append(msg)

    def get_context(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            self._ensure_session(session_id)
            return dict(self._sessions[session_id]["context"])

    def update_context(self, session_id: str, key: str, value: Any):
        with self._lock:
            self._ensure_session(session_id)
            self._sessions[session_id]["context"][key] = value

    def clear_session(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_all_sessions(self) -> List[str]:
        with self._lock:
            return list(self._sessions.keys())

# Global memory instance
memory = SessionMemory()
