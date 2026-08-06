"""Core Connection Pool Manager.

Safely handles read-only connection objects maps.
"""

import sqlite3
import pandas as pd
from typing import Generator
from models.models import QueryResult

import sqlite3
import pandas as pd
import time
import os
from typing import Generator, Dict, Any, List, Optional
from models.models import QueryResult
from core.exceptions import DatabaseConnectionError, QueryExecutionError

def make_timeout_handler(start_time: float, timeout: float):
    def handler():
        if time.time() - start_time > timeout:
            return 1  # returns non-zero to interrupt query execution
        return 0
    return handler

class DatabaseManager:
    """Provides secure database handles configuration controls."""
    
    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        
    def get_connection(self, read_only: bool = True) -> sqlite3.Connection:
        """Returns active SQLite connection handle."""
        try:
            if read_only:
                # For read-only mode, we enforce URI connection with mode=ro
                # Note: Windows paths need to be handled carefully in URI formatting
                normalized_path = self.db_path.replace("\\", "/")
                # Ensure the path starts with a slash for file:/// formatting on windows
                if not normalized_path.startswith("/"):
                    normalized_path = "/" + normalized_path
                uri = f"file:{normalized_path}?mode=ro"
                conn = sqlite3.connect(uri, uri=True)
            else:
                conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            raise DatabaseConnectionError(f"Could not connect to database at {self.db_path}: {e}") from e
        
    def execute_raw(self, sql: str, timeout: float = 5.0) -> QueryResult:
        """Runs SQLite commands applying resource limitations constraints."""
        start_perf = time.perf_counter()
        start_time = time.time()
        conn = self.get_connection(read_only=True)
        try:
            # Set timeout progress handler
            handler = make_timeout_handler(start_time, timeout)
            conn.set_progress_handler(handler, 100)
            
            cursor = conn.cursor()
            cursor.execute(sql)
            
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            
            serialized_rows = []
            for row in rows:
                serialized_rows.append(list(row))
                
            execution_time_ms = (time.perf_counter() - start_perf) * 1000.0
            
            return QueryResult(
                columns=columns,
                rows=serialized_rows,
                row_count=len(serialized_rows),
                execution_time_ms=execution_time_ms
            )
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e).lower() or "callback" in str(e).lower():
                raise QueryExecutionError(f"Query execution exceeded timeout limit of {timeout}s.") from e
            raise QueryExecutionError(f"Database operational error: {e}") from e
        except Exception as e:
            raise QueryExecutionError(f"Database query execution failed: {e}") from e
        finally:
            conn.close()
        
    def get_table_list(self) -> list:
        """Fetches tables identifiers lists."""
        conn = self.get_connection(read_only=True)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to fetch table list: {e}") from e
        finally:
            conn.close()

    def get_schema_metadata(self, table: str) -> dict:
        """Fetches table columns and foreign keys information."""
        conn = self.get_connection(read_only=True)
        try:
            cursor = conn.cursor()
            
            # Get table info (cid, name, type, notnull, dflt_value, pk)
            # Use param binding? No, PRAGMA doesn't accept bindings, so we construct it.
            # But table names should be validated/safe because they are derived from catalog.
            cursor.execute(f'PRAGMA table_info("{table}");')
            columns_info = cursor.fetchall()
            
            if not columns_info:
                # Try unquoted or check if it exists
                cursor.execute(f"PRAGMA table_info({table});")
                columns_info = cursor.fetchall()
            
            # Get foreign key list (id, seq, table, from, to, on_update, on_delete, match)
            cursor.execute(f'PRAGMA foreign_key_list("{table}");')
            fkeys_info = cursor.fetchall()
            
            columns = []
            primary_keys = []
            for col in columns_info:
                col_name = col["name"]
                col_type = col["type"]
                is_pk = bool(col["pk"])
                if is_pk:
                    primary_keys.append(col_name)
                
                # Check for foreign key references
                fkey_ref = None
                for fk in fkeys_info:
                    if fk["from"] == col_name:
                        fkey_ref = {"table": fk["table"], "column": fk["to"]}
                        break
                        
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "is_primary": is_pk,
                    "foreign_reference": fkey_ref
                })
                
            return {
                "name": table,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": [
                    {"from": fk["from"], "table": fk["table"], "to": fk["to"]}
                    for fk in fkeys_info
                ]
            }
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to fetch schema metadata for table '{table}': {e}") from e
        finally:
            conn.close()

