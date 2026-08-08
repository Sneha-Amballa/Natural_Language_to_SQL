"""Runtime Coverage and Integration Tests.

Covers all 7 integration scenarios and memory/visualization unit tests.
"""

# pyrefly: ignore [missing-import]
import pytest
import sqlite3
import os
import tempfile
import pandas as pd
import json
from unittest.mock import patch, MagicMock

from agent.memory import ConversationMemoryManager
from agent.orchestrator import SQLAgent
from agent.planner import QueryPlanner
from services.visualization_service import VisualizationService
from utils.csv_loader import CSVLoader
from utils.formatter import format_results
from core.security import SecurityValidator
from core.database import DatabaseManager
from utils.cache import cache_schema

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE customers (id INT PRIMARY KEY, name TEXT, age INT);")
    cursor.execute("CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT, amount REAL, order_date TEXT);")
    
    cursor.execute("INSERT INTO customers (id, name, age) VALUES (1, 'Alice', 30);")
    cursor.execute("INSERT INTO customers (id, name, age) VALUES (2, 'Bob', 25);")
    cursor.execute("INSERT INTO orders (id, customer_id, amount, order_date) VALUES (100, 1, 99.99, '2026-08-01');")
    cursor.execute("INSERT INTO orders (id, customer_id, amount, order_date) VALUES (101, 2, 49.50, '2026-08-02');")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

# --- 1. ConversationMemoryManager Unit Tests ---

def test_memory_empty():
    mem = ConversationMemoryManager()
    assert len(mem.get_history_within_tokens()) == 0

def test_memory_add_user_message():
    mem = ConversationMemoryManager()
    mem.add_message("user", "Hello agent")
    history = mem.get_history_within_tokens()
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello agent"

def test_memory_add_assistant_message():
    mem = ConversationMemoryManager()
    mem.add_message("assistant", "Hello user")
    history = mem.get_history_within_tokens()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"

def test_memory_multiple_messages():
    mem = ConversationMemoryManager()
    mem.add_message("system", "Sys message")
    mem.add_message("user", "User query")
    mem.add_message("assistant", "Agent response")
    assert len(mem.get_history_within_tokens()) == 3

def test_memory_token_counting():
    mem = ConversationMemoryManager()
    msg = {"role": "user", "content": "Test token count content string"}
    tokens = mem._count_tokens(msg)
    assert tokens > 0

def test_memory_below_token_limit():
    mem = ConversationMemoryManager(max_token_limit=1000)
    mem.add_message("user", "Short message")
    assert len(mem.get_history_within_tokens()) == 1

def test_memory_pruning_protects_system_and_first_user():
    # Enforce extremely small token limit to trigger pruning
    mem = ConversationMemoryManager(max_token_limit=15)
    
    # Add messages. The first user and system message should remain.
    mem.add_message("system", "System rule")  # protected
    mem.add_message("user", "First question")  # protected
    mem.add_message("assistant", "Response 1") # prunable
    mem.add_message("user", "Second question") # prunable
    
    # Triggers pruning
    mem.add_message("assistant", "Very long response that will force pruning of older prunable items")
    
    history = mem.get_history_within_tokens()
    roles = [m["role"] for m in history]
    contents = [m["content"] for m in history]
    
    # Asserts system and first user message are protected
    assert "system" in roles
    assert "First question" in contents
    # Prunable messages get popped to fit in the limit
    assert "Response 1" not in contents

def test_memory_context_retrieval():
    mem = ConversationMemoryManager()
    mem.add_message("user", "Get context query")
    retrieved = mem.get_history_within_tokens()
    assert len(retrieved) == 1
    assert retrieved[0]["content"] == "Get context query"

def test_memory_very_large_single_message():
    mem = ConversationMemoryManager(max_token_limit=10)
    mem.add_message("system", "Sys")
    mem.add_message("user", "First")
    # This message is huge and exceeds limit
    mem.add_message("user", "Very large message content that exceeds limit by itself")
    history = mem.get_history_within_tokens()
    # Pruning stops deleting when only protected system/first user remain
    assert len(history) >= 2

