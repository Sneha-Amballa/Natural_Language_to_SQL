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
        self.api_key = settings.GROQ_API_KEY.get_secret_value()
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

