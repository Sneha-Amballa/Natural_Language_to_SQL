"""File Upload Security Hardening Tests.

Covers the 12 test cases required by Phase 6.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from utils.helpers import validate_uploaded_file, sanitize_filename
from utils.csv_loader import CSVLoader
import sqlite3

# TEST 1: valid SQLite upload
def test_valid_sqlite_upload():
    # SQLite signature with correct extension
    res = validate_uploaded_file("test.db", 100, b"SQLite format 3\x00\x00\x00")
    assert res == "sqlite"

# TEST 2: valid CSV upload
def test_valid_csv_upload():
    # Valid CSV extension and text-decodable bytes
    res = validate_uploaded_file("test.csv", 100, b"id,name\n1,Alice")
    assert res == "csv"

# TEST 3: oversized upload rejected
def test_oversized_upload_rejected():
    from config import settings
    # 51MB (limit is 50MB)
    oversized_bytes = (settings.MAX_UPLOAD_SIZE_MB + 1) * 1024 * 1024
    with pytest.raises(ValueError) as excinfo:
        validate_uploaded_file("test.db", oversized_bytes, b"SQLite format 3\x00\x00\x00")
    assert "exceeds the maximum" in str(excinfo.value)

# TEST 4: valid upload at allowed size
def test_valid_upload_at_allowed_size():
    from config import settings
    # Exactly at limit (50MB)
    exact_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    res = validate_uploaded_file("test.db", exact_bytes, b"SQLite format 3\x00\x00\x00")
    assert res == "sqlite"

# TEST 5: invalid SQLite signature rejected
def test_invalid_sqlite_signature_rejected():
    with pytest.raises(ValueError) as excinfo:
        # DB extension but arbitrary binary headers instead of SQLite Format 3 signature
        validate_uploaded_file("test.db", 100, b"ArbitraryBinaryData")
    assert "not a valid SQLite database" in str(excinfo.value)

# TEST 6: renamed binary file rejected
def test_renamed_binary_file_rejected():
    with pytest.raises(ValueError) as excinfo:
        # Renamed EXE/ELF to CSV
        validate_uploaded_file("test.csv", 100, b"\x7fELF\x02\x01\x01\x00\x00\x00")
    assert "could not be parsed as a valid CSV" in str(excinfo.value)

# TEST 7: malformed CSV handled safely
def test_malformed_csv_handled_safely():
    # Verify that a malformed CSV with non-decodable bytes raises ValueErrors
    with pytest.raises(ValueError) as excinfo:
        validate_uploaded_file("test.csv", 100, b"\x80\x81\x82\x83\x84")
    assert "could not be parsed as a valid CSV" in str(excinfo.value)

# TEST 8: empty CSV handled according to existing application behavior
def test_empty_csv_handled(tmp_path):
    # CSVLoader should fail gracefully or catch empty dataset errors on actual import
    temp_csv = tmp_path / "empty.csv"
    temp_csv.write_text("")
    
    temp_db = tmp_path / "temp.db"
    conn = sqlite3.connect(temp_db)
    
    with pytest.raises(Exception): # pd.read_csv raises EmptyDataError on empty files
        CSVLoader.import_csv(str(temp_csv), conn, "empty_table")
    conn.close()

# TEST 9: path traversal filename rejected/sanitized
def test_path_traversal_filename_sanitized():
    # sanitize_filename should strip directory separators and path traversal sequences
    traversal_name = "../../dangerous_file.db"
    safe_name = sanitize_filename(traversal_name)
    assert safe_name == "dangerous_file.db"
    assert ".." not in safe_name

# TEST 10: absolute path filename rejected/sanitized
def test_absolute_path_filename_sanitized():
    # sanitize_filename should strip drive letters and leading separators
    absolute_name = "/etc/passwd"
    safe_name = sanitize_filename(absolute_name)
    assert safe_name == "passwd"
    
    absolute_win = "C:\\Windows\\System32\\cmd.exe"
    safe_win = sanitize_filename(absolute_win)
    assert safe_win == "cmd.exe"

# TEST 11: unsupported file type rejected
def test_unsupported_file_type_rejected():
    with pytest.raises(ValueError) as excinfo:
        validate_uploaded_file("exploit.exe", 100, b"\x4d\x5a\x90\x00")
    assert "Unsupported file format" in str(excinfo.value)

# TEST 12: existing valid uploads continue working
def test_existing_valid_uploads_continue_working():
    # Checks that normal files are parsed without errors
    db_res = validate_uploaded_file("my_sales.sqlite", 500, b"SQLite format 3\x00")
    assert db_res == "sqlite"
    
    csv_res = validate_uploaded_file("my_data.csv", 200, b"name,age,country\nAlice,30,USA")
    assert csv_res == "csv"
