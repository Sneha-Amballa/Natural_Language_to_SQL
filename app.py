import streamlit as st
import os
import time
import sqlite3

import pandas as pd
import json
import traceback
import shutil
from config import settings
from core.database import DatabaseManager
from core.security import SecurityValidator
from core.exceptions import SecurityValidationError
from agent.orchestrator import SQLAgent

from services.summary_service import SummaryService
from services.visualization_service import VisualizationService
from utils.csv_loader import CSVLoader
from utils.parser import MarkdownParser
from models.models import QueryResult

# Define upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# Page configuration
st.set_page_config(
    page_title="Readout - Text-to-SQL Analytics Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium aesthetic custom styles
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap');
    
    /* App-wide background and font resets */
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        background-color: #F8F8F6 !important;
        font-family: 'Outfit', sans-serif !important;
        color: #1C1E1C !important;
    }
    
    /* Sidebar compact design */
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div {
        background-color: #F1F1EC !important;
        border-right: 1px solid #E4E4DC !important;
    }
    [data-testid="stSidebar"] {
        min-width: 260px !important;
        max-width: 260px !important;
    }
    
    /* Sidebar text colors */
    [data-testid="stSidebar"] [class*="css"], [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
        color: #2D312E !important;
    }
    
    /* Center main content container like ChatGPT */
    [data-testid="stAppViewContainer"] [data-testid="stMainFrame"] .block-container {
        max-width: 800px !important;
        margin: 0 auto !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    
    /* Center title and subtitle */
    .main-title {
        font-family: 'Playfair Display', serif !important;
        font-weight: 700;
        font-size: 2.8rem;
        color: #1C1E1C !important;
        margin-bottom: 0.1rem;
        margin-top: 1rem;
        line-height: 1.2;
        text-align: center !important;
    }
    
    .main-subtitle {
        font-family: 'Playfair Display', serif !important;
        font-style: italic;
        color: #C08030 !important;
        font-size: 2.0rem;
        margin-top: 0.1rem;
        margin-bottom: 1rem;
        font-weight: 400;
        text-align: center !important;
    }
    
    .main-description {
        color: #555A56;
        font-size: 1.05rem;
        margin-bottom: 2rem;
        max-width: 800px;
        line-height: 1.5;
        text-align: center !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    
    /* Streamlit tabs overrides to make them pills */
    button[data-baseweb="tab"] {
        font-family: 'Outfit', sans-serif !important;
        background-color: #EFEFED !important;
        color: #555A56 !important;
        border: 1px solid #E2E2D9 !important;
        border-radius: 8px !important;
        padding: 0.4rem 1rem !important;
        margin-right: 0.5rem !important;
        transition: all 0.2s ease-in-out !important;
        font-weight: 500 !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #1C1E1C !important;
        border: 1px solid #C08030 !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05) !important;
        font-weight: 600 !important;
    }
    
    /* macOS-style code editor panel styling */
    .mac-editor-frame {
        background-color: #FDFDFD;
        border: 1px solid #E2E2D9;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
        margin-bottom: 1.5rem;
        overflow: hidden;
    }
    
    .mac-editor-header {
        background-color: #F2F2EC;
        border-bottom: 1px solid #E2E2D9;
        padding: 0.6rem 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .mac-dots {
        display: flex;
        gap: 6px;
    }
    
    .mac-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
    }
    .mac-dot.red { background-color: #FF5F56; }
    .mac-dot.yellow { background-color: #FFBD2E; }
    .mac-dot.green { background-color: #27C93F; }
    
    .mac-filename {
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #7B817C;
        font-weight: 600;
    }
    
    /* Cards and metrics containers styling */
    .card {
        background-color: #FFFFFF !important;
        border: 1px solid #E4E4DC !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02) !important;
    }
    
    .card-title {
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        color: #1C1E1C !important;
        margin-bottom: 0.5rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Play/Run action button styling */
    .stButton>button {
        border-radius: 20px !important;
        background-color: #FFFFFF !important;
        color: #1C1E1C !important;
        border: 1px solid #C08030 !important;
        padding: 0.35rem 1.2rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton>button:hover {
        background-color: #C08030 !important;
        color: #FFFFFF !important;
        border-color: #C08030 !important;
        box-shadow: 0 4px 10px rgba(192, 128, 48, 0.2) !important;
    }
    
    /* Connect status tags */
    .status-connected {
        background-color: rgba(46, 204, 113, 0.12) !important;
        color: #27ae60 !important;
        padding: 0.3rem 0.75rem !important;
        border-radius: 20px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        display: inline-block !important;
        border: 1px solid rgba(46, 204, 113, 0.25) !important;
    }
    
    .status-disconnected {
        background-color: rgba(231, 76, 60, 0.12) !important;
        color: #c0392b !important;
        padding: 0.3rem 0.75rem !important;
        border-radius: 20px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        display: inline-block !important;
        border: 1px solid rgba(231, 76, 60, 0.25) !important;
    }
    
    /* Scrollable chat style message box adjustment */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E4E4DC !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.01) !important;
    }
    
    /* Connect mac-editor-frame header with st.code block and st.text_area */
    .mac-editor-frame + div.element-container pre, 
    .mac-editor-frame + div[data-testid="element-container"] pre,
    .mac-editor-frame + pre,
    .mac-editor-frame + div.element-container textarea, 
    .mac-editor-frame + div[data-testid="element-container"] textarea,
    .mac-editor-frame + textarea {
        border-top-left-radius: 0px !important;
        border-top-right-radius: 0px !important;
        margin-top: -1.5rem !important;
        border-top: none !important;
        background-color: #FAFAF9 !important;
        border: 1px solid #E2E2D9 !important;
    }
    
    /* Fit everything in one screen with fixed layout */
    [data-testid="stAppViewContainer"], .stApp {
        height: 100vh !important;
        overflow: hidden !important;
    }
    
    /* Pinned question input box layout & Scrollable messages */
    .chat-container-wrapper div[data-testid="stVerticalBlock"] {
        height: calc(100vh - 350px) !important;
        max-height: calc(100vh - 350px) !important;
        overflow-y: auto !important;
        padding-right: 5px;
    }
    
    /* Custom thin scrollbar for chat container */
    .chat-container-wrapper div[data-testid="stVerticalBlock"]::-webkit-scrollbar {
        width: 6px;
    }
    .chat-container-wrapper div[data-testid="stVerticalBlock"]::-webkit-scrollbar-thumb {
        background-color: #E4E4DC;
        border-radius: 3px;
    }
    
    /* Floating rounded ChatGPT-style query box */
    [data-testid="stChatInput"] {
        max-width: 800px !important;
        margin: 0 auto !important;
        border-radius: 26px !important;
        border: 1px solid #E4E4DC !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05) !important;
        bottom: 24px !important;
        padding: 0.2rem 0.5rem !important;
    }
    [data-testid="stChatInput"] textarea {
        border: none !important;
        background-color: transparent !important;
        color: #1C1E1C !important;
        border-radius: 26px !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to create sample database
def create_sample_db(path: str):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            country TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT,
            category TEXT,
            price REAL,
            stock INTEGER
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            sale_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            sale_date TEXT,
            total_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)
    
    # Check if empty, insert mock data
    cursor.execute("SELECT COUNT(*) FROM customers;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO customers (customer_id, first_name, last_name, email, country)
            VALUES (?, ?, ?, ?, ?);
        """, [
            (1, "Alice", "Smith", "alice@example.com", "USA"),
            (2, "Bob", "Jones", "bob@example.com", "Canada"),
            (3, "Charlie", "Brown", "charlie@example.com", "UK"),
            (4, "Diana", "Prince", "diana@example.com", "USA"),
            (5, "Evan", "Wright", "evan@example.com", "Australia")
        ])
        
        cursor.executemany("""
            INSERT INTO products (product_id, product_name, category, price, stock)
            VALUES (?, ?, ?, ?, ?);
        """, [
            (101, "Laptop", "Electronics", 999.99, 15),
            (102, "Smartphone", "Electronics", 699.50, 30),
            (103, "Coffee Maker", "Appliances", 89.90, 50),
            (104, "Desk Chair", "Furniture", 149.00, 20),
            (105, "Running Shoes", "Apparel", 79.99, 100)
        ])
        
        cursor.executemany("""
            INSERT INTO sales (sale_id, customer_id, product_id, quantity, sale_date, total_amount)
            VALUES (?, ?, ?, ?, ?, ?);
        """, [
            (1, 1, 101, 1, "2026-07-01", 999.99),
            (2, 2, 103, 2, "2026-07-02", 179.80),
            (3, 3, 105, 1, "2026-07-03", 79.99),
            (4, 4, 102, 1, "2026-07-04", 699.50),
            (5, 5, 104, 1, "2026-07-05", 149.00),
            (6, 1, 103, 1, "2026-07-06", 89.90),
            (7, 3, 102, 2, "2026-07-07", 1399.00)
        ])
        
    conn.commit()
    conn.close()

# Cleanup database session states
def reset_database_state():
    from utils.cache import cache_schema
    cache_schema().clear()
    if "is_temp_db" in st.session_state and st.session_state.is_temp_db:
        if "db_path" in st.session_state and st.session_state.db_path:
            if os.path.exists(st.session_state.db_path):
                try:
                    os.remove(st.session_state.db_path)
                except Exception:
                    pass
    st.session_state.db_path = None
    st.session_state.db_manager = None
    st.session_state.is_temp_db = False
    st.session_state.schema_metadata = {}
    st.session_state.chat_history = []
    st.session_state.loaded_filename = None
    import uuid
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
    st.session_state.events = []

# Initialize state keys
if "db_path" not in st.session_state:
    st.session_state.db_path = None
if "db_manager" not in st.session_state:
    st.session_state.db_manager = None
if "is_temp_db" not in st.session_state:
    st.session_state.is_temp_db = False
if "schema_metadata" not in st.session_state:
    st.session_state.schema_metadata = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "loaded_filename" not in st.session_state:
    st.session_state.loaded_filename = None
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
if "events" not in st.session_state:
    st.session_state.events = []

# Sidebar Controls
from ui.sidebar import render_sidebar

def load_demo_db():
    reset_database_state()
    sample_path = os.path.join(UPLOAD_DIR, "demo_sales.db")
    create_sample_db(sample_path)
    st.session_state.db_path = sample_path
    st.session_state.db_manager = DatabaseManager(sample_path)
    st.session_state.is_temp_db = False
    st.success("Demo Sales Database Loaded!")

render_sidebar(
    upload_dir=UPLOAD_DIR,
    reset_db_callback=reset_database_state,
    load_demo_db_callback=load_demo_db
)

# Main Workspace Layout
st.markdown('<div class="main-title">Ask your data anything.</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Get the query, the read, the chart.</div>', unsafe_allow_html=True)
st.markdown('<div class="main-description">A secure, natural-language interface for exploring your database — every answer shows its work, so you can trust the SQL before you trust the result.</div>', unsafe_allow_html=True)

if not st.session_state.db_manager:
    # Welcome banner and details when no database is loaded
    st.info("👋 Welcome! Please upload a `.db` / `.sqlite` database, load a `.csv` spreadsheet, or load our pre-configured Demo Sales Database in the sidebar to get started.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="card">
            <div class="card-title">📁 1. Load Data</div>
            Upload an existing SQLite file, import a CSV, or load the built-in Sales Database instantly.
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="card">
            <div class="card-title">💬 2. Query in Plain Text</div>
            Ask the AI Analyst to pull statistics, filter information, or join multiple tables using natural English.
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="card">
            <div class="card-title">🛡️ 3. Safe Execution</div>
            Query execution is restricted to read-only transactions, backed by Abstract Syntax Tree (AST) validation.
        </div>
        """, unsafe_allow_html=True)
        
else:
    # Database is loaded! Display the workspace Tabs
    tab_chat, tab_sql, tab_visuals, tab_schema = st.tabs([
        "Ask",
        "SQL Editor",
        "Visualizations",
        "Schema"
    ])
    
    # ------------------ TAB 1: AI Chat Analyst ------------------
    with tab_chat:
        from ui.chat import render_chat_tab
        render_chat_tab()
        
    # ------------------ TAB 2: Direct SQL Executor ------------------
    with tab_sql:
        from ui.sql_viewer import render_sql_executor_tab
        render_sql_executor_tab()
        
    # ------------------ TAB 3: Visualization Center ------------------
    with tab_visuals:
        from ui.charts import render_visualizations_tab
        render_visualizations_tab()

    # ------------------ TAB 4: Raw Schema Metadata ------------------
    with tab_schema:
        st.markdown("### 📋 Cached Schema Definition")
        schema_json = {}
        try:
            tables = st.session_state.db_manager.get_table_list()
            for table in tables:
                try:
                    schema_json[table] = st.session_state.db_manager.get_schema_metadata(table)
                except Exception:
                    pass
        except Exception as e:
            st.error(f"Failed to fetch table list: {e}")
        st.json(schema_json)
