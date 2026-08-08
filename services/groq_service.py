"""Groq API Service.

Client wrapper handling API calls.
"""

from typing import List, Dict, Any
from config import settings

import groq
from typing import List, Dict, Any
from config import settings
from core.exceptions import LLMCallError

class GroqService:
    """Integrates with Groq platform API instances."""
    
    def __init__(self):
        api_key = None
        try:
            import streamlit as st
            api_key = st.session_state.get("groq_api_key")
        except Exception:
            pass
            
        if not api_key:
            import os
            api_key = os.environ.get("GROQ_API_KEY")
            
        if not api_key and settings.GROQ_API_KEY:
            api_key = settings.GROQ_API_KEY.get_secret_value()
            
        if not api_key:
            raise ValueError("Groq API key is missing.")
            
        self.api_key = api_key
        self.client = groq.Groq(api_key=self.api_key)
        
    def generate_completion(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Any:
        """Runs completions executions checking fallback connection properties."""
        model = settings.LLM_MODEL
        temperature = settings.TEMPERATURE
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            kwargs["tools"] = tools
            
        try:
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as e:
            raise LLMCallError(f"Groq API call failed: {e}") from e

