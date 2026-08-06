"""Tests for Utilities.

Verifies CSV headers normalization operations.
"""

import pytest

import pytest
import pandas as pd
from utils.csv_loader import CSVLoader
from utils.parser import MarkdownParser

import pytest
import pandas as pd
import sqlite3
import os
import tempfile
import json
import decimal
import datetime
from unittest.mock import patch, MagicMock

# Import all utilities
from utils.csv_loader import CSVLoader
from utils.parser import MarkdownParser, parse_llm_response, repair_json_string, parse_tables_from_sql, parse_key_value_config
from utils.retry import retry_llm_call, retry_on_exception, is_retryable_exception
from utils.timer import Timer, measure_execution_time, measure_time
from utils.cache import SchemaCache, cache_schema
from utils.formatter import ResultFormatter, format_results
from utils.logger import setup_logging, log_agent_steps
from utils.helpers import (
    clean_file_path, detect_file_type, safe_json_load, safe_json_dump,
    snake_case, normalize_column_name, truncate_text, sanitize_filename
)

# ----------------- CSV Loader Tests -----------------

def test_csv_headers_normalizations():
    """Verifies characters stripping cleanups algorithms and handles duplicate columns."""
    df = pd.DataFrame(columns=["User ID", "First Name!", "123_Count", "  spaces  ", "Age", "age"])
    cleaned_df = CSVLoader._clean_headers(df)
    
    expected_columns = ["user_id", "first_name", "col_123_count", "spaces", "age", "age_1"]
    assert list(cleaned_df.columns) == expected_columns

