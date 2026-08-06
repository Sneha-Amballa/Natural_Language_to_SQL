"""Sanitize SQL Agent Tool.

Blocks query commands modifications (write filters protection).
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.security import SecurityValidator

class SanitizeSqlTool(BaseTool):
    """AST analysis sandbox filter execution tool."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    @property
    def name(self) -> str:
        return "sanitize_sql"
        
    @property
    def description(self) -> str:
        return "Sanitizes generated SQL statements preventing mutation commands."
        
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
        """Sanitizes statement nodes."""
        sql = kwargs.get("sql", "")
        if not sql:
            return ToolResponse(
                is_success=False,
                result_content="Error: No SQL query provided.",
                error_message="No SQL query provided."
            )
            
        try:
            is_safe = SecurityValidator.validate_sql_ast(sql)
            if not is_safe:
                return ToolResponse(
                    is_success=False,
                    result_content="Error: SQL statement contains blocked/unsafe operations. Only SELECT queries are permitted.",
                    error_message="Query is unsafe."
                )
            return ToolResponse(
                is_success=True,
                result_content=f"SQL statement is sanitized and safe: {sql}"
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"SQL sanitization check failed: {e}",
                error_message=str(e)
            )

