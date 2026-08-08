"""Get Column Stats Agent Tool.

Safely retrieves min, max, avg, null count, and unique count for a target column.
"""

import json
from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from config import settings

class GetColumnStatsTool(BaseTool):
    """Safely retrieves column statistics."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "get_column_stats"
        
    @property
    def description(self) -> str:
        return "Returns statistics (min, max, average, null_count, unique_count) for a specific column in a table."
        
    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "The name of the table."},
                "col": {"type": "string", "description": "The name of the column."}
            },
            "required": ["table", "col"]
        }
        
    def execute(self, **kwargs) -> ToolResponse:
        """Executes aggregate select statements on the target column."""
        table = kwargs.get("table", "").strip()
        col = kwargs.get("col", "").strip()
        
        if not table or not col:
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
            columns = {c["name"].lower(): c for c in meta["columns"]}
            if col.lower() not in columns:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Column '{col}' does not exist on table '{table}'.",
                    error_message=f"Column '{col}' does not exist."
                )
                
            # Get actual column name and type (retaining exact case from meta)
            actual_col = next(c["name"] for c in meta["columns"] if c["name"].lower() == col.lower())
            col_type = columns[col.lower()]["type"].upper()
            
            # Identify data types
            is_numeric = any(t in col_type for t in ["INT", "REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"])
            is_datetime = any(t in col_type for t in ["DATE", "TIME", "TIMESTAMP"])
            
            # Check row count first to handle empty table cases cleanly
            sql_count = f'SELECT COUNT(*) FROM "{table}";'
            cnt_res = self.db_manager.execute_raw(sql_count, timeout=settings.SQL_TIMEOUT_SEC)
            row_count = cnt_res.rows[0][0]
            
            if row_count == 0:
                stats = {
                    "null_count": 0,
                    "unique_count": 0
                }
                if is_numeric:
                    stats.update({"min": None, "max": None, "average": None})
                elif is_datetime:
                    stats.update({"min": None, "max": None})
                else:
                    stats.update({"min": None, "max": None})
                return ToolResponse(
                    is_success=True,
                    result_content=json.dumps(stats, indent=2, default=str)
                )
                
            if is_numeric:
                sql = f'SELECT MIN("{actual_col}"), MAX("{actual_col}"), AVG("{actual_col}"), SUM(CASE WHEN "{actual_col}" IS NULL THEN 1 ELSE 0 END), COUNT(DISTINCT "{actual_col}") FROM "{table}";'
                query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
                row = query_result.rows[0]
                stats = {
                    "min": row[0],
                    "max": row[1],
                    "average": row[2],
                    "null_count": row[3] if row[3] is not None else 0,
                    "unique_count": row[4]
                }
            elif is_datetime:
                sql = f'SELECT MIN("{actual_col}"), MAX("{actual_col}"), SUM(CASE WHEN "{actual_col}" IS NULL THEN 1 ELSE 0 END), COUNT(DISTINCT "{actual_col}") FROM "{table}";'
                query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
                row = query_result.rows[0]
                stats = {
                    "min": row[0],
                    "max": row[1],
                    "null_count": row[2] if row[2] is not None else 0,
                    "unique_count": row[3]
                }
            else:
                # Text/Blob/Other
                sql = f'SELECT MIN("{actual_col}"), MAX("{actual_col}"), SUM(CASE WHEN "{actual_col}" IS NULL THEN 1 ELSE 0 END), COUNT(DISTINCT "{actual_col}") FROM "{table}";'
                query_result = self.db_manager.execute_raw(sql, timeout=settings.SQL_TIMEOUT_SEC)
                row = query_result.rows[0]
                stats = {
                    "null_count": row[2] if row[2] is not None else 0,
                    "unique_count": row[3],
                    "min": row[0],
                    "max": row[1]
                }
                
            return ToolResponse(
                is_success=True,
                result_content=json.dumps(stats, indent=2, default=str)
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to get column stats: {e}",
                error_message=str(e)
            )
