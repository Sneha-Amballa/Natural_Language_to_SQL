"""Get Table Schema Agent Tool.

Exposes column fields, primary keys, and foreign keys references.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager

class GetSchemaTool(BaseTool):
    """Exposes target schemas to assist query generation."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "get_schema"
        
    @property
    def description(self) -> str:
        return "Returns schema information (columns, types, foreign keys) for table list."
        
    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tables": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["tables"]
        }
        
    def execute(self, **kwargs) -> ToolResponse:
        """Runs SQLite PRAGMA commands to inspect table metadata."""
        tables = kwargs.get("tables", [])
        if not tables:
            return ToolResponse(
                is_success=False,
                result_content="No tables provided.",
                error_message="No tables provided."
            )
            
        try:
            schema_data = {}
            conn = self.db_manager.get_connection(read_only=True)
            cursor = conn.cursor()
            try:
                for table in tables:
                    cursor.execute(f'PRAGMA table_info("{table}");')
                    cols_info = cursor.fetchall()
                    
                    cursor.execute(f'PRAGMA foreign_key_list("{table}");')
                    fkeys_info = cursor.fetchall()
                    
                    cursor.execute(f'PRAGMA index_list("{table}");')
                    idxs_info = cursor.fetchall()
                    
                    indexes = []
                    for idx in idxs_info:
                        idx_name = idx["name"]
                        cursor.execute(f'PRAGMA index_info("{idx_name}");')
                        idx_cols = cursor.fetchall()
                        indexes.append({
                            "name": idx_name,
                            "unique": bool(idx["unique"]),
                            "columns": [ic["name"] for ic in idx_cols]
                        })
                        
                    columns = []
                    primary_keys = []
                    for col in cols_info:
                        col_name = col["name"]
                        col_type = col["type"]
                        is_pk = bool(col["pk"])
                        is_nullable = not bool(col["notnull"])
                        if is_pk:
                            primary_keys.append(col_name)
                            
                        fkey_ref = None
                        for fk in fkeys_info:
                            if fk["from"] == col_name:
                                fkey_ref = {"table": fk["table"], "column": fk["to"]}
                                break
                                
                        columns.append({
                            "name": col_name,
                            "type": col_type,
                            "is_primary": is_pk,
                            "nullable": is_nullable,
                            "foreign_reference": fkey_ref
                        })
                        
                    schema_data[table] = {
                        "columns": columns,
                        "primary_keys": primary_keys,
                        "foreign_keys": [
                            {"from": fk["from"], "table": fk["table"], "to": fk["to"]}
                            for fk in fkeys_info
                        ],
                        "indexes": indexes
                    }
            finally:
                conn.close()
                
            return ToolResponse(
                is_success=True,
                result_content=str(schema_data)
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to retrieve schemas: {e}",
                error_message=str(e)
            )


