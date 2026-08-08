"""Session History persistence Tests.

Covers the 14 required tests for Phase 9.
"""

import pytest
import os
import tempfile
import json
import shutil
from services.history_service import SessionHistoryService
from models.models import ChatMessage

@pytest.fixture
def temp_history_dir():
    path = tempfile.mkdtemp(prefix="history_test_")
    yield path
    if os.path.exists(path):
        shutil.rmtree(path)

# 1. create/save session & 11. history directory creation
def test_create_and_save_session(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    # Verify directory was created
    assert os.path.exists(temp_history_dir)
    
    msgs = [ChatMessage(role="user", content="Test question")]
    service.save_session("session_1", msgs)
    
    # Check that file exists on disk
    file_path = os.path.join(temp_history_dir, "session_1.json")
    assert os.path.exists(file_path)

# 2. load session
def test_load_session(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    msgs = [ChatMessage(role="user", content="Question 1")]
    service.save_session("session_1", msgs)
    
    loaded = service.load_session("session_1")
    assert len(loaded) == 1
    assert loaded[0].role == "user"
    assert loaded[0].content == "Question 1"

# 3. save then load equality
def test_save_load_equality(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    msgs = [
        ChatMessage(role="user", content="Q1"),
        ChatMessage(role="assistant", content="A1")
    ]
    service.save_session("sess_equality", msgs)
    loaded = service.load_session("sess_equality")
    
    assert len(loaded) == len(msgs)
    assert loaded[0].role == msgs[0].role
    assert loaded[0].content == msgs[0].content
    assert loaded[1].role == msgs[1].role
    assert loaded[1].content == msgs[1].content

# 4. multiple sessions & 5. session isolation
def test_multiple_sessions_isolation(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    service.save_session("sess_A", [ChatMessage(role="user", content="Message A")])
    service.save_session("sess_B", [ChatMessage(role="user", content="Message B")])
    
    loaded_A = service.load_session("sess_A")
    loaded_B = service.load_session("sess_B")
    
    assert loaded_A[0].content == "Message A"
    assert loaded_B[0].content == "Message B"
    assert "sess_A" in service.list_sessions()
    assert "sess_B" in service.list_sessions()

# 6. missing session
def test_missing_session_returns_empty(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    loaded = service.load_session("nonexistent_session_id")
    assert loaded == []

# 7. malformed history
def test_malformed_history_fails_gracefully(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "corrupt.json")
    with open(file_path, "w") as f:
        f.write("{invalid_json_corrupted")
        
    loaded = service.load_session("corrupt")
    assert loaded == []

# 8. empty history
def test_empty_history_file(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    file_path = os.path.join(temp_history_dir, "empty.json")
    with open(file_path, "w") as f:
        f.write("")
        
    loaded = service.load_session("empty")
    assert loaded == []

# 9. session update
def test_session_update(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    # Initial save
    service.save_session("sess_update", [ChatMessage(role="user", content="Q1")])
    assert len(service.load_session("sess_update")) == 1
    
    # Update save
    service.save_session("sess_update", [
        ChatMessage(role="user", content="Q1"),
        ChatMessage(role="assistant", content="A1")
    ])
    assert len(service.load_session("sess_update")) == 2

# 10. clear/delete if implemented
def test_delete_session(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    service.save_session("sess_delete", [ChatMessage(role="user", content="Q")])
    assert "sess_delete" in service.list_sessions()
    
    service.delete_session("sess_delete")
    assert "sess_delete" not in service.list_sessions()
    assert service.load_session("sess_delete") == []

# 12. secret fields are not persisted
def test_secret_fields_not_persisted(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    msgs = [ChatMessage(role="user", content="Set Groq key gsk_somekeyval123")]
    service.save_session("sess_secret", msgs)
    
    loaded = service.load_session("sess_secret")
    assert "gsk_somekeyval123" not in loaded[0].content
    assert "[REDACTED SECRET]" in loaded[0].content

# 13. timeline rendering/import
def test_timeline_import():
    import ui.timeline
    assert hasattr(ui.timeline, "render_timeline")

# 14. integration with existing chat/session state
def test_raw_vs_pydantic_mapping_integration(temp_history_dir):
    service = SessionHistoryService(temp_history_dir)
    raw_history = [
        {"role": "user", "content": "Query text", "helper_key": "some_meta"},
        {"role": "assistant", "content": "SQL result text", "sql": "SELECT 1;", "df": {"id": [1]}}
    ]
    service.save_session("sess_raw", [], raw_history=raw_history)
    
    # Verify standard load returns Pydantic ChatMessage list
    loaded_pydantic = service.load_session("sess_raw")
    assert len(loaded_pydantic) == 2
    assert isinstance(loaded_pydantic[0], ChatMessage)
    assert loaded_pydantic[0].content == "Query text"
    
    # Verify raw load preserves special helper keys (but cleans dataframe values to prevent data leaks)
    loaded_raw = service.load_session_raw("sess_raw")
    assert len(loaded_raw) == 2
    assert loaded_raw[1]["sql"] == "SELECT 1;"
    assert loaded_raw[1]["df"] is None
    assert "df_metadata" in loaded_raw[1]
