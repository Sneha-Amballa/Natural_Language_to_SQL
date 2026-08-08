"""Schema Caching Integration Tests.

Covers the 13 required test cases of Phase 5.
"""

import pytest
import sqlite3
import os
import tempfile
import time
from unittest.mock import patch, MagicMock

from core.database import DatabaseManager
from utils.cache import cache_schema, SchemaCache
from tools.list_tables import ListTablesTool
from tools.get_schema import GetSchemaTool
from tools.get_column_stats import GetColumnStatsTool
from tools.count_rows import CountRowsTool
from tools.validate_sql import ValidateSqlTool

@pytest.fixture
def temp_db1():
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
        try:
            os.remove(path)
        except Exception:
            pass

@pytest.fixture
def temp_db2():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE logs (id INT PRIMARY KEY, msg TEXT);")
    cursor.execute("INSERT INTO logs (id, msg) VALUES (10, 'Info log');")
    conn.commit()
    conn.close()
    
    yield path
    
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

# TEST 1 & 2 & 3 & 4: Hit, Miss, and connection spying
def test_schema_cache_hit_miss_flow(temp_db1):
    db_manager = DatabaseManager(temp_db1)
    cache = cache_schema()
    cache.clear()
    
    # Spy on get_connection
    with patch.object(db_manager, "get_connection", wraps=db_manager.get_connection) as mock_get_conn:
        # TEST 1: First schema request produces cache miss (must access db)
        tables1 = db_manager.get_table_list()
        assert mock_get_conn.call_count == 1
        assert "users" in tables1
        
        # TEST 2 & 3: Second identical request produces cache hit (uses cached value)
        tables2 = db_manager.get_table_list()
        
        # TEST 4: Second request does not query database connection again
        assert mock_get_conn.call_count == 1
        assert tables1 == tables2

# TEST 5: TTL expiration causes refresh
def test_schema_cache_ttl_expiration(temp_db1):
    db_manager = DatabaseManager(temp_db1)
    cache = cache_schema()
    cache.clear()
    
    with patch.object(db_manager, "get_connection", wraps=db_manager.get_connection) as mock_get_conn:
        # Load initially (miss)
        db_manager.get_table_list()
        assert mock_get_conn.call_count == 1
        
        # Expose cache and force expiration by changing TTL to -1 (expired immediately)
        original_ttl = cache.ttl
        cache.ttl = -1
        try:
            # Query again: must produce a miss and call get_connection again
            db_manager.get_table_list()
            assert mock_get_conn.call_count == 2
        finally:
            cache.ttl = original_ttl

# TEST 6: Explicit invalidation causes refresh
def test_schema_cache_explicit_invalidation(temp_db1):
    db_manager = DatabaseManager(temp_db1)
    cache = cache_schema()
    cache.clear()
    
    with patch.object(db_manager, "get_connection", wraps=db_manager.get_connection) as mock_get_conn:
        # Query 1
        db_manager.get_table_list()
        assert mock_get_conn.call_count == 1
        
        # Query 2 (Hit)
        db_manager.get_table_list()
        assert mock_get_conn.call_count == 1
        
        # Explicit Invalidate
        cache.clear()
        
        # Query 3 (Miss)
        db_manager.get_table_list()
        assert mock_get_conn.call_count == 2

# TEST 7 & 9: New database gets different cache entry & no cross-database collision
def test_schema_cache_database_separation(temp_db1, temp_db2):
    db_manager1 = DatabaseManager(temp_db1)
    db_manager2 = DatabaseManager(temp_db2)
    cache = cache_schema()
    cache.clear()
    
    # Query database 1 (miss)
    tables1 = db_manager1.get_table_list()
    assert "users" in tables1
    
    # Query database 2 (miss)
    tables2 = db_manager2.get_table_list()
    assert "logs" in tables2
    assert "users" not in tables2 # TEST 9: No collision, returns correct database 2 schemas

# TEST 8: Different uploaded CSV gets a different cache entry
def test_schema_cache_csv_timestamp_change(temp_db1):
    db_manager = DatabaseManager(temp_db1)
    cache = cache_schema()
    cache.clear()
    
    # Initial request
    db_manager.get_table_list()
    
    # Modify database file timestamp (simulating overwrite/replacement uploader action)
    future_time = time.time() + 15
    os.utime(temp_db1, (future_time, future_time))
    
    with patch.object(db_manager, "get_connection", wraps=db_manager.get_connection) as mock_get_conn:
        # Request table list: timestamp changed, generates a new key, leading to database re-query
        db_manager.get_table_list()
        assert mock_get_conn.call_count == 1

# TEST 10: Existing schema tools continue working
def test_existing_schema_tools(temp_db1):
    cache = cache_schema()
    cache.clear()
    
    list_tool = ListTablesTool(temp_db1)
    res_list = list_tool.execute()
    assert res_list.is_success is True
    assert "users" in res_list.result_content
    
    schema_tool = GetSchemaTool(temp_db1)
    res_schema = schema_tool.execute(tables=["users"])
    assert res_schema.is_success is True
    assert "name" in res_schema.result_content

# TEST 11: get_column_stats continues working
def test_get_column_stats_caching(temp_db1):
    cache = cache_schema()
    cache.clear()
    
    tool = GetColumnStatsTool(temp_db1)
    res = tool.execute(table="users", col="name")
    assert res.is_success is True
    assert "unique_count" in res.result_content

# TEST 12: count_rows continues working
def test_count_rows_caching(temp_db1):
    cache = cache_schema()
    cache.clear()
    
    tool = CountRowsTool(temp_db1)
    res = tool.execute(table_name="users")
    assert res.is_success is True
    assert res.result_content == "1"

# TEST 13: catalog validation continues working
def test_catalog_validation_caching(temp_db1):
    cache = cache_schema()
    cache.clear()
    
    tool = ValidateSqlTool(temp_db1)
    res = tool.execute(sql="SELECT name FROM users;")
    assert res.is_success is True
    
    res_bad = tool.execute(sql="SELECT age FROM users;")
    assert res_bad.is_success is False
