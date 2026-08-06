"""Tests for Security Validator.

Verifies AST verification pipelines.
"""

import pytest

import pytest
from core.security import SecurityValidator
from core.exceptions import SecurityValidationError

def test_validate_sql_syntax_allowlist():
    """Verifies SELECT command expressions are allowed."""
    # Good SELECT statements
    assert SecurityValidator.validate_sql_ast("SELECT * FROM products;") is True
    assert SecurityValidator.validate_sql_ast("SELECT id, name FROM users WHERE age > 21 LIMIT 10;") is True
    assert SecurityValidator.validate_sql_ast("WITH sales_cte AS (SELECT id, amount FROM sales) SELECT SUM(amount) FROM sales_cte;") is True
    assert SecurityValidator.validate_sql_ast("EXPLAIN QUERY PLAN SELECT * FROM orders;") is True

def test_validate_sql_syntax_denylist():
    """Verifies mutating statements are blocked."""
    # Blocked write operations
    assert SecurityValidator.validate_sql_ast("INSERT INTO users (name) VALUES ('John');") is False
    assert SecurityValidator.validate_sql_ast("UPDATE products SET price = 9.99 WHERE id = 1;") is False
    assert SecurityValidator.validate_sql_ast("DELETE FROM logs WHERE created_at < '2023-01-01';") is False
    assert SecurityValidator.validate_sql_ast("DROP TABLE customers;") is False
    assert SecurityValidator.validate_sql_ast("CREATE TABLE temp_data (id INT);") is False
    assert SecurityValidator.validate_sql_ast("ALTER TABLE users ADD COLUMN email TEXT;") is False
    
    # Blocked commands/pragmas
    assert SecurityValidator.validate_sql_ast("PRAGMA compile_options;") is False
    assert SecurityValidator.validate_sql_ast("ATTACH DATABASE 'other.db' AS other;") is False
    assert SecurityValidator.validate_sql_ast("DETACH DATABASE other;") is False

def test_is_safe_statement_raises():
    """Verifies is_safe_statement raises exception for unsafe queries."""
    with pytest.raises(SecurityValidationError):
        SecurityValidator.is_safe_statement("DELETE FROM products;")
        
    # Should not raise for safe queries
    assert SecurityValidator.is_safe_statement("SELECT COUNT(*) FROM products;") is True

