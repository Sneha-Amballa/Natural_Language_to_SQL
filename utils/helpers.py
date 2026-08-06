import os
import re
import json
from typing import Any, Union, Optional

def clean_file_path(path: str) -> str:
    """Normalizes path mapping syntax characters."""
    if not path:
        return ""
    path = path.strip('"' + "'")
    return os.path.normpath(path)

def detect_file_type(file_path: str) -> str:
    """Validates files extensions and magic bytes headers.
    
    Returns 'sqlite' or 'csv', or raises ValueError.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    _, ext = os.path.splitext(file_path.lower())
    
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
    except Exception as e:
        raise ValueError(f"Could not read file header: {e}") from e
        
    # SQLite check: magic byte header starts with b"SQLite format 3\x00"
    if header.startswith(b"SQLite format 3\x00"):
        if ext in (".db", ".sqlite", ".sqlite3"):
            return "sqlite"
        raise ValueError(f"File signature matches SQLite but extension '{ext}' is invalid.")
        
    # CSV check: must have .csv extension and be text-readable
    if ext == ".csv":
        try:
            # Verify if text decodable
            header.decode("utf-8")
            return "csv"
        except UnicodeDecodeError:
            try:
                header.decode("latin-1")
                return "csv"
            except Exception:
                raise ValueError("CSV file is not valid encoded text.")
        except Exception as e:
            raise ValueError(f"Invalid CSV structure: {e}") from e
            
    raise ValueError(f"Unsupported file format with extension '{ext}'. Only SQLite and CSV are allowed.")

def safe_json_load(text: str) -> Any:
    """Safely parses JSON string, returning None if parsing fails."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None

def safe_json_dump(obj: Any) -> str:
    """Safely serializes object to JSON string with default serializer for decimals/dates."""
    import decimal
    import datetime
    
    def default_serializer(o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        return str(o)
        
    try:
        return json.dumps(obj, default=default_serializer)
    except Exception:
        return "{}"

def snake_case(text: str) -> str:
    """Converts a string to snake_case."""
    if not text:
        return ""
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', text)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return re.sub(r'[^a-z0-9]+', '_', s2).strip('_')

def normalize_column_name(text: str) -> str:
    """Cleans up special character column maps to safe column names."""
    if not text:
        return "column"
    cleaned = snake_case(text)
    if cleaned and cleaned[0].isdigit():
        cleaned = "col_" + cleaned
    return cleaned if cleaned else "column"

def truncate_text(text: str, max_len: int = 100) -> str:
    """Truncates text string if it exceeds max length, adding ellipsis."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].strip() + "..."

def sanitize_filename(text: str) -> str:
    """Sanitizes filename strings, blocking directory traversal and special chars."""
    if not text:
        return "file"
    cleaned = os.path.basename(text)
    cleaned = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', cleaned)
    return cleaned if cleaned else "file"

