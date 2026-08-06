"""Summary Service.

Constructs conversational analytical outputs from raw query result matrices.
"""

import pandas as pd
from models.models import SummaryResponse

import json
import pandas as pd
from models.models import SummaryResponse
from services.groq_service import GroqService

class SummaryService:
    """Generates business intelligence highlights summaries."""
    
    def summarize_results(self, df: pd.DataFrame, context_prompt: str) -> SummaryResponse:
        """Uses LLM to summarize key performance statistics metrics patterns."""
        if df.empty:
            return SummaryResponse(
                insights="No data available to summarize.",
                key_takeaways=["Empty dataset."]
            )
            
        # Limit rows to 50 to fit model context window comfortably
        df_str = df.head(50).to_string(index=False)
        
        prompt = (
            "You are a business intelligence assistant. Your task is to analyze the following dataset and generate a brief executive summary.\n\n"
            f"User query context: {context_prompt}\n\n"
            f"Dataset (top 50 rows):\n{df_str}\n\n"
            "Respond ONLY with a JSON object in this format:\n"
            '{\n  "insights": "A summary of key trends, anomalies, or insights from the dataset.",\n  "key_takeaways": ["Bullet point takeaway 1", "Bullet point takeaway 2"]\n}'
        )
        
        try:
            groq_service = GroqService()
            response = groq_service.generate_completion([{"role": "user", "content": prompt}])
            content = response.content or ""
            
            # Extract JSON block if returned inside markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content.strip())
            return SummaryResponse(
                insights=data.get("insights", "Insight summary generated successfully."),
                key_takeaways=data.get("key_takeaways", [])
            )
        except Exception as e:
            return SummaryResponse(
                insights=f"Summary failed to generate: {e}. Dataset contains {len(df)} rows and columns: {list(df.columns)}.",
                key_takeaways=[f"Rows count: {len(df)}", f"Columns: {', '.join(df.columns)}"]
            )

