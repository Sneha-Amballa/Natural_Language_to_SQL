"""Explain Query Agent Tool.

Returns execution pipeline paths contexts analysis data.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from core.security import SecurityValidator
from config import settings

class ExplainQueryTool(BaseTool):
    """Exposes EXPLAIN query operations plans."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "explain_query"
        
    @property
    def description(self) -> str:
        return "Fetches SQLite execution steps details for performance verification."
        
    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sql": {"type": "string"}
            },
            "required": ["sql"]
        }
        
    def execute(self, **kwargs) -> ToolResponse:
        """Runs EXPLAIN SQLite command statements."""
        sql = kwargs.get("sql", "")
        if not sql:
            return ToolResponse(
                is_success=False,
                result_content="Error: No SQL query provided.",
                error_message="No SQL query provided."
            )
            
        try:
            # First validate statement safety
            SecurityValidator.is_safe_statement(sql)
            
            # Execute EXPLAIN QUERY PLAN
            explain_sql = f"EXPLAIN QUERY PLAN {sql}"
            query_result = self.db_manager.execute_raw(explain_sql, timeout=settings.SQL_TIMEOUT_SEC)
            
            import re
            plan_lines = []
            # Find the index of the "detail" column
            detail_idx = 3
            if "detail" in query_result.columns:
                detail_idx = query_result.columns.index("detail")
                
            for row in query_result.rows:
                if len(row) > detail_idx:
                    plan_lines.append(str(row[detail_idx]))
                    
            explanations = []
            for line in plan_lines:
                line_upper = line.upper()
                if "SCAN TABLE" in line_upper:
                    table_match = re.search(r"SCAN TABLE (\w+)", line, re.IGNORECASE)
                    table_name = table_match.group(1) if table_match else "table"
                    explanations.append(f"• Performs a full table scan on '{table_name}' (reads every row; inefficient for large datasets).")
                elif "SEARCH TABLE" in line_upper:
                    table_match = re.search(r"SEARCH TABLE (\w+)", line, re.IGNORECASE)
                    table_name = table_match.group(1) if table_match else "table"
                    using_match = re.search(r"USING (.*)", line, re.IGNORECASE)
                    using_info = using_match.group(1) if using_match else "an index"
                    explanations.append(f"• Searches table '{table_name}' using indexing: {using_info} (efficient search).")
                elif "USE TEMP B-TREE FOR ORDER BY" in line_upper:
                    explanations.append("• Sorts final results using a temporary B-tree (might be slow; index could optimize sorting).")
                elif "USE TEMP B-TREE FOR GROUP BY" in line_upper:
                    explanations.append("• Groups results using a temporary B-tree.")
                elif "CORRELATED" in line_upper:
                    explanations.append("• Executes a correlated nested loop subquery (potentially slow).")
                else:
                    explanations.append(f"• {line}")
                    
            if not explanations:
                explanations.append("• No explanation details returned from database engine.")
                
            plain_english = "Query Execution Steps:\n" + "\n".join(explanations)
            
            return ToolResponse(
                is_success=True,
                result_content=plain_english
            )

        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to explain query plan: {e}",
                error_message=str(e)
            )

