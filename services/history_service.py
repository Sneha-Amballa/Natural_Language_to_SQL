"""Conversational History Service.

Stores session runs indexing interactions parameters.
"""

from typing import List
from models.models import ChatMessage

class SessionHistoryService:
    """Handles operations saving queries log history."""
    
    def save_session(self, session_id: str, history: List[ChatMessage]) -> None:
        """Persists interaction patterns databases records logs."""
        pass
        
    def load_session(self, session_id: str) -> List[ChatMessage]:
        """Restores user session chat records."""
        pass
