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
    page_title="Text-to-SQL Analytics Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium aesthetic custom styles
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        background: linear-gradient(135deg, #FF4B4B 0%, #852DF2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.6rem;
        margin-bottom: 0.2rem;
    }
    
    .main-subtitle {
        color: #8C96A8;
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
    }
    
    .status-connected {
        background-color: rgba(46, 204, 113, 0.15);
        color: #2ecc71;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        border: 1px solid rgba(46, 204, 113, 0.3);
    }
    
    .status-disconnected {
        background-color: rgba(231, 76, 60, 0.15);
        color: #e74c3c;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        border: 1px solid rgba(231, 76, 60, 0.3);
    }
    
    .card {
        background-color: #1E1E2F;
        border: 1px solid #2D2D44;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    }
    
    .card-title {
        font-weight: 700;
        font-size: 1.1rem;
        color: #E2E8F0;
        margin-bottom: 0.5rem;
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
st.markdown('<div class="main-title">📊 Text-to-SQL Analytics Copilot</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Secure, read-only natural language interface for SQLite databases and CSV files.</div>', unsafe_allow_html=True)

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
        "🤖 AI Analyst",
        "💻 Raw SQL Executor",
        "📊 Visualizations",
        "📋 Full Schema JSON"
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
