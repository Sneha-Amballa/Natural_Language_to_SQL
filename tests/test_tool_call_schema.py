"""Tool Call Schema and Argument Validation Tests.

Validates the 10 tests required by Phase 11 success criteria.
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import MagicMock, patch
from tools.registry import ToolRegistry
from tools.count_rows import CountRowsTool
from tools.get_column_stats import GetColumnStatsTool
from agent.planner import QueryPlanner
from agent.orchestrator import SQLAgent
from core.database import DatabaseManager

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE student_performance_dataset (
            student_id INTEGER PRIMARY KEY,
            gender TEXT,
            final_grade TEXT
        );
    """)
    cursor.execute("INSERT INTO student_performance_dataset VALUES (1, 'F', 'A');")
    cursor.execute("INSERT INTO student_performance_dataset VALUES (2, 'M', 'B');")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        os.remove(path)

# TEST 1: Verify count_rows is registered
def test_count_rows_registered(temp_db):
    registry = ToolRegistry()
    registry.register(CountRowsTool(temp_db))
    assert "count_rows" in registry.list_tools()

# TEST 2: Verify count_rows is LLM-visible for Aggregation/count questions
def test_count_rows_planner_exposure():
    cat = QueryPlanner.classify_question("How many students are in the dataset?")
    assert cat == "Aggregation"
    allowed = QueryPlanner.plan_tools(cat)
    assert "count_rows" in allowed

# TEST 3: Verify the generated Groq schema contains table_name
def test_count_rows_schema_contains_table_name(temp_db):
    tool = CountRowsTool(temp_db)
    schema = tool.schema
    assert "table_name" in schema["properties"]

# TEST 4: Verify the generated Groq schema does NOT define table
def test_count_rows_schema_does_not_define_table(temp_db):
    tool = CountRowsTool(temp_db)
    schema = tool.schema
    assert "table" not in schema["properties"]

# TEST 5: Verify table_name is required
def test_count_rows_table_name_required(temp_db):
    tool = CountRowsTool(temp_db)
    schema = tool.schema
    assert "table_name" in schema["required"]

# TEST 6: Verify count_rows executes successfully using {"table_name": "student_performance_dataset"}
def test_count_rows_executes_successfully(temp_db):
    tool = CountRowsTool(temp_db)
    res = tool.execute(table_name="student_performance_dataset")
    assert res.is_success is True
    assert res.result_content == "2"

# TEST 7: Verify an invalid argument such as {"table": "student_performance_dataset"} does NOT bypass schema validation
def test_count_rows_invalid_arguments_rejected(temp_db):
    tool = CountRowsTool(temp_db)
    val_res = tool.validate(table="student_performance_dataset")
    assert val_res.is_valid is False
    assert any("table_name" in err for err in val_res.errors)

# TEST 8: Verify get_column_stats has matching schema and implementation parameters
def test_get_column_stats_matching_schema(temp_db):
    tool = GetColumnStatsTool(temp_db)
    schema = tool.schema
    assert "table" in schema["properties"]
    assert "col" in schema["properties"]
    assert "table" in schema["required"]
    assert "col" in schema["required"]
    
    # Execution
    res = tool.execute(table="student_performance_dataset", col="gender")
    assert res.is_success is True

# TEST 9: Mock the Groq completion and verify that the schema sent to Groq contains the correct count_rows parameter definition
@patch("services.groq_service.GroqService.generate_completion")
def test_groq_schema_contains_table_name(mock_generate, temp_db):
    agent = SQLAgent(temp_db)
    
    msg = MagicMock()
    msg.content = "Total rows is 2"
    msg.tool_calls = None
    mock_generate.return_value = msg
    
    agent.execute("How many students are in student_performance_dataset?")
    
    # Extract the schema passed to GroqService
    called_args = mock_generate.call_args
    assert called_args is not None
    tools = called_args[1]["tools"]
    
    # Locate count_rows schema
    count_schema = next(t for t in tools if t["function"]["name"] == "count_rows")
    assert "table_name" in count_schema["function"]["parameters"]["properties"]
    assert "table" not in count_schema["function"]["parameters"]["properties"]

# TEST 10: Simulate the original invalid tool generation and verify the application handles it safely without executing an unsafe or malformed tool call
@patch("services.groq_service.GroqService.generate_completion")
def test_safely_handle_failed_generation(mock_generate, temp_db):
    agent = SQLAgent(temp_db)
    
    # Simulate a transient 400 error on the first call, then succeed on retry
    err_msg = "Failed to call a function. failed_generation: <function=count_rows{\"table\": \"student_performance_dataset\"}>"
    
    # Setup call side effects: first call throws tool_use_failed, second call succeeds with valid output
    msg_success = MagicMock()
    msg_success.content = "There are 2 students."
    msg_success.tool_calls = None
    
    mock_generate.side_effect = [
        Exception(err_msg),
        msg_success
    ]
    
    response = agent.execute("How many students are in student_performance_dataset?")
    
    # Assert orchestrator caught error, appended warning, retried, and completed successfully
    assert response.response_text == "There are 2 students."
    assert mock_generate.call_count == 2
