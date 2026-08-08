"""Sidebar Layout Panel.

Renders file uploader blocks and database status panels.
"""

import streamlit as st
import os
import time
import sqlite3
from core.database import DatabaseManager
from utils.csv_loader import CSVLoader
from ui.settings import render_api_key_settings

def render_sidebar(upload_dir: str, reset_db_callback, load_demo_db_callback) -> None:
    """Renders configuration sidebar."""
    st.sidebar.markdown(
        """
        <div style='margin-bottom: 2rem; display: flex; align-items: center; gap: 10px;'>
            <div style="background-color: #C08030; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 1.3rem; font-family: 'Playfair Display', serif;">R</div>
            <div>
                <h1 style='font-family: "Playfair Display", serif; font-weight: 700; font-size: 1.8rem; margin: 0; color: #1C1E1C; line-height: 1.1;'>Readout</h1>
                <div style='font-family: "Outfit", sans-serif; font-size: 0.65rem; font-weight: 600; letter-spacing: 1px; color: #7B817C; text-transform: uppercase;'>Text-to-SQL Copilot</div>
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Render settings input from ui/settings.py
    with st.sidebar:
        render_api_key_settings()
        
    # Session History persistence manager
    from services.history_service import SessionHistoryService
    history_service = SessionHistoryService()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.5rem; letter-spacing: 0.5px;'>SESSION</div>", unsafe_allow_html=True)
    
    # Ensure current session_id is initialized
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
        
    sessions = history_service.list_sessions()
    session_list = list(sessions)
    
    # Keep the active session_id strictly at index 0 of the selectbox options to prevent Streamlit widget shift race conditions
    if st.session_state.session_id in session_list:
        session_list.remove(st.session_state.session_id)
    session_list.insert(0, st.session_state.session_id)
        
    if "selected_session_key" not in st.session_state or st.session_state.selected_session_key != st.session_state.session_id:
        st.session_state.selected_session_key = st.session_state.session_id

    selected_sess = st.sidebar.selectbox(
        "Current Session ID",
        session_list,
        index=0,
        key="selected_session_key"
    )
    
    if selected_sess != st.session_state.session_id:
        st.session_state.session_id = selected_sess
        st.session_state.selected_session_key = selected_sess
        st.session_state.chat_history = history_service.load_session_raw(selected_sess)
        st.session_state.events = history_service.load_session_events(selected_sess)
        st.rerun()
        
    if st.sidebar.button("➕ Start New Session", help="Reset chat window and generate a new session ID"):
        import uuid
        new_sess_id = f"session_{uuid.uuid4().hex[:8]}"
        st.session_state.session_id = new_sess_id
        st.session_state.selected_session_key = new_sess_id
        st.session_state.chat_history = []
        st.session_state.events = []
        st.rerun()
        
    st.sidebar.markdown("---")
    
    # File Uploader
    uploaded_file = st.sidebar.file_uploader(
        "Upload Database / Dataset",
        type=["db", "sqlite", "sqlite3", "csv"],
        help="Accepts SQLite databases (.db/.sqlite) or CSV spreadsheets."
    )
    
    # Sample database loader button
    if st.sidebar.button("💡 Load Demo Sales DB", help="Generate and load a pre-populated Sales database."):
        load_demo_db_callback()
        st.session_state.loaded_filename = "demo_sales.db"
        st.rerun()
        
    # Process uploaded file
    if uploaded_file is not None:
        if "loaded_filename" not in st.session_state or st.session_state.loaded_filename != uploaded_file.name:
            from utils.helpers import sanitize_filename, validate_uploaded_file
            
            file_name = uploaded_file.name
            file_size = uploaded_file.size
            file_content_prefix = uploaded_file.getvalue()[:16]
            
            try:
                file_type = validate_uploaded_file(file_name, file_size, file_content_prefix)
                safe_name = sanitize_filename(file_name)
                temp_save_path = os.path.join(upload_dir, safe_name)
                
                with open(temp_save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                reset_db_callback()
                
                if file_type == "csv":
                    temp_db_path = os.path.join(upload_dir, f"temp_{int(time.time())}.db")
                    conn = sqlite3.connect(temp_db_path)
                    try:
                        table_name = os.path.splitext(safe_name)[0]
                        CSVLoader.import_csv(temp_save_path, conn, table_name)
                        st.session_state.db_path = temp_db_path
                        st.session_state.db_manager = DatabaseManager(temp_db_path)
                        st.session_state.is_temp_db = True
                        st.sidebar.success(f"CSV imported successfully into table `{table_name}`!")
                        st.session_state.loaded_filename = file_name
                    except Exception as e:
                        st.sidebar.error(f"Failed to import CSV: {e}")
                    finally:
                        conn.close()
                    if os.path.exists(temp_save_path):
                        os.remove(temp_save_path)
                else:
                    st.session_state.db_path = temp_save_path
                    st.session_state.db_manager = DatabaseManager(temp_save_path)
                    st.session_state.is_temp_db = False
                    st.sidebar.success("Database loaded successfully!")
                    st.session_state.loaded_filename = file_name
                    
            except ValueError as ve:
                st.sidebar.error(str(ve))
            except Exception as e:
                st.sidebar.error("Upload processing failed.")
                
    elif uploaded_file is None:
        if st.session_state.db_path and st.session_state.get("loaded_filename") != "demo_sales.db":
            reset_db_callback()
            st.session_state.loaded_filename = None
            st.rerun()
            
    # Connection status & Schema Explorer
    if st.session_state.db_manager:
        db_mgr = st.session_state.db_manager
        
        # Fetch size and row count for dataset card styling
        size_str = "0.0 KB"
        total_rows = 0
        try:
            if st.session_state.db_path and os.path.exists(st.session_state.db_path):
                size_bytes = os.path.getsize(st.session_state.db_path)
                if size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024*1024):.1f} MB"
                else:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                    
            tables = db_mgr.get_table_list()
            for t in tables:
                res = db_mgr.execute_raw(f"SELECT COUNT(*) FROM {t};")
                total_rows += res.rows[0][0]
        except Exception:
            pass
            
        filename = st.session_state.loaded_filename or "Loaded DB"
        # Display dataset details card
        st.sidebar.markdown(
            f"""
            <div style='margin-top: 1.5rem; margin-bottom: 1.5rem;'>
                <div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.5rem; letter-spacing: 0.5px;'>DATASET</div>
                <div class="card" style="padding: 0.75rem; border-radius: 8px; border: 1px solid #E4E4DC; background-color: #FFFFFF;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 1.5rem;">📄</span>
                        <div>
                            <div style="font-weight: 600; font-size: 0.9rem; color: #1C1E1C; word-break: break-all;">{filename}</div>
                            <div style="font-size: 0.75rem; color: #7B817C;">{size_str} &middot; {total_rows:,} rows</div>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        try:
            tables = db_mgr.get_table_list()
            st.sidebar.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-top: 1.5rem; margin-bottom: 0.5rem; letter-spacing: 0.5px;'>SCHEMA EXPLORER</div>", unsafe_allow_html=True)
            
            for table in tables:
                with st.sidebar.expander(f"📁 {table}"):
                    meta = db_mgr.get_schema_metadata(table)
                    for col in meta["columns"]:
                        icons = ""
                        if col["is_primary"]:
                            icons += " 🔑"
                        if col["foreign_reference"]:
                            icons += " 🔗"
                        st.markdown(f"**{col['name']}** *({col['type']})*{icons}")
                        if col["foreign_reference"]:
                            ref = col["foreign_reference"]
                            st.markdown(f"<span style='color:#8C96A8; font-size:0.8rem;'>→ {ref['table']}.{ref['column']}</span>", unsafe_allow_html=True)
        except Exception as e:
            st.sidebar.error(f"Error exploring schema: {e}")
            
        if st.sidebar.button("❌ Close Connection"):
            reset_db_callback()
            st.session_state.loaded_filename = None
            st.rerun()
    else:
        st.sidebar.markdown('<div class="status-disconnected">○ Disconnected</div>', unsafe_allow_html=True)
