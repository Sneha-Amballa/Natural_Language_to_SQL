import re
from typing import List

class QueryPlanner:
    """Classifies user questions and plans required tools for SQL generation."""
    
    @staticmethod
    def classify_question(question: str) -> str:
        """Categorizes the natural language question.
        
        Possible categories: Aggregation, Filtering, Join, Ranking, Trend, Comparison, Schema lookup.
        """
        q_upper = question.upper()
        
        def has_word(word: str) -> bool:
            # handle multi-word phrases by replacing space with regex whitespace
            pattern = rf"\b{re.escape(word)}\b"
            return bool(re.search(pattern, q_upper, re.IGNORECASE))
            
        if any(has_word(w) for w in ["COUNT", "SUM", "AVG", "AVERAGE", "MAX", "MIN", "TOTAL", "HOW MANY", "NUMBER OF", "QUANTITY", "MAXIMUM", "MINIMUM"]):
            return "Aggregation"
        if any(has_word(w) for w in ["JOIN", "COMBINE", "RELATE", "TOGETHER", "CUSTOMER AND SALES", "PRODUCT AND SALES"]):
            return "Join"
        if any(has_word(w) for w in ["ORDER BY", "ORDERED", "SORT", "TOP", "BEST", "WORST", "RANK", "LIMIT"]):
            return "Ranking"
        if any(has_word(w) for w in ["TREND", "MONTH", "YEAR", "DATE", "OVER TIME", "DAILY", "WEEKLY"]):
            return "Trend"
        if any(has_word(w) for w in ["COMPARE", "VS", "VERSUS", "DIFFERENCE", "MORE THAN", "LESS THAN"]):
            return "Comparison"
        if any(has_word(w) for w in ["SCHEMA", "TABLE", "COLUMNS", "DESCRIBE", "WHAT IS", "SAMPLE", "RECORD", "ROWS", "PREVIEW", "EXAMPLE"]):
            return "Schema lookup"

            
        return "Filtering"  # Default safe category
        
    @staticmethod
    def plan_tools(category: str) -> List[str]:
        """Determines required tools based on query classification."""
        tools = ["list_tables", "get_schema", "run_query"]
        
        if category == "Schema lookup":
            return ["list_tables", "get_schema", "get_sample_rows"]
            
        # For query generation categories, expose find_column_values and get_sample_rows
        tools.extend(["find_column_values", "get_sample_rows"])
        
        if category in ("Aggregation", "Join", "Ranking", "Comparison", "Trend"):
            tools.extend(["explain_query", "suggest_indexes"])
            
        if category == "Aggregation":
            tools.extend(["count_rows", "get_column_stats"])
            
        return tools
