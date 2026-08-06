"""List Tables Agent Tool.

Returns table names present in target database schema.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager

class ListTablesTool(BaseTool):
    """Queries metadata schema mapping table lists."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "list_tables"
        
    @property
    def description(self) -> str:
        return "Returns list of all table names inside the active database."
        
    @property
    def schema(self) -> dict:
        return {}
        
    def execute(self, **kwargs) -> ToolResponse:
        """Runs sqlite system catalog execution lookup."""
        try:
            tables = self.db_manager.get_table_list()
            result_data = {}
            for table in tables:
                count_res = self.db_manager.execute_raw(f"SELECT COUNT(*) FROM `{table}`;")
                row_count = count_res.rows[0][0] if count_res.rows else 0
                result_data[table] = {
                    "row_count": row_count,
                    "description": "None available"
                }
            return ToolResponse(
                is_success=True,
                result_content=str(result_data)
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to retrieve tables list: {e}",
                error_message=str(e)
            )


