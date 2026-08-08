"""Tests for agent tool exposure and internal safety validation.

Verifies the fix for Phase 2.
"""

import pytest
import sqlite3
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

from agent.planner import QueryPlanner
from agent.orchestrator import SQLAgent
from tools.run_query import RunQueryTool
from tools.validate_sql import ValidateSqlTool
from tools.sanitize_sql import SanitizeSqlTool

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT);")
    cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice');")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

# TEST 1: QueryPlanner exposes get_sample_rows when schema exploration is required
def test_planner_exposes_get_sample_rows_on_schema_exploration():
    category = QueryPlanner.classify_question("Show me sample records from the customers table")
    assert category == "Schema lookup"
    allowed_tools = QueryPlanner.plan_tools(category)
    assert "get_sample_rows" in allowed_tools
    # find_column_values should not be exposed here
    assert "find_column_values" not in allowed_tools

# TEST 2: QueryPlanner exposes find_column_values when value discovery/filter verification is required
def test_planner_exposes_find_column_values_on_value_discovery():
    category = QueryPlanner.classify_question("Find customers from Hyderabad")
    assert category == "Filtering"
    allowed_tools = QueryPlanner.plan_tools(category)
    assert "find_column_values" in allowed_tools
    assert "get_sample_rows" in allowed_tools

# TEST 3 & 4: Final Groq tool schema contains get_sample_rows and find_column_values
# Also verifies validate_sql and sanitize_sql are not in LLM schema
@patch("services.groq_service.GroqService.generate_completion")
def test_final_groq_tool_schema_contains_required_tools(mock_generate, temp_db):
    agent = SQLAgent(temp_db)
    
    # Mock completion response to end orchestrator cycle immediately
    msg = MagicMock()
    msg.content = "Here is the result."
    msg.tool_calls = None
    mock_generate.return_value = msg
    
    agent.execute("Find customers from Hyderabad")
    
    assert mock_generate.call_count >= 1
    # Get the tools keyword argument from the LLM call
    called_kwargs = mock_generate.call_args[1]
    tools_schema = called_kwargs.get("tools", [])
    
    tool_names = [t["function"]["name"] for t in tools_schema]
    
    # TEST 3
    assert "get_sample_rows" in tool_names
    
    # TEST 4
    assert "find_column_values" in tool_names
    
    # Safety checks: validate_sql and sanitize_sql are NOT exposed to the LLM
    assert "validate_sql" not in tool_names
    assert "sanitize_sql" not in tool_names

# TEST 5: validate_sql remains internally enforced in run_query
def test_validate_sql_remains_internally_enforced(temp_db):
    # RunQueryTool executes ValidateSqlTool internally
    tool = RunQueryTool(temp_db)
    
    # Selecting non-existent column fails validate_sql checks
    res = tool.execute(sql="SELECT non_existent_col FROM users;")
    assert res.is_success is False
    assert "Validation Failed" in res.result_content

# TEST 6: sanitize_sql remains internally enforced in run_query
def test_sanitize_sql_remains_internally_enforced(temp_db):
    # RunQueryTool executes SanitizeSqlTool internally
    tool = RunQueryTool(temp_db)
    
    # Mutation query fails sanitize_sql checks
    res = tool.execute(sql="DELETE FROM users;")
    assert res.is_success is False
    assert "Sanitization Blocked" in res.result_content

# TEST 7: run_query cannot execute an unsafe query by bypassing validation
def test_run_query_blocks_unsafe_execution_bypass(temp_db):
    tool = RunQueryTool(temp_db)
    
    # Ensure raw write attempts (e.g. DROP TABLE) are blocked and fail
    res = tool.execute(sql="DROP TABLE users;")
    assert res.is_success is False
    assert "Sanitization Blocked" in res.result_content
    
    # Double check database state to verify table users still exists and wasn't dropped
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    row = cursor.fetchone()
    conn.close()
    assert row is not None
