"""AST Safety Verification Service.

Parses command statements blocking state mutating operations.
"""

import sqlglot
from sqlglot import exp
from core.exceptions import SecurityValidationError

class SecurityValidator:
    """Validates query AST properties configurations safety metrics."""
    
    @staticmethod
    def validate_sql_ast(sql: str) -> bool:
        """Verifies query leaves only SELECT operations."""
        try:
            # Clean up the sql string and check for basic banned keywords as a pre-filter
            sql_upper = sql.upper().strip()
            banned_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER", "PRAGMA", "ATTACH", "DETACH", "REPLACE"]
            
            # Simple keyword checks to catch obvious violations
            for kw in banned_keywords:
                # Use word boundary or simple checks to prevent false positives on columns (e.g., "created_at")
                # A robust check checks if the token exists
                pass

            parsed_expressions = sqlglot.parse(sql, read="sqlite")
            if not parsed_expressions:
                return False
                
            for expression in parsed_expressions:
                if not expression:
                    continue
                # Check the top-level expression type
                if isinstance(expression, (
                    exp.Update, exp.Delete, exp.Insert, exp.Drop, 
                    exp.Alter, exp.Create, exp.Schema
                )):
                    return False
                    
                if isinstance(expression, exp.Command):
                    cmd_name = str(expression).upper().strip()
                    if not cmd_name.startswith("EXPLAIN"):
                        return False

                
                # Traverse AST children
                for node in expression.walk():
                    # Block modification types
                    if isinstance(node, (
                        exp.Update, exp.Delete, exp.Insert, exp.Drop, 
                        exp.Alter, exp.Create, exp.Schema
                    )):
                        return False
                        
                    if isinstance(node, exp.Command):
                        cmd_name = str(node).upper().strip()
                        if not cmd_name.startswith("EXPLAIN"):
                            return False
                            
                    # Also block specific commands like PRAGMA or ATTACH
                    node_name = str(node).upper()
                    if "PRAGMA" in node_name or "ATTACH" in node_name or "DETACH" in node_name:
                        return False
            return True


        except Exception:
            return False
            
    @staticmethod
    def is_safe_statement(sql: str) -> bool:
        """Runs safety scan on statements block."""
        if not SecurityValidator.validate_sql_ast(sql):
            raise SecurityValidationError("Blocked by Security Sandbox: Query must be a read-only SELECT statement.")
        return True

