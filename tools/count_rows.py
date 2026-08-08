"""Count Rows Agent Tool.

Returns the row count for the specified table.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from config import settings

class CountRowsTool(BaseTool):
    """Returns row counts from specified table."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "count_rows"
        
    @property
    def description(self) -> str:
        return (
            "Count the number of rows in a database table.\n\n"
            "Required argument:\n"
            "    table_name\n\n"
            "table_name must be the exact table name returned by list_tables.\n"
            "Example:\n"
            "    count_rows({\"table_name\": \"student_performance_dataset\"})"
        )
        
    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Exact table name."}
            },
            "required": ["table_name"]
        }
        
    def validate(self, **kwargs):
        from tools.tool_models import ValidationResult
        if "table_name" not in kwargs:
            return ValidationResult(is_valid=False, errors=["Missing required field 'table_name'"])
        return ValidationResult(is_valid=True, errors=[])
        
    def execute(self, **kwargs) -> ToolResponse:
        """Executes SELECT COUNT(*) commands."""
        table_name = kwargs.get("table_name", "").strip()
        if not table_name:
            return ToolResponse(
                is_success=False,
                result_content="Error: Table name must be provided.",
                error_message="Table name must be provided."
            )
            
        try:
            tables = self.db_manager.get_table_list()
            if table_name not in tables:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Table '{table_name}' does not exist.",
                    error_message=f"Table '{table_name}' does not exist."
                )
                
            sql = f'SELECT COUNT(*) FROM "{table_name}";'
            query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
            row_count = query_result.rows[0][0]
            
            return ToolResponse(
                is_success=True,
                result_content=str(row_count)
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to count rows: {e}",
                error_message=str(e)
            )
