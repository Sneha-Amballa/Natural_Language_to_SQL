from typing import List, Dict, Any
from models.models import ChatMessage

def serialize_conversation_history(history: List[ChatMessage]) -> List[Dict[str, Any]]:
    """Converts structured ChatMessage list to JSON objects sequence."""
    serialized = []
    for msg in history:
        msg_dict = {"role": msg.role, "content": msg.content}
        if msg.tool_call_id:
            msg_dict["tool_call_id"] = msg.tool_call_id
        serialized.append(msg_dict)
    return serialized

class ConversationManager:
    """Manages conversational history, prompts load, and sliding window boundaries."""
    
    def __init__(self, system_prompt: str, max_history: int = 20):
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.history: List[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt)
        ]
        
    def add_user_message(self, content: str) -> None:
        self.history.append(ChatMessage(role="user", content=content))
        self._prune()
        
    def add_assistant_message(self, content: str, tool_call_id: str = None) -> None:
        self.history.append(ChatMessage(role="assistant", content=content, tool_call_id=tool_call_id))
        self._prune()
        
    def add_tool_output(self, tool_call_id: str, content: str) -> None:
        self.history.append(ChatMessage(role="tool", content=content, tool_call_id=tool_call_id))
        self._prune()
        
    def _prune(self) -> None:
        # Keep system prompt at index 0 and slide the rest if history limit is exceeded
        if len(self.history) > self.max_history:
            self.history = [self.history[0]] + self.history[-(self.max_history - 1):]

