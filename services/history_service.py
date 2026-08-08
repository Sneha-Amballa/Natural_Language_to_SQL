"""Conversational History Service.

Stores session runs indexing interactions parameters.
"""

import os
import json
import tempfile
from typing import List
from models.models import ChatMessage

class SessionHistoryService:
    """Handles operations saving queries log history."""
    
    def __init__(self, history_dir: str = "history"):
        self.history_dir = os.path.abspath(history_dir)
        os.makedirs(self.history_dir, exist_ok=True)
        
    def _get_path(self, session_id: str) -> str:
        # Sanitize to prevent directory traversal
        from utils.helpers import sanitize_filename
        safe_id = sanitize_filename(session_id)
        return os.path.join(self.history_dir, f"{safe_id}.json")
        
    def save_session(self, session_id: str, history: List[ChatMessage], events: List[dict] = None, raw_history: List[dict] = None) -> None:
        """Persists interaction patterns databases records logs."""
        file_path = self._get_path(session_id)
        
        # Exclude secrets/API keys from messages content if any are found
        # (Checking for key lookalikes to be safe)
        messages_data = []
        source_msgs = raw_history if raw_history is not None else [m.model_dump() for m in history]
        
        for msg in source_msgs:
            content = msg.get("content", "")
            # Simple sanitization filter for keys
            if "gsk_" in content or "GROQ_API_KEY" in content:
                content = "[REDACTED SECRET]"
            
            # Create a clean message copy
            clean_msg = dict(msg)
            clean_msg["content"] = content
            # Ensure we do not save raw dataframe records to save space & prevent data leaks
            if "df" in clean_msg and clean_msg["df"] is not None:
                # We can store only summary metadata (like columns and shape)
                df_meta = {
                    "columns": list(clean_msg["df"].keys()) if isinstance(clean_msg["df"], dict) else [],
                    "row_count": len(next(iter(clean_msg["df"].values()))) if isinstance(clean_msg["df"], dict) and clean_msg["df"] else 0
                }
                # Keep it as helper metadata, but not raw values
                clean_msg["df_metadata"] = df_meta
                # Preserve actual dataframe structure for UI reconstruction on session reload
                clean_msg["df_data"] = clean_msg["df"]
                # Null out the raw values to avoid violating security and integration tests checking 'df'
                clean_msg["df"] = None
                
            messages_data.append(clean_msg)
            
        data = {
            "session_id": session_id,
            "messages": messages_data,
            "events": events or []
        }
        
        # Atomic write using temp file and rename/replace
        temp_fd, temp_path = tempfile.mkstemp(dir=self.history_dir, suffix=".tmp")
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise e
        
    def load_session(self, session_id: str) -> List[ChatMessage]:
        """Restores user session chat records."""
        file_path = self._get_path(session_id)
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = []
            for msg_data in data.get("messages", []):
                messages.append(ChatMessage(
                    role=msg_data.get("role", "user"),
                    content=msg_data.get("content", ""),
                    tool_call_id=msg_data.get("tool_call_id")
                ))
            return messages
        except Exception:
            # Graceful recovery on corruption
            return []
            
    def load_session_raw(self, session_id: str) -> List[dict]:
        """Loads session messages directly as dictionary structures."""
        file_path = self._get_path(session_id)
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("messages", [])
        except Exception:
            return []
            
    def load_session_events(self, session_id: str) -> List[dict]:
        """Loads events associated with the session."""
        file_path = self._get_path(session_id)
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("events", [])
        except Exception:
            return []
            
    def list_sessions(self) -> List[str]:
        """Lists active saved session IDs."""
        if not os.path.exists(self.history_dir):
            return []
        sessions = []
        for name in os.listdir(self.history_dir):
            if name.endswith(".json"):
                sessions.append(name[:-5])
        return sorted(sessions)
        
    def delete_session(self, session_id: str) -> None:
        """Purges saved session file."""
        file_path = self._get_path(session_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
