"""Tests for get_column_stats and count_rows tools.

Verifies Phase 3 requirements.
"""

import pytest
import sqlite3
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

from tools.count_rows import CountRowsTool
from tools.get_column_stats import GetColumnStatsTool
from tools.registry import ToolRegistry
from agent.planner import QueryPlanner
from core.exceptions import DatabaseConnectionError

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    # Create tables
    cursor.execute("CREATE TABLE test_numeric (id INT PRIMARY KEY, val_num REAL, val_nulls INT);")
    cursor.execute("CREATE TABLE test_text (id INT PRIMARY KEY, name TEXT);")
    cursor.execute("CREATE TABLE test_empty (id INT PRIMARY KEY, score REAL);")
    
    # Populate numeric
    cursor.execute("INSERT INTO test_numeric (id, val_num, val_nulls) VALUES (1, 10.0, 100);")
    cursor.execute("INSERT INTO test_numeric (id, val_num, val_nulls) VALUES (2, 20.0, NULL);")
    cursor.execute("INSERT INTO test_numeric (id, val_num, val_nulls) VALUES (3, 30.0, 100);")
    
    # Populate text
    cursor.execute("INSERT INTO test_text (id, name) VALUES (1, 'Alice');")
    cursor.execute("INSERT INTO test_text (id, name) VALUES (2, 'Bob');")
    
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

# --- get_column_stats tests ---

# 1. numeric column statistics
def test_get_column_stats_numeric(temp_db):
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="test_numeric", col="val_num")
    assert res.is_success is True
    stats = json.loads(res.result_content)
    assert stats["min"] == 10.0
    assert stats["max"] == 30.0
    assert stats["average"] == 20.0
    assert stats["null_count"] == 0
    assert stats["unique_count"] == 3

# 2. text column statistics
def test_get_column_stats_text(temp_db):
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="test_text", col="name")
    assert res.is_success is True
    stats = json.loads(res.result_content)
    assert "average" not in stats
    assert stats["min"] == "Alice"
    assert stats["max"] == "Bob"
    assert stats["null_count"] == 0
    assert stats["unique_count"] == 2

# 3. null counting & 4. unique counting
def test_get_column_stats_nulls_and_uniques(temp_db):
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="test_numeric", col="val_nulls")
    assert res.is_success is True
    stats = json.loads(res.result_content)
    assert stats["null_count"] == 1
    assert stats["unique_count"] == 1

# 5. invalid table
def test_get_column_stats_invalid_table(temp_db):
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="invalid_tbl", col="val_num")
    assert res.is_success is False
    assert "does not exist" in res.result_content

# 6. invalid column
def test_get_column_stats_invalid_column(temp_db):
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="test_numeric", col="invalid_col")
    assert res.is_success is False
    assert "does not exist" in res.result_content

# 7. empty table if supported
def test_get_column_stats_empty_table(temp_db):
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="test_empty", col="score")
    assert res.is_success is True
    stats = json.loads(res.result_content)
    assert stats["null_count"] == 0
    assert stats["unique_count"] == 0
    assert stats["min"] is None
    assert stats["max"] is None
    assert stats["average"] is None

# 8. database connection failure
@patch("core.database.DatabaseManager.get_connection")
def test_get_column_stats_connection_failure(mock_conn, temp_db):
    mock_conn.side_effect = DatabaseConnectionError("Failed connection")
    tool = GetColumnStatsTool(temp_db)
    res = tool.execute(table="test_numeric", col="val_num")
    assert res.is_success is False
    assert "Failed connection" in res.result_content

# --- count_rows tests ---

# 9. normal table count
def test_count_rows_normal(temp_db):
    tool = CountRowsTool(temp_db)
    res = tool.execute(table_name="test_numeric")
    assert res.is_success is True
    assert res.result_content == "3"

# 10. empty table count
def test_count_rows_empty(temp_db):
    tool = CountRowsTool(temp_db)
    res = tool.execute(table_name="test_empty")
    assert res.is_success is True
    assert res.result_content == "0"

# 11. invalid table
def test_count_rows_invalid_table(temp_db):
    tool = CountRowsTool(temp_db)
    res = tool.execute(table_name="invalid_tbl")
    assert res.is_success is False
    assert "does not exist" in res.result_content

# 12. database connection failure
@patch("core.database.DatabaseManager.get_connection")
def test_count_rows_connection_failure(mock_conn, temp_db):
    mock_conn.side_effect = DatabaseConnectionError("Failed connection")
    tool = CountRowsTool(temp_db)
    res = tool.execute(table_name="test_numeric")
    assert res.is_success is False
    assert "Failed connection" in res.result_content

# --- Tool Registry Tests (13) ---

def test_registry_missing_tools_registration(temp_db):
    registry = ToolRegistry()
    registry.register(GetColumnStatsTool(temp_db))
    registry.register(CountRowsTool(temp_db))
    
    # 13a. list tools
    tools = registry.list_tools()
    assert "get_column_stats" in tools
    assert "count_rows" in tools
    
    # 13b. executable through registry
    res_stats = registry.execute_tool("get_column_stats", table="test_numeric", col="val_num")
    assert res_stats.is_success is True
    
    res_count = registry.execute_tool("count_rows", table_name="test_numeric")
    assert res_count.is_success is True
    assert res_count.result_content == "3"
    
    # 13c. schema generated correctly
    schemas = registry.get_all_schemas()
    stats_schema = next(s for s in schemas if s["function"]["name"] == "get_column_stats")
    assert "table" in stats_schema["function"]["parameters"]["properties"]
    assert "col" in stats_schema["function"]["parameters"]["properties"]

# --- Agent Integration / Planner Tests (14) ---

def test_planner_tool_exposure_integration():
    # TEST 14a: "How many customers are there?" -> count_rows
    cat1 = QueryPlanner.classify_question("How many customers are there?")
    assert cat1 == "Aggregation"
    allowed1 = QueryPlanner.plan_tools(cat1)
    assert "count_rows" in allowed1
    assert "get_column_stats" in allowed1
    
    # TEST 14b: "What is the average order amount?" -> get_column_stats
    cat2 = QueryPlanner.classify_question("What is the average order amount?")
    assert cat2 == "Aggregation"
    allowed2 = QueryPlanner.plan_tools(cat2)
    assert "get_column_stats" in allowed2
    assert "count_rows" in allowed2

    # TEST 14c: "What is the maximum order amount?" -> get_column_stats
    cat3 = QueryPlanner.classify_question("What is the maximum order amount?")
    assert cat3 == "Aggregation"
    allowed3 = QueryPlanner.plan_tools(cat3)
    assert "get_column_stats" in allowed3
    assert "count_rows" in allowed3
