"""Visualization Recommendation Service.

Evaluates dataset attributes dynamically suggesting appropriate charts templates.
"""

import pandas as pd
from models.models import VisualizationRecommendation

import pandas as pd
from typing import Dict, Any
from models.models import VisualizationRecommendation

class VisualizationService:
    """Recommends visual charting strategies mappings."""
    
    def get_recommendation(self, df: pd.DataFrame) -> VisualizationRecommendation:
        """Exposes visual metrics properties."""
        if df.empty or len(df.columns) < 2:
            return VisualizationRecommendation(
                should_render=False,
                chart_type="none",
                x_axis="",
                y_axis="",
                vega_lite_spec={}
            )
            
        numeric_cols = []
        datetime_cols = []
        categorical_cols = []
        
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_numeric_dtype(dtype):
                # Ensure it's not all nulls
                if not df[col].isnull().all():
                    numeric_cols.append(col)
            elif pd.api.types.is_datetime64_any_dtype(dtype) or "date" in col.lower() or "time" in col.lower():
                datetime_cols.append(col)
            else:
                categorical_cols.append(col)
                
        # Apply rule-based heuristics
        if datetime_cols and numeric_cols:
            x_col = datetime_cols[0]
            y_col = numeric_cols[0]
            chart_type = "line"
        elif categorical_cols and numeric_cols:
            x_col = categorical_cols[0]
            y_col = numeric_cols[0]
            chart_type = "bar"
        elif len(numeric_cols) >= 2:
            x_col = numeric_cols[0]
            y_col = numeric_cols[1]
            chart_type = "scatter"
        elif numeric_cols:
            x_col = df.columns[0]
            y_col = numeric_cols[0]
            chart_type = "bar"
        else:
            x_col = df.columns[0]
            y_col = df.columns[1]
            chart_type = "bar"
            
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "description": f"Recommended {chart_type} chart.",
            "mark": "bar" if chart_type == "bar" else ("line" if chart_type == "line" else "point"),
            "encoding": {
                "x": {"field": x_col, "type": "temporal" if chart_type == "line" else "nominal"},
                "y": {"field": y_col, "type": "quantitative"}
            }
        }
        
        return VisualizationRecommendation(
            should_render=True,
            chart_type=chart_type,
            x_axis=x_col,
            y_axis=y_col,
            vega_lite_spec=spec
        )
        
    def should_show_chart(self, df: pd.DataFrame, query: str) -> bool:
        """Determines if a chart should be rendered based on dataset shape and query context."""
        if df.empty or len(df) <= 1:
            return False
            
        q = query.lower()
        # Explicit chart requests
        explicit = any(word in q for word in ["plot", "chart", "graph", "visual", "distribution", "scatter", "histogram", "line", "bar", "relation", "trend"])
        if explicit:
            return True
            
        # Context-aware heuristics based on dataset shape and columns
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c].dtype)]
        
        # If dataset has multiple numeric columns, it could be a scatter plot relation
        # If it has a category/label column and a numeric column, it's a distribution
        if len(df.columns) >= 2 and len(numeric_cols) >= 1:
            return True
            
        return False

