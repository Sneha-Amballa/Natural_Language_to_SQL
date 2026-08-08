"""Tests for SQLAgent.

Verifies error correction loops.
"""

import pytest

import pytest
import sqlite3
import os
import tempfile
from unittest.mock import patch, MagicMock
from agent.orchestrator import SQLAgent
from models.models import AgentResponse

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

class MockChoice:
    def __init__(self, message):
        self.message = message

class MockCompletionResponse:
    def __init__(self, message):
        self.choices = [MockChoice(message)]

@patch("services.groq_service.GroqService.generate_completion")
def test_agent_correction_execution(mock_generate, temp_db):
    """Verifies self-correction handles syntactically broken SQL loops."""
    # Create agent instance
    agent = SQLAgent(temp_db)
    
    # We will simulate a 2-turn conversation:
    # Turn 1: LLM returns a tool call to run an invalid query: "SELECT * FROM missing_table"
    # Turn 2: LLM receives the error and returns the final answer
    
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "run_query"
    mock_tool_call.function.arguments = '{"sql": "SELECT * FROM missing_table;"}'
    
    message_1 = MagicMock()
    message_1.content = "Let me try querying the database."
    message_1.tool_calls = [mock_tool_call]
    
    message_2 = MagicMock()
    message_2.content = "The previous query failed, but here is Alice from the users table."
    message_2.tool_calls = None
    
    # Configure mock responses sequentially
    mock_generate.side_effect = [message_1, message_2]
    
    response = agent.execute("Find alice")
    
    assert isinstance(response, AgentResponse)
    assert "Alice" in response.response_text
    assert len(response.steps) == 1
    assert response.steps[0]["tool_called"] == "run_query"
    assert "do not exist in database" in response.steps[0]["result"] or "no such table" in response.steps[0]["result"]

# ----------------- Planner Tests -----------------

def test_query_planner():
    from agent.planner import QueryPlanner
    
    # Classifications
    assert QueryPlanner.classify_question("How many customers do we have?") == "Aggregation"
    assert QueryPlanner.classify_question("List customers where country is USA") == "Filtering"
    assert QueryPlanner.classify_question("Show products over daily sales chart") == "Trend"
    
    # Tool planning lists
    tools_agg = QueryPlanner.plan_tools("Aggregation")
    assert "explain_query" in tools_agg
    assert "suggest_indexes" in tools_agg
    
    tools_schema = QueryPlanner.plan_tools("Schema lookup")
    assert "run_query" not in tools_schema

# ----------------- State Machine Tests -----------------

def test_state_machine():
    from agent.state import AgentState, StateMachine
    
    sm = StateMachine()
    assert sm.current_state == AgentState.IDLE
    
    sm.transition_to(AgentState.UNDERSTAND)
    assert sm.current_state == AgentState.UNDERSTAND

# ----------------- Tool Executor Tests -----------------

def test_tool_executor():
    from agent.tool_executor import ToolExecutor
    from tools.registry import ToolRegistry
    from tools.base_tool import BaseTool
    from tools.tool_models import ToolResponse
    
    registry = ToolRegistry()
    
    # Mock a dummy tool
    class MockTool(BaseTool):
        @property
        def name(self): return "mock_tool"
        @property
        def description(self): return "mock"
        @property
        def schema(self): return {"type": "object", "properties": {"val": {"type": "string"}}, "required": ["val"]}
        def execute(self, **kwargs):
            return ToolResponse(is_success=True, result_content=f"value is {kwargs.get('val')}")
            
    registry.register(MockTool())
    
    executor = ToolExecutor(registry)
    
    # Single execution
    res = executor.execute_single("mock_tool", {"val": "hello"})
    assert res.is_success is True
    assert "hello" in res.result_content
    
    # Validation error
    res_bad = executor.execute_single("mock_tool", {})
    assert res_bad.is_success is False
    assert "Missing required" in res_bad.result_content
    
    # Batch execution
    batch_res = executor.execute_multiple([
        {"id": "c1", "name": "mock_tool", "arguments": {"val": "a"}},
        {"id": "c2", "name": "mock_tool", "arguments": {"val": "b"}}
    ])
    assert len(batch_res) == 2
    assert batch_res[0]["tool_call_id"] == "c1"
    assert "a" in batch_res[0]["result"]





