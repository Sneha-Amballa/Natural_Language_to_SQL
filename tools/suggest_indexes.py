"""Suggest Indexes Agent Tool.

Highlights search performance indices candidates definitions.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

import sqlglot
from sqlglot import exp
from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager
from core.security import SecurityValidator
from config import settings

class SuggestIndexesTool(BaseTool):
    """Provides database search optimization tips."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "suggest_indexes"
        
    @property
    def description(self) -> str:
        return "Suggest indices to resolve bottlenecks in generated SQL execution planning."
        
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
        """Analyzes filter keys mapping schemas."""
        sql = kwargs.get("sql", "")
        if not sql:
            return ToolResponse(
                is_success=False,
                result_content="Error: No SQL query provided.",
                error_message="No SQL query provided."
            )
            
        try:
            SecurityValidator.is_safe_statement(sql)
            
            # Fetch EXPLAIN QUERY PLAN
            explain_sql = f"EXPLAIN QUERY PLAN {sql}"
            query_result = self.db_manager.execute_raw(explain_sql, timeout=settings.SQL_TIMEOUT_SEC)
            
            import re
            # Find scanned tables in the explain plan
            scanned_tables = []
            for row in query_result.rows:
                detail = ""
                for val in row:
                    if isinstance(val, str) and "SCAN" in val.upper():
                        detail = val
                        break
                if detail:
                    match = re.search(r"SCAN(?: TABLE)? (\w+)", detail, re.IGNORECASE)
                    if match:
                        table_name = match.group(1).strip('"`[]')
                        scanned_tables.append(table_name)

            
            # Parse columns in WHERE/JOIN clauses
            parsed = sqlglot.parse_one(sql, read="sqlite")
            table_column_map = {}
            
            for clause in parsed.find_all((exp.Where, exp.Join, exp.Group, exp.Order)):
                for col in clause.find_all(exp.Column):
                    col_name = col.name
                    tbl_name = col.table
                    if tbl_name:
                        table_column_map.setdefault(tbl_name, set()).add(col_name)
                    else:
                        for tbl in scanned_tables:
                            try:
                                meta = self.db_manager.get_schema_metadata(tbl)
                                tbl_cols = [c["name"] for c in meta["columns"]]
                                if col_name in tbl_cols:
                                    table_column_map.setdefault(tbl, set()).add(col_name)
                            except Exception:
                                pass
                                
            suggested_indexes = []
            for table in set(scanned_tables):
                cols = list(table_column_map.get(table, []))
                if cols:
                    try:
                        meta = self.db_manager.get_schema_metadata(table)
                        pks = meta.get("primary_keys", [])
                        cols = [c for c in cols if c not in pks]
                    except Exception:
                        pass
                        
                for col in cols:
                    suggested_indexes.append({
                        "table": table,
                        "columns": [col],
                        "ddl": f'CREATE INDEX "idx_{table}_{col}" ON "{table}"("{col}");',
                        "benefit_reason": f"Removes SCAN TABLE on table '{table}' in favor of index lookups on column '{col}'.",
                        "estimated_improvement": "Reduces query complexity from O(N) full table scan to O(log N) binary index lookup."
                    })

                    
            return ToolResponse(
                is_success=True,
                result_content=str(suggested_indexes)
            )
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Failed to suggest indexes: {e}",
                error_message=str(e)
            )