def test_csv_loader_import_resilient():
    """Verifies CSV import with multiple encoding fallbacks, chunked reading, and slug table names."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    
    # Save a sample CSV with duplicate columns and headers starting with numbers
    df = pd.DataFrame({
        "1st Column": [1, 2],
        "Name": ["Alice", "Bob"],
        "name": ["Smith", "Jones"]
    })
    df.to_csv(path, index=False)
    
    temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_db_fd)
    
    conn = sqlite3.connect(temp_db_path)
    try:
        CSVLoader.import_csv(path, conn, "123-demo table")
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        assert "tbl_123_demo_table" in tables
        
        cursor.execute("SELECT * FROM tbl_123_demo_table;")
        rows = cursor.fetchall()
        cols = [description[0] for description in cursor.description]
        
        assert cols == ["col_1st_column", "name", "name_1"]
        assert len(rows) == 2
    finally:
        conn.close()
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

# ----------------- Parser Tests -----------------

def test_markdown_parser_sql_block():
    text_with_sql = "I have generated the SQL:\n```sql\nSELECT * FROM users;\n```\nLet me know if you need help."
    thought, sql = MarkdownParser.parse_sql_block(text_with_sql)
    assert sql == "SELECT * FROM users;"
    assert "I have generated the SQL:" in thought
    assert "Let me know if you need help." in thought
    
    text_no_sql = "This is plain text with no SQL query."
    thought2, sql2 = MarkdownParser.parse_sql_block(text_no_sql)
    assert sql2 == ""
    assert thought2 == "This is plain text with no SQL query."

def test_repair_json_string():
    bad_json = "{'key': 'value', 'items': ['a', 'b']}"
    good_json = repair_json_string(bad_json)
    assert json.loads(good_json) == {"key": "value", "items": ["a", "b"]}

def test_parse_llm_response():
    # Case 1: Markdown SQL
    res1 = parse_llm_response("Here is the query:\n```sql\nSELECT * FROM products;\n```")
    assert res1["sql_query"] == "SELECT * FROM products;"
    assert "run_query" in [tc["name"] for tc in res1["tool_calls"]]
    
    # Case 2: JSON Response with tool calls
    json_text = '{"tool_calls": [{"name": "list_tables", "arguments": {}}], "assistant_response": "Listing tables."}'
    res2 = parse_llm_response(json_text)
    assert len(res2["tool_calls"]) == 1
    assert res2["tool_calls"][0]["name"] == "list_tables"
    assert res2["assistant_response"] == "Listing tables."
    
    # Case 3: Empty text
    res3 = parse_llm_response("")
    assert res3["tool_calls"] == []

def test_parse_tables_from_sql():
    sql = "SELECT u.name, o.id FROM users u JOIN orders o ON u.id = o.user_id;"
    tables = parse_tables_from_sql(sql)
    assert "users" in tables
    assert "orders" in tables

def test_parse_key_value_config():
    config_text = """
    # Comments
    PORT=8000
    HOST=localhost
    """
    config = parse_key_value_config(config_text)
    assert config == {"PORT": "8000", "HOST": "localhost"}

# ----------------- Retry Tests -----------------

class RateLimitError(Exception):
    pass

def test_is_retryable_exception():
    err1 = RateLimitError()
    setattr(err1, "status_code", 429)
    assert is_retryable_exception(err1) is True
    
    err2 = ValueError("Standard issue")
    assert is_retryable_exception(err2) is False

@patch("utils.retry.time.sleep", return_value=None)
def test_retry_llm_call_success_flow(mock_sleep):
    mock_func = MagicMock(side_effect=[RateLimitError("Rate limited"), "Success!"])
    res = retry_llm_call(mock_func)
    assert res == "Success!"
    assert mock_func.call_count == 2

@patch("utils.retry.time.sleep", return_value=None)
def test_retry_llm_call_failure_exhausted(mock_sleep):
    mock_func = MagicMock(side_effect=RateLimitError("Rate limited"))
    with pytest.raises(RateLimitError):
        retry_llm_call(mock_func)


def test_retry_on_exception_decorator():
    mock_func = MagicMock(side_effect=[ValueError("Failed"), "Decorated Success"])
    
    @retry_on_exception(retries=2, delay=0.01)
    def test_func():
        return mock_func()
        
    res = test_func()
    assert res == "Decorated Success"
    assert mock_func.call_count == 2

# ----------------- Timer Tests -----------------

def test_timer_as_context_manager():
    with Timer("context_test") as timer:
        assert timer.name == "context_test"
    assert timer.elapsed is not None
    assert timer.elapsed >= 0.0

def test_timer_as_decorator():
    @measure_time
    def decorated_func(x):
        return x * 2
        
    res = decorated_func(10)
    assert res == 20

def test_nested_timer():
    with measure_execution_time("parent"):
        with measure_execution_time("child"):
            pass

# ----------------- Cache Tests -----------------

def test_schema_cache_operations():
    cache = SchemaCache(ttl=1)
    cache.set("key1", "val1")
    assert cache.get("key1") == "val1"
    
    # Invalidation
    cache.delete("key1")
    assert cache.get("key1") is None
    
    # Auto loader callback
    loader = MagicMock(return_value="loaded_val")
    val = cache.get("key2", loader=loader)
    assert val == "loaded_val"
    assert loader.call_count == 1
    
    # Hit from cache
    val_cached = cache.get("key2", loader=loader)
    assert val_cached == "loaded_val"
    assert loader.call_count == 1 # cached, loader not called again
    
    # Expire TTL
    cache_short = SchemaCache(ttl=-1) # forces immediate expiration
    cache_short.set("key3", "val3")
    assert cache_short.get("key3") is None

def test_cache_schema_factory():
    c1 = cache_schema()
    c2 = cache_schema()
    assert c1 is c2  # Singleton
    
    c3 = cache_schema(ttl=10)
    assert c3 is not c1

# ----------------- Formatter Tests -----------------

def test_formatter_markdown():
    df = pd.DataFrame({"col1": [1, 2], "col2": [None, decimal.Decimal("10.5")]})
    md = ResultFormatter.df_to_markdown(df)
    assert "col1" in md
    assert "NULL" in md
    assert "10.5" in md

def test_format_results_types():
    df = pd.DataFrame({
        "num": [1], 
        "val": [decimal.Decimal("20.5")], 
        "date": [datetime.date(2026, 7, 12)]
    })
    
    csv_str = format_results(df, "csv")
    assert "2026-07-12" in csv_str
    
    json_str = format_results(df, "json")
    assert "20.5" in json_str
    
    dict_str = format_results(df, "dict")
    assert "20.5" in dict_str

# ----------------- Logger Tests -----------------

def test_setup_logging_and_steps(tmp_path):
    log_file = tmp_path / "test_agent.log"
    # Temporarily patch settings log path
    with patch("config.settings.LOG_FILE_PATH", str(log_file)):
        # Clear existing root logger handlers to force a fresh file logger initialization
        import logging
        logging.getLogger().handlers = []
        setup_logging("DEBUG")
        log_agent_steps(
            run_id="run-1",
            question="Find sales",
            tool_name="run_query",
            execution_time=12.5,
            arguments={"sql": "SELECT * FROM sales;"},
            sql="SELECT * FROM sales;",
            rows_returned=5,
            summary="Fetched 5 sales"
        )
        assert os.path.exists(str(log_file))

# ----------------- Helpers Tests -----------------

def test_helpers_paths_and_json():
    assert clean_file_path("c:\\test\\path\\file.txt") == os.path.normpath("c:/test/path/file.txt")
    
    # JSON loaded/dumped
    data = {"age": decimal.Decimal("20.5"), "time": datetime.datetime(2026, 7, 12, 12, 0)}
    dumped = safe_json_dump(data)
    assert "20.5" in dumped
    assert "2026-07-12" in dumped
    
    loaded = safe_json_load(dumped)
    assert loaded["age"] == 20.5

def test_helpers_strings():
    assert snake_case("UserIDNumber") == "user_id_number"
    assert normalize_column_name("123 User Name!") == "col_123_user_name"
    assert truncate_text("hello world", 5) == "hello..."
    assert sanitize_filename("../../etc/passwd") == "passwd"


def test_detect_file_type():
    # SQLite temp file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    with open(db_path, "wb") as f:
        f.write(b"SQLite format 3\x00" + b"\x00" * 16)
        
    csv_fd, csv_path = tempfile.mkstemp(suffix=".csv")
    os.close(csv_fd)
    with open(csv_path, "w") as f:
        f.write("col1,col2\n1,2\n")
        
    txt_fd, txt_path = tempfile.mkstemp(suffix=".txt")
    os.close(txt_fd)
    with open(txt_path, "w") as f:
        f.write("plain text")
        
    try:
        assert detect_file_type(db_path) == "sqlite"
        assert detect_file_type(csv_path) == "csv"
        
        with pytest.raises(ValueError):
            detect_file_type(txt_path)
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if os.path.exists(txt_path):
            os.remove(txt_path)


