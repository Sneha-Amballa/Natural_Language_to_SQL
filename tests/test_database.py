"""Tests for Database Manager.

Verifies connection isolation.
"""

import pytest

import pytest
import sqlite3
import os
import tempfile
import time
from core.database import DatabaseManager
from core.exceptions import DatabaseConnectionError, QueryExecutionError

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Populate with sample tables and relations
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);")
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, category_id INTEGER, FOREIGN KEY(category_id) REFERENCES categories(id));")
    cursor.execute("INSERT INTO categories (id, name) VALUES (1, 'Electronics'), (2, 'Books');")
    cursor.execute("INSERT INTO products (id, name, price, category_id) VALUES (101, 'Laptop', 999.9, 1), (102, 'Sci-Fi Book', 15.0, 2);")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

def test_get_table_list(temp_db):
    db_mgr = DatabaseManager(temp_db)
    tables = db_mgr.get_table_list()
    assert "categories" in tables
    assert "products" in tables
    assert len(tables) == 2

def test_get_schema_metadata(temp_db):
    db_mgr = DatabaseManager(temp_db)
    meta = db_mgr.get_schema_metadata("products")
    
    assert meta["name"] == "products"
    columns = {c["name"]: c for c in meta["columns"]}
    assert "name" in columns
    assert columns["name"]["type"] == "TEXT"
    assert columns["id"]["is_primary"] is True
    
    # foreign key validation
    assert len(meta["foreign_keys"]) == 1
    fk = meta["foreign_keys"][0]
    assert fk["from"] == "category_id"
    assert fk["table"] == "categories"
    assert fk["to"] == "id"

def test_readonly_db_connection(temp_db):
    db_mgr = DatabaseManager(temp_db)
    # Read is allowed
    res = db_mgr.execute_raw("SELECT * FROM products;")
    assert res.row_count == 2
    assert res.columns == ["id", "name", "price", "category_id"]
    
    # Write (INSERT/UPDATE/DELETE) is blocked by the SQLite engine's read-only setting
    # (even if AST checks are bypassed, the SQLite engine itself will reject it)
    with pytest.raises(QueryExecutionError) as exc_info:
        db_mgr.execute_raw("INSERT INTO categories (id, name) VALUES (3, 'Home');")
    assert "attempt to write a readonly database" in str(exc_info.value).lower()

def test_query_execution_timeout(temp_db):
    db_mgr = DatabaseManager(temp_db)
    # Enforce a tight timeout limit and run a query that is artificially delayed or complex
    # In SQLite, we can generate a lot of rows or run cross joins to make a slow query.
    # E.g., a cross join of table with itself repeatedly.
    # Note: we use progress handler timeout.
    # Let's run a slow cross join query with a very small timeout (e.g. 0.001 seconds)
    slow_sql = """
        WITH RECURSIVE r(i) AS (
          VALUES(0)
          UNION ALL
          SELECT i+1 FROM r LIMIT 1000000
        )
        SELECT * FROM r;
    """
    with pytest.raises(QueryExecutionError) as exc_info:
        db_mgr.execute_raw(slow_sql, timeout=0.01)
    assert "timeout" in str(exc_info.value).lower()

