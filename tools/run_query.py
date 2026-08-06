"""Run Query Agent Tool.

Safely fetches query responses with size limitations.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from core.security import SecurityValidator
from config import settings

class RunQueryTool(BaseTool):
    """Runs analytical SQL execution structures."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "run_query"
        
    @property
    def description(self) -> str:
        return "Safely execute read-only queries with timeouts limits configurations."
        
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
        """Queries database connection pool context."""
        sql = kwargs.get("sql", "")
        if not sql:
            return ToolResponse(
                is_success=False,
                result_content="Error: No SQL query provided.",
                error_message="No SQL query provided."
            )
            
        try:
            # 1. Chained Sanitization check
            from tools.sanitize_sql import SanitizeSqlTool
            sanitizer = SanitizeSqlTool(self.db_path)
            sanitize_res = sanitizer.execute(sql=sql)
            if not sanitize_res.is_success:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Sanitization Blocked: {sanitize_res.result_content}",
                    error_message=sanitize_res.error_message
                )
                
            # 2. Chained Validation check
            from tools.validate_sql import ValidateSqlTool
            validator = ValidateSqlTool(self.db_path)
            validate_res = validator.execute(sql=sql)
            if not validate_res.is_success:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Validation Failed: {validate_res.result_content}",
                    error_message=validate_res.error_message
                )
                
            # 3. Database execution
            import json
            query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
            
            # Limit rows inside LLM context to prevent token overflow
            max_rows = settings.MAX_QUERY_ROWS
            original_row_count = query_result.row_count
            if query_result.row_count > max_rows:
                query_result.rows = query_result.rows[:max_rows]
                query_result.row_count = max_rows
                
            response_payload = {
                "columns": query_result.columns,
                "rows": query_result.rows,
                "row_count": query_result.row_count,
                "total_db_rows": original_row_count,
                "execution_time_ms": query_result.execution_time_ms,
                "metadata": {
                    "sql": sql,
                    "truncated": original_row_count > max_rows
                }
            }
            
            return ToolResponse(
                is_success=True,
                result_content=json.dumps(response_payload)
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Error executing SQL query: {e}",
                error_message=str(e)
            )


