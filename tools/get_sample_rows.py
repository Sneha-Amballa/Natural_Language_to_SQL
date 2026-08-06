"""Get Sample Rows Agent Tool.

Fetches profiling records to confirm columns format constraints.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from config import settings

class GetSampleRowsTool(BaseTool):
    """Safely profiles sample rows."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "get_sample_rows"
        
    @property
    def description(self) -> str:
        return "Fetches sample rows from specified table."
        
    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "limit": {"type": "integer"},
                "method": {"type": "string", "enum": ["first", "random"]}
            },
            "required": ["table"]
        }
        
    def execute(self, **kwargs) -> ToolResponse:
        """Executes limited SELECT commands."""
        table = kwargs.get("table", "")
        limit = kwargs.get("limit", settings.SAMPLE_ROWS_LIMIT)
        method = kwargs.get("method", "first").lower().strip()
        if not table:
            return ToolResponse(
                is_success=False,
                result_content="Error: Table name must be provided.",
                error_message="Table name must be provided."
            )
            
        try:
            tables = self.db_manager.get_table_list()
            if table not in tables:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Table '{table}' does not exist.",
                    error_message=f"Table '{table}' does not exist."
                )
                
            order_clause = "ORDER BY RANDOM()" if method == "random" else ""
            sql = f'SELECT * FROM "{table}" {order_clause} LIMIT {int(limit)};'
            query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
            
            # Format results in readable Markdown table
            import pandas as pd
            from utils.formatter import ResultFormatter
            df = pd.DataFrame(query_result.rows, columns=query_result.columns)
            formatted_md = ResultFormatter.df_to_markdown(df)
            
            return ToolResponse(
                is_success=True,
                result_content=formatted_md
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to fetch sample rows: {e}",
                error_message=str(e)
            )


