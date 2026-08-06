"""Find Column Values Agent Tool.

Provides unique categorical indexing checks.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from config import settings

class FindColumnValuesTool(BaseTool):
    """Resolves column filter query options."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "find_column_values"
        
    @property
    def description(self) -> str:
        return "Search distinct column attributes to align SQL filters query configurations."
        
    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "column": {"type": "string"},
                "search_term": {"type": "string"},
                "search_type": {"type": "string", "enum": ["like", "exact", "distinct"]},
                "limit": {"type": "integer"}
            },
            "required": ["table", "column"]
        }
        
    def execute(self, **kwargs) -> ToolResponse:
        """Runs SELECT DISTINCT configurations."""
        table = kwargs.get("table", "")
        column = kwargs.get("column", "")
        search_term = kwargs.get("search_term", "")
        search_type = kwargs.get("search_type", "like").lower().strip()
        limit = kwargs.get("limit", 20)
        
        if not table or not column:
            return ToolResponse(
                is_success=False,
                result_content="Error: Table and column name must be provided.",
                error_message="Table and column name must be provided."
            )
            
        try:
            tables = self.db_manager.get_table_list()
            if table not in tables:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Table '{table}' does not exist.",
                    error_message=f"Table '{table}' does not exist."
                )
                
            meta = self.db_manager.get_schema_metadata(table)
            columns = [c["name"] for c in meta["columns"]]
            if column not in columns:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Column '{column}' does not exist on table '{table}'.",
                    error_message=f"Column '{column}' does not exist."
                )
                
            escaped_term = search_term.replace("'", "''")
            if search_term:
                if search_type == "exact":
                    sql = f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" = \'{escaped_term}\' LIMIT {int(limit)};'
                else:  # like
                    sql = f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" LIKE \'%{escaped_term}%\' LIMIT {int(limit)};'
            else:
                sql = f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL LIMIT {int(limit)};'
                
            query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
            distinct_values = [row[0] for row in query_result.rows]
            
            return ToolResponse(
                is_success=True,
                result_content=str(distinct_values)
            )

        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to find column values: {e}",
                error_message=str(e)
            )