def test_memory_reset_wiping():
    mem = ConversationMemoryManager()
    mem.add_message("user", "Query")
    assert len(mem.get_history_within_tokens()) == 1
    # Reset messages
    mem.messages = []
    assert len(mem.get_history_within_tokens()) == 0


# --- 2. Runtime Memory Integration Test ---

def test_agent_uses_conversation_memory_manager(temp_db):
    agent = SQLAgent(temp_db)
    # Asserts orchestrator uses token memory manager
    assert isinstance(agent.memory, ConversationMemoryManager)


# --- 3. VisualizationService Unit Tests ---

def test_viz_date_numeric():
    viz = VisualizationService()
    df = pd.DataFrame({
        "order_date": pd.to_datetime(["2026-08-01", "2026-08-02"]),
        "amount": [100.0, 150.0]
    })
    rec = viz.get_recommendation(df)
    assert rec.should_render is True
    assert rec.chart_type == "line"

def test_viz_category_numeric():
    viz = VisualizationService()
    df = pd.DataFrame({
        "category": ["Electronics", "Appliances"],
        "sales": [5000.0, 2000.0]
    })
    rec = viz.get_recommendation(df)
    assert rec.should_render is True
    assert rec.chart_type == "bar"

def test_viz_numeric_numeric():
    viz = VisualizationService()
    df = pd.DataFrame({
        "x": [1.0, 2.0],
        "y": [10.0, 20.0]
    })
    rec = viz.get_recommendation(df)
    assert rec.should_render is True
    assert rec.chart_type == "scatter"

def test_viz_single_numeric():
    viz = VisualizationService()
    df = pd.DataFrame({
        "col_name": ["Alice", "Bob"],
        "sales": [500.0, 600.0]
    })
    rec = viz.get_recommendation(df)
    assert rec.should_render is True
    assert rec.chart_type == "bar"

def test_viz_empty_df():
    viz = VisualizationService()
    df = pd.DataFrame()
    rec = viz.get_recommendation(df)
    assert rec.should_render is False
    assert rec.chart_type == "none"

def test_viz_single_column_df():
    viz = VisualizationService()
    df = pd.DataFrame({"col1": [1, 2, 3]})
    rec = viz.get_recommendation(df)
    assert rec.should_render is False
    assert rec.chart_type == "none"

def test_viz_unsupported_data():
    viz = VisualizationService()
    # All text columns
    df = pd.DataFrame({
        "col1": ["Alice", "Bob"],
        "col2": ["NY", "SF"]
    })
    rec = viz.get_recommendation(df)
    assert rec.should_render is True
    assert rec.chart_type == "bar" # Fallback behavior


# --- 4. End-to-End Integration Scenarios (1 to 7) ---

# SCENARIO 1: Upload SQLite database -> discover tables -> retrieve schema
def test_integration_scenario_1(temp_db):
    # Initialize cache and database manager
    cache = cache_schema()
    cache.clear()
    
    db_mgr = DatabaseManager(temp_db)
    
    # 1. Discover tables
    tables = db_mgr.get_table_list()
    assert "customers" in tables
    assert "orders" in tables
    
    # 2. Retrieve schema details
    meta = db_mgr.get_schema_metadata("customers")
    cols = [c["name"] for c in meta["columns"]]
    assert "name" in cols
    assert "age" in cols

