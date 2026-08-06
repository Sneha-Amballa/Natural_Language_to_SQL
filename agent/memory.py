"""Conversation Memory Manager.

Manages conversational state contexts, token length evaluations,
and rolling message cache truncations.
"""

from typing import List, Dict, Any

import tiktoken
from typing import List, Dict, Any

class ConversationMemoryManager:
    """Stateful short-term memory management module."""
    
    def __init__(self, max_token_limit: int = 6000):
        """Initializes memory parameters."""
        self.messages: List[Dict[str, Any]] = []
        self.max_token_limit = max_token_limit
        
    def add_message(self, role: str, content: str, name: str = None) -> None:
        """Appends a raw chat event to history."""
        msg = {"role": role, "content": content}
        if name:
            msg["name"] = name
        self.messages.append(msg)
        self._prune_history()
        
    def get_history_within_tokens(self) -> List[Dict[str, Any]]:
        """Returns the token-budget truncated conversational logs."""
        self._prune_history()
        return self.messages
        
    def _count_tokens(self, message: Dict[str, Any]) -> int:
        """Measures message size."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Simple fallback: 1 token approx 4 chars
            return len(str(message.get("content", ""))) // 4 + 4
        
        content = message.get("content") or ""
        role = message.get("role") or ""
        name = message.get("name") or ""
        
        tokens = len(encoding.encode(content)) + len(encoding.encode(role))
        if name:
            tokens += len(encoding.encode(name))
        return tokens
        
    def _prune_history(self) -> None:
        """Ejects oldest prunable messages from state index to stay within limits."""
        total_tokens = sum(self._count_tokens(m) for m in self.messages)
        if total_tokens <= self.max_token_limit:
            return
            
        # We need to eject prunable messages.
        # Protected messages:
        # - Any system messages (role == "system")
        # - The very first user message (role == "user"), which is the original prompt.
        # We find the first prunable message, eject it, and recount.
        
        # Let's identify the index of system messages and the first user query.
        first_user_idx = -1
        for i, msg in enumerate(self.messages):
            if msg.get("role") == "user":
                first_user_idx = i
                break
                
        while total_tokens > self.max_token_limit:
            prune_idx = -1
            # Search for the oldest prunable message
            for i in range(len(self.messages)):
                msg = self.messages[i]
                if msg.get("role") == "system":
                    continue
                if i == first_user_idx:
                    continue
                # If we get here, this message is prunable
                prune_idx = i
                break
                
            if prune_idx != -1:
                removed = self.messages.pop(prune_idx)
                # Recalculate first user index since list changed
                first_user_idx = -1
                for i, m in enumerate(self.messages):
                    if m.get("role") == "user":
                        first_user_idx = i
                        break
                total_tokens -= self._count_tokens(removed)
            else:
                # No more prunable messages, must stop to avoid deleting core system/goal
                break

