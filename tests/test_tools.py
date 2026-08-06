"""Tests for Agent Tools.

Verifies schema parameter formats validations.
"""

import pytest

import pytest
import sqlite3
import os
import tempfile
import json
from tools.list_tables import ListTablesTool
from tools.get_schema import GetSchemaTool
from tools.run_query import RunQueryTool
from tools.get_sample_rows import GetSampleRowsTool
from tools.find_column_values import FindColumnValuesTool
from tools.validate_sql import ValidateSqlTool
from tools.sanitize_sql import SanitizeSqlTool
from tools.explain_query import ExplainQueryTool
from tools.suggest_indexes import SuggestIndexesTool
from tools.registry import ToolRegistry
from tools.tool_models import ToolResponse

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT);")
    cursor.execute("CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, amount REAL, FOREIGN KEY(user_id) REFERENCES users(id));")
    cursor.execute("CREATE INDEX idx_users_name ON users(name);")
    cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice');")
    cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob');")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

def test_list_tables_tool(temp_db):
    tool = ListTablesTool(temp_db)
    res = tool.execute()
    assert res.is_success is True
    assert "users" in res.result_content
    assert "orders" in res.result_content
    # Checks row counts are fetched
    assert "row_count" in res.result_content

def test_get_schema_tool(temp_db):
    tool = GetSchemaTool(temp_db)
    res = tool.execute(tables=["users"])
    assert res.is_success is True
    assert "users" in res.result_content
    assert "idx_users_name" in res.result_content
    assert "nullable" in res.result_content

def test_get_sample_rows_tool(temp_db):
    tool = GetSampleRowsTool(temp_db)
    # Test random sampling
    res_rand = tool.execute(table="users", limit=1, method="random")
    assert res_rand.is_success is True
    assert "Alice" in res_rand.result_content or "Bob" in res_rand.result_content
    # Test Markdown format is returned
    assert "|" in res_rand.result_content

def test_find_column_values_tool(temp_db):
    tool = FindColumnValuesTool(temp_db)
    # Exact search
    res_exact = tool.execute(table="users", column="name", search_term="Alice", search_type="exact")
    assert res_exact.is_success is True
    assert "Alice" in res_exact.result_content
    assert "Bob" not in res_exact.result_content
    
    # Like search
    res_like = tool.execute(table="users", column="name", search_term="A", search_type="like")
    assert "Alice" in res_like.result_content

def test_validate_sql_tool(temp_db):
    tool = ValidateSqlTool(temp_db)
    # Valid SELECT
    res_ok = tool.execute(sql="SELECT name FROM users WHERE id = 1;")
    assert res_ok.is_success is True
    
    # Missing columns
    res_bad_col = tool.execute(sql="SELECT age FROM users;")
    assert res_bad_col.is_success is False
    assert "age" in res_bad_col.result_content

def test_sanitize_sql_tool(temp_db):
    tool = SanitizeSqlTool(temp_db)
    res = tool.execute(sql="DROP TABLE users;")
    assert res.is_success is False
    assert "unsafe" in res.result_content.lower() or "blocked" in res.result_content.lower()

def test_run_query_tool_pipeline(temp_db):
    tool = RunQueryTool(temp_db)
    # Should run sanitize -> validate -> execute query returning metadata
    res = tool.execute(sql="SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id;")
    assert res.is_success is True
    data = json.loads(res.result_content)
    assert "columns" in data
    assert "rows" in data
    assert "execution_time_ms" in data

def test_explain_query_tool(temp_db):
    tool = ExplainQueryTool(temp_db)
    res = tool.execute(sql="SELECT * FROM users WHERE id = 2;")
    assert res.is_success is True
    assert "search" in res.result_content.lower() or "scan" in res.result_content.lower()


def test_suggest_indexes_tool(temp_db):
    tool = SuggestIndexesTool(temp_db)
    # Query causing scan
    res = tool.execute(sql="SELECT * FROM orders WHERE amount > 100.0;")
    assert res.is_success is True
    assert "idx_orders_amount" in res.result_content
    assert "estimated_improvement" in res.result_content

def test_registry_integration(temp_db):
    # Registry loading & schemas
    registry = ToolRegistry()
    registry.register(ListTablesTool(temp_db))
    registry.register(GetSchemaTool(temp_db))
    
    # execute_tool
    res = registry.execute_tool("list_tables")
    assert res.is_success is True
    assert "users" in res.result_content
    
    # Schemas Groq compatibility checks
    schemas = registry.get_all_schemas()
    assert len(schemas) == 2
    assert schemas[0]["type"] == "function"
    assert "parameters" in schemas[0]["function"]