# SCENARIO 2: Upload CSV -> import to SQLite -> discover schema -> query data
def test_integration_scenario_2(tmp_path):
    # Create temp CSV file
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text("order_id,amount,customer\n101,99.50,Alice\n102,150.00,Bob\n")
    
    temp_db_path = tmp_path / "imported_csv.db"
    conn = sqlite3.connect(temp_db_path)
    
    # 1. CSV import
    CSVLoader.import_csv(str(csv_file), conn, "imported_orders")
    conn.close()
    
    db_mgr = DatabaseManager(str(temp_db_path))
    
    # 2. Discover schema
    meta = db_mgr.get_schema_metadata("imported_orders")
    cols = [c["name"] for c in meta["columns"]]
    assert "order_id" in cols
    assert "amount" in cols
    
    # 3. Query imported CSV data
    res = db_mgr.execute_raw("SELECT SUM(amount) FROM imported_orders;")
    assert res.rows[0][0] == 249.50
    
    # Clean up temp db
    if os.path.exists(str(temp_db_path)):
        os.remove(str(temp_db_path))

# SCENARIO 3: Ask "How many customers are there?" -> count_rows is available
def test_integration_scenario_3():
    cat = QueryPlanner.classify_question("How many customers are there?")
    allowed = QueryPlanner.plan_tools(cat)
    assert "count_rows" in allowed

# SCENARIO 4: Ask "What is the average order amount?" -> get_column_stats is available
def test_integration_scenario_4():
    cat = QueryPlanner.classify_question("What is the average order amount?")
    allowed = QueryPlanner.plan_tools(cat)
    assert "get_column_stats" in allowed

# SCENARIO 5: Ask "Show monthly sales" -> SQL result -> VisualizationService line spec
def test_integration_scenario_5(temp_db):
    db_mgr = DatabaseManager(temp_db)
    
    # Query result representing monthly sales (date + numeric)
    query_res = db_mgr.execute_raw("SELECT order_date, SUM(amount) FROM orders GROUP BY order_date;")
    
    df = pd.DataFrame(query_res.rows, columns=query_res.columns)
    # Ensure types match
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["SUM(amount)"] = pd.to_numeric(df["SUM(amount)"])
    
    viz = VisualizationService()
    rec = viz.get_recommendation(df)
    
    assert rec.should_render is True
    assert rec.chart_type == "line"
    assert rec.x_axis == "order_date"
    assert rec.y_axis == "SUM(amount)"

# SCENARIO 6: Execute invalid SQL -> security layer blocks it
def test_integration_scenario_6(temp_db):
    db_mgr = DatabaseManager(temp_db)
    # Mutation injection attempt
    invalid_sql = "SELECT * FROM customers; DROP TABLE customers;"
    
    assert SecurityValidator.validate_sql_ast(invalid_sql) is False

# SCENARIO 7: Download query results -> correct CSV content
def test_integration_scenario_7(temp_db):
    db_mgr = DatabaseManager(temp_db)
    query_res = db_mgr.execute_raw("SELECT name, age FROM customers;")
    
    df = pd.DataFrame(query_res.rows, columns=query_res.columns)
    csv_data = format_results(df, "csv")
    
    assert "name,age" in csv_data
    assert "Alice,30" in csv_data
    assert "Bob,25" in csv_data

# SCENARIO 8: Test context-aware chart detection (should_show_chart)
def test_should_show_chart_heuristics():
    viz = VisualizationService()
    
    # 1. Empty dataframe should not show chart
    assert viz.should_show_chart(pd.DataFrame(), "plot distribution") is False
    
    # 2. Single row should not show chart (even if explicitly requested)
    single_row_df = pd.DataFrame({"name": ["Alice"], "count": [1]})
    assert viz.should_show_chart(single_row_df, "show bar chart") is False
    
    # 3. Explicit chart request with valid multi-row data
    multi_row_df = pd.DataFrame({"grade": ["A", "B"], "count": [284, 354]})
    assert viz.should_show_chart(multi_row_df, "show distribution of final grades") is True
    
    # 4. Context-aware implicit chart request (multi-row with numeric columns)
    assert viz.should_show_chart(multi_row_df, "What are the grade counts?") is True
    
    # 5. Non-chartable scalar (e.g. single scalar average result count is len <= 1, but multi-row average without numeric column is False)
    text_only_df = pd.DataFrame({"name": ["Alice", "Bob"], "city": ["NY", "SF"]})
    assert viz.should_show_chart(text_only_df, "show list") is False
