"""Validate SQL Agent Tool.

Exposes parsed structures checking queries validity.
"""

from tools.base_tool import BaseTool
from models.models import ToolResponse

import sqlglot
from sqlglot import exp
from tools.base_tool import BaseTool
from models.models import ToolResponse
from core.database import DatabaseManager

class ValidateSqlTool(BaseTool):
    """Validates SQL queries configurations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        
    @property
    def name(self) -> str:
        return "validate_sql"
        
    @property
    def description(self) -> str:
        return "Checks syntax and structure validation on generated SQL string."
        
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
        """Compiles execution trees and validates syntax, tables, and columns."""
        sql = kwargs.get("sql", "")
        if not sql:
            return ToolResponse(
                is_success=False,
                result_content="Error: No SQL query provided.",
                error_message="No SQL query provided."
            )
            
        try:
            parsed = sqlglot.parse(sql, read="sqlite")
            if not parsed:
                return ToolResponse(
                    is_success=False,
                    result_content="Error: Failed to parse SQL statement syntax.",
                    error_message="Failed to parse SQL statement syntax."
                )
                
            db_tables = self.db_manager.get_table_list()
            db_tables_lower = {t.lower(): t for t in db_tables}
            
            tables_referenced = []
            columns_referenced = []
            
            for expression in parsed:
                if not expression:
                    continue
                for node in expression.walk():
                    if isinstance(node, exp.Table):
                        tables_referenced.append(node.name)
                    elif isinstance(node, exp.Column):
                        columns_referenced.append((node.table, node.name))
                        
            tables_referenced = list(set(t.lower() for t in tables_referenced if t))
            invalid_tables = [t for t in tables_referenced if t not in db_tables_lower]
            
            if invalid_tables:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Table(s) {invalid_tables} do not exist in database. Available tables: {db_tables}",
                    error_message=f"Missing tables: {invalid_tables}"
                )
                
            # Load columns schemas
            table_columns = {}
            for t_ref in tables_referenced:
                actual_name = db_tables_lower[t_ref]
                meta = self.db_manager.get_schema_metadata(actual_name)
                table_columns[t_ref] = [col["name"].lower() for col in meta["columns"]]
                
            # Build alias mapping
            alias_map = {}
            for t_ref in tables_referenced:
                alias_map[t_ref] = t_ref
                
            for expression in parsed:
                if not expression:
                    continue
                for node in expression.walk():
                    if isinstance(node, exp.Table):
                        tbl_name = node.name.lower()
                        alias = node.alias
                        if alias:
                            alias_map[alias.lower()] = tbl_name
                            
            invalid_columns = []
            for t_name, c_name in columns_referenced:
                c_lower = c_name.lower()
                if t_name:
                    t_lower = t_name.lower()
                    if t_lower in alias_map:
                        actual_tbl = alias_map[t_lower]
                        if c_lower not in table_columns.get(actual_tbl, []):
                            invalid_columns.append(f"{t_name}.{c_name}")
                    else:
                        # Invalid table alias / reference
                        invalid_columns.append(f"{t_name}.{c_name}")
                else:
                    found = False
                    for t_lower, cols in table_columns.items():
                        if c_lower in cols:
                            found = True
                            break
                    if not found and tables_referenced:
                        invalid_columns.append(c_name)
                        
            if invalid_columns:
                return ToolResponse(
                    is_success=False,
                    result_content=f"Error: Column(s) {invalid_columns} do not exist in referenced table(s).",
                    error_message=f"Missing columns: {invalid_columns}"
                )
                
            # Allowed SQL check
            from core.security import SecurityValidator
            if not SecurityValidator.validate_sql_ast(sql):
                return ToolResponse(
                    is_success=False,
                    result_content="Error: Query contains blocked operations (only SELECT, WITH, and EXPLAIN queries are permitted).",
                    error_message="Safety block on non-read statement"
                )
                
            return ToolResponse(
                is_success=True,
                result_content=f"SQL query is valid. References tables: {tables_referenced}."
            )

        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"SQL validation failed: {e}",
                error_message=str(e)
            )

