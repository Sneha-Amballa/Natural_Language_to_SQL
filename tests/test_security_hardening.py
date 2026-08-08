"""Hardened Security and SQL Catalog Validation Tests.

Covers the 28 tests required by Phase 4.
"""

import pytest
import sqlite3
import os
import tempfile
from unittest.mock import patch

from core.security import SecurityValidator
from core.database import DatabaseManager
from tools.validate_sql import ValidateSqlTool
from tools.sanitize_sql import SanitizeSqlTool
from tools.run_query import RunQueryTool
from core.exceptions import DatabaseConnectionError

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE customers (id INT PRIMARY KEY, name TEXT);")
    cursor.execute("CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT, amount REAL);")
    cursor.execute("INSERT INTO customers (id, name) VALUES (1, 'Alice');")
    cursor.execute("INSERT INTO orders (id, customer_id, amount) VALUES (100, 1, 99.99);")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

# --- SECURITY TESTS (1 to 14) ---

# 1. SELECT allowed
def test_select_allowed():
    assert SecurityValidator.validate_sql_ast("SELECT * FROM customers;") is True

# 2. WITH query allowed
def test_with_query_allowed():
    assert SecurityValidator.validate_sql_ast("WITH cte AS (SELECT * FROM customers) SELECT * FROM cte;") is True

# 3. EXPLAIN allowed if supported
def test_explain_allowed():
    assert SecurityValidator.validate_sql_ast("EXPLAIN QUERY PLAN SELECT * FROM customers;") is True

# 4. INSERT blocked
def test_insert_blocked():
    assert SecurityValidator.validate_sql_ast("INSERT INTO customers (id, name) VALUES (2, 'Bob');") is False

# 5. UPDATE blocked
def test_update_blocked():
    assert SecurityValidator.validate_sql_ast("UPDATE customers SET name = 'Bob' WHERE id = 1;") is False

# 6. DELETE blocked
def test_delete_blocked():
    assert SecurityValidator.validate_sql_ast("DELETE FROM customers WHERE id = 1;") is False

# 7. DROP blocked
def test_drop_blocked():
    assert SecurityValidator.validate_sql_ast("DROP TABLE customers;") is False

# 8. ALTER blocked
def test_alter_blocked():
    assert SecurityValidator.validate_sql_ast("ALTER TABLE customers ADD COLUMN age INT;") is False

# 9. CREATE blocked
def test_create_blocked():
    assert SecurityValidator.validate_sql_ast("CREATE TABLE temp (id INT);") is False

# 10. ATTACH blocked
def test_attach_blocked():
    assert SecurityValidator.validate_sql_ast("ATTACH DATABASE 'other.db' AS other;") is False

# 11. DETACH blocked
def test_detach_blocked():
    assert SecurityValidator.validate_sql_ast("DETACH DATABASE other;") is False

# 12. PRAGMA blocked
def test_pragma_blocked():
    assert SecurityValidator.validate_sql_ast("PRAGMA table_info(customers);") is False

# 13. TRUNCATE rejected
def test_truncate_blocked():
    assert SecurityValidator.validate_sql_ast("TRUNCATE TABLE customers;") is False

# 14. multiple statements rejected
def test_multiple_statements_blocked():
    # Multiple SELECTs
    assert SecurityValidator.validate_sql_ast("SELECT * FROM customers; SELECT * FROM orders;") is False
    # SELECT followed by mutation attempt
    assert SecurityValidator.validate_sql_ast("SELECT * FROM customers; DROP TABLE customers;") is False


# --- DATABASE TESTS (15 to 17) ---

# 15. read-only mode connection pool enforcement
def test_readonly_mode_connection_string(temp_db):
    db_manager = DatabaseManager(temp_db)
    conn = db_manager.get_connection()
    try:
        cursor = conn.cursor()
        with pytest.raises(sqlite3.OperationalError) as excinfo:
            cursor.execute("INSERT INTO customers (id, name) VALUES (99, 'Bypassed');")
        assert "readonly" in str(excinfo.value).lower()
    finally:
        conn.close()

# 16. write cannot modify database
def test_write_cannot_modify_db_engine(temp_db):
    db_manager = DatabaseManager(temp_db)
    
    # Try direct execution of write statement via RunQueryTool
    tool = RunQueryTool(temp_db)
    res = tool.execute(sql="INSERT INTO customers (id, name) VALUES (99, 'Bypassed');")
    assert res.is_success is False
    
    # Verify that database remained unmodified
    res_select = db_manager.execute_raw("SELECT COUNT(*) FROM customers;")
    assert res_select.rows[0][0] == 1

# 17. timeout protection works
def test_timeout_protection(temp_db):
    db_manager = DatabaseManager(temp_db)
    # Slow recursive CTE query
    slow_sql = "WITH RECURSIVE r(i) AS (VALUES(0) UNION ALL SELECT i+1 FROM r LIMIT 100000000) SELECT COUNT(*) FROM r;"
    
    # Execute query, should trigger timeout progress handler
    with pytest.raises(Exception) as excinfo:
        db_manager.execute_raw(slow_sql, timeout=0.1)
    assert "interrupted" in str(excinfo.value).lower() or "timeout" in str(excinfo.value).lower() or "progress" in str(excinfo.value).lower()


# --- CATALOG TESTS (18 to 28) ---

# 18. valid table
def test_catalog_valid_table(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT * FROM customers;")
    assert res.is_success is True

# 19. invalid table
def test_catalog_invalid_table(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT * FROM nonexistent;")
    assert res.is_success is False
    assert "nonexistent" in res.result_content

# 20. valid column
def test_catalog_valid_column(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT name FROM customers;")
    assert res.is_success is True

# 21. invalid column
def test_catalog_invalid_column(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT age FROM customers;")
    assert res.is_success is False
    assert "age" in res.result_content

# 22. valid alias
def test_catalog_valid_alias(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT c.name FROM customers c;")
    assert res.is_success is True

# 23. invalid alias
def test_catalog_invalid_alias(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT x.name FROM customers c;")
    assert res.is_success is False
    assert "x.name" in res.result_content

# 24. valid JOIN
def test_catalog_valid_join(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT c.name, o.amount FROM customers c JOIN orders o ON c.id = o.customer_id;")
    assert res.is_success is True

# 25. invalid JOIN column
def test_catalog_invalid_join_col(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT c.name FROM customers c JOIN orders o ON c.invalid_col = o.customer_id;")
    assert res.is_success is False
    assert "c.invalid_col" in res.result_content

# 26. invalid JOIN table
def test_catalog_invalid_join_table(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT c.name FROM customers c JOIN nonexistent o ON c.id = o.customer_id;")
    assert res.is_success is False
    assert "nonexistent" in res.result_content

# 27. valid nested query
def test_catalog_valid_nested(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT * FROM customers WHERE id IN (SELECT customer_id FROM orders);")
    assert res.is_success is True

# 28. invalid nested query
def test_catalog_invalid_nested(temp_db):
    tool = ValidateSqlTool(temp_db)
    res = tool.execute(sql="SELECT * FROM customers WHERE id IN (SELECT invalid_col FROM orders);")
    assert res.is_success is False
    assert "invalid_col" in res.result_content
