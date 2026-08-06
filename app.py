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

# Sidebar Controls
st.sidebar.markdown("<h2 style='font-weight:800; font-size:1.5rem;'>⚙️ Configuration</h2>", unsafe_allow_html=True)

# API Key override
api_key_input = st.sidebar.text_input("Groq API Key Override", type="password", help="Use this input to supply your Groq API Key if not set in .env")
if api_key_input:
    os.environ["GROQ_API_KEY"] = api_key_input
    # Clear settings cache if required, or simply override env
    #settings.GROQ_API_KEY = SecretStr(api_key_input)

# File Uploader
uploaded_file = st.sidebar.file_uploader(
    "Upload Database / Dataset",
    type=["db", "sqlite", "sqlite3", "csv"],
    help="Accepts SQLite databases (.db/.sqlite) or CSV spreadsheets."
)

# Sample database loader button
if st.sidebar.button("💡 Load Demo Sales DB", help="Generate and load a pre-populated Sales database."):
    reset_database_state()
    sample_path = os.path.join(UPLOAD_DIR, "demo_sales.db")
    create_sample_db(sample_path)
    st.session_state.db_path = sample_path
    st.session_state.db_manager = DatabaseManager(sample_path)
    st.session_state.is_temp_db = False
    st.success("Demo Sales Database Loaded!")

# Process uploaded file
if uploaded_file is not None:
    # Check if this file is different from current db_path to prevent reset loop
    file_name = uploaded_file.name
    temp_save_path = os.path.join(UPLOAD_DIR, file_name)
    
    # Save uploaded file
    with open(temp_save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    if st.session_state.db_path != temp_save_path:
        reset_database_state()
        
        if file_name.endswith(".csv"):
            # Import CSV into a temporary sqlite db
            temp_db_path = os.path.join(UPLOAD_DIR, f"temp_{int(time.time())}.db")
            conn = sqlite3.connect(temp_db_path)
            try:
                table_name = os.path.splitext(file_name)[0]
                CSVLoader.import_csv(temp_save_path, conn, table_name)
                st.session_state.db_path = temp_db_path
                st.session_state.db_manager = DatabaseManager(temp_db_path)
                st.session_state.is_temp_db = True
                st.sidebar.success(f"CSV imported successfully into table `{table_name}`!")
            except Exception as e:
                st.sidebar.error(f"Failed to import CSV: {e}")
            finally:
                conn.close()
            # Clean up CSV save file
            if os.path.exists(temp_save_path):
                os.remove(temp_save_path)
        else:
            # SQLite DB loaded
            st.session_state.db_path = temp_save_path
            st.session_state.db_manager = DatabaseManager(temp_save_path)
            st.session_state.is_temp_db = False
            st.sidebar.success("Database loaded successfully!")

# Connection status
if st.session_state.db_manager:
    st.sidebar.markdown('<div class="status-connected">● Connected</div>', unsafe_allow_html=True)
    db_mgr = st.session_state.db_manager
    
    # Schema Explorer in sidebar
    try:
        tables = db_mgr.get_table_list()
        st.sidebar.markdown("<h3 style='margin-top:1.5rem; font-weight:700; font-size:1.1rem;'>🗺️ Schema Explorer</h3>", unsafe_allow_html=True)
        
        for table in tables:
            with st.sidebar.expander(f"📁 {table}"):
                meta = db_mgr.get_schema_metadata(table)
                # Show columns
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
        reset_database_state()
        st.experimental_rerun()
else:
    st.sidebar.markdown('<div class="status-disconnected">○ Disconnected</div>', unsafe_allow_html=True)

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
        "💬 AI Analyst",
        "💻 Raw SQL Executor",
        "📊 Visualizations",
        "📋 Full Schema JSON"
    ])
    
    # Retrieve schemas list
    tables = st.session_state.db_manager.get_table_list()
    
    # ------------------ TAB 1: AI Chat Analyst ------------------
    with tab_chat:
        # Prompt warnings for API key
        groq_api_key_check = os.environ.get("GROQ_API_KEY", "") or settings.GROQ_API_KEY.get_secret_value()
        if not groq_api_key_check or groq_api_key_check.startswith("placeholder"):
            st.warning("⚠️ Warning: Groq API Key is not set. Please supply your API Key in the sidebar or update your `.env` file to chat with the AI Analyst.")
            
        # Display chat messages
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if "sql" in msg and msg["sql"]:
                    with st.expander("💻 Generated SQL Code"):
                        st.code(msg["sql"], language="sql")
                if "df" in msg and msg["df"] is not None:
                    # Convert dict back to df
                    df = pd.DataFrame(msg["df"])
                    st.dataframe(df)
                    
        # Chat input
        user_prompt = st.chat_input("Ask the AI Analyst a question...")
        if user_prompt:
            # Display user prompt
            with st.chat_message("user"):
                st.write(user_prompt)
                
            # Add to history
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            
            # Run Agent
            with st.chat_message("assistant"):
                with st.status("AI Analyst is thinking...") as status_block:
                    try:
                        agent = SQLAgent(st.session_state.db_path)
                        # Sync past memory history to agent's memory
                        # (ignoring system/meta to prevent duplication)
                        for hist in st.session_state.chat_history[:-1]:
                            agent.memory.add_message(hist["role"], hist["content"])
                            
                        # Execute
                        response = agent.execute(user_prompt)
                        
                        # Render logs in status block
                        for step in response.steps:
                            st.write(f"**Step {step['step']}:** Called `{step['tool_called']}` ({step['duration_ms']:.1f}ms) -> *{step['status']}*")
                            if step["status"] == "FAILED":
                                st.error(f"Error: {step['result']}")
                                
                        status_block.update(label="Analysis Completed!", state="complete")
                    except Exception as e:
                        status_block.update(label="Analysis Failed", state="error")
                        st.error(f"Error running agent loop: {e}")
                        traceback.print_exc()
                        response = None
                        
                if response:
                    # Print response content
                    st.write(response.response_text)
                    
                    # Check if SQL was executed
                    df_res = None
                    if response.sql_query:
                        with st.expander("💻 Generated SQL Code"):
                            st.code(response.sql_query, language="sql")
                            
                        # Query execution to get DataFrame
                        try:
                            # Safely fetch dataframe
                            query_res = st.session_state.db_manager.execute_raw(response.sql_query)
                            df_res = pd.DataFrame(query_res.rows, columns=query_res.columns)
                            st.dataframe(df_res)
                            
                            # Provide download button
                            csv_data = df_res.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                "📥 Download CSV",
                                data=csv_data,
                                file_name="query_results.csv",
                                mime="text/csv"
                            )
                        except Exception as q_err:
                            st.error(f"Failed to load dataset: {q_err}")
                            
                    # Add assistant response to history
                    hist_entry = {
                        "role": "assistant",
                        "content": response.response_text,
                        "sql": response.sql_query,
                        "df": df_res.to_dict(orient="list") if df_res is not None else None
                    }
                    st.session_state.chat_history.append(hist_entry)
                    st.rerun()

                    
    # ------------------ TAB 2: Direct SQL Executor ------------------
    with tab_sql:
        st.markdown("### 💻 Direct SQL Editor")
        sql_input = st.text_area("Type your SELECT query here:", value="SELECT * FROM sqlite_master LIMIT 5;", height=150)
        
        col_exec, col_clear = st.columns([1, 8])
        exec_clicked = col_exec.button("⚡ Run Query", type="primary")
        
        if exec_clicked and sql_input:
            try:
                # AST Safety check
                SecurityValidator.is_safe_statement(sql_input)
                
                # Execute Raw Query
                with st.spinner("Executing SQL query..."):
                    res = st.session_state.db_manager.execute_raw(sql_input, timeout=settings.SQL_TIMEOUT_SEC)
                    df = pd.DataFrame(res.rows, columns=res.columns)
                    
                st.success(f"Query executed successfully in {res.execution_time_ms:.1f}ms! Loaded {res.row_count} rows.")
                st.dataframe(df)
                
                # Download button
                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Results CSV",
                    data=csv_data,
                    file_name="executor_results.csv",
                    mime="text/csv"
                )
                
                # Recommendations
                st.markdown("---")
                col_vis, col_ins = st.columns(2)
                
                with col_vis:
                    st.markdown("#### 📊 Recommended Visualization")
                    vis_service = VisualizationService()
                    rec = vis_service.get_recommendation(df)
                    if rec.should_render:
                        if rec.chart_type == "line":
                            st.line_chart(df, x=rec.x_axis, y=rec.y_axis)
                        elif rec.chart_type == "bar":
                            st.bar_chart(df, x=rec.x_axis, y=rec.y_axis)
                        elif rec.chart_type == "scatter":
                            st.scatter_chart(df, x=rec.x_axis, y=rec.y_axis)
                        st.caption(f"Suggested {rec.chart_type.capitalize()} Chart: {rec.x_axis} vs {rec.y_axis}")
                    else:
                        st.info("No visualization recommended for this dataset.")
                        
                with col_ins:
                    st.markdown("#### 💡 Executive Highlights")
                    summary_service = SummaryService()
                    summary = summary_service.summarize_results(df, context_prompt=sql_input)
                    st.write(summary.insights)
                    for item in summary.key_takeaways:
                        st.markdown(f"- {item}")
                        
            except SecurityValidationError as sec_err:
                st.error(f"🛡️ Security Block: {sec_err}")
            except Exception as e:
                st.error(f"❌ Execution Error: {e}")
                traceback.print_exc()

    # ------------------ TAB 3: Visualization Center ------------------
    with tab_visuals:
        st.markdown("### 📊 Visualizations Dashboard")
        st.info("Run a query in the Direct SQL Editor or chat with the AI Analyst to generate tables. This tab automatically renders graphs based on the last executed query results.")
        
        # Pull last run result
        last_df = None
        last_sql = ""
        # Check if chat history or executor has data
        if st.session_state.chat_history:
            last_msg = st.session_state.chat_history[-1]
            if last_msg.get("df") is not None:
                last_df = pd.DataFrame(last_msg["df"])
                last_sql = last_msg.get("sql", "Chat Query")
                
        if last_df is not None:
            st.markdown(f"**Visualizing results for:** `{last_sql}`")
            
            # Recommend chart
            vis_service = VisualizationService()
            rec = vis_service.get_recommendation(last_df)
            
            if rec.should_render:
                chart_option = st.selectbox("Select Chart Type", ["Recommended", "Bar", "Line", "Scatter"])
                
                x_axis = st.selectbox("X-Axis Column", last_df.columns, index=list(last_df.columns).index(rec.x_axis) if rec.x_axis in last_df.columns else 0)
                y_axis = st.selectbox("Y-Axis Column", last_df.columns, index=list(last_df.columns).index(rec.y_axis) if rec.y_axis in last_df.columns else 0)
                
                type_sel = rec.chart_type if chart_option == "Recommended" else chart_option.lower()
                
                if type_sel == "line":
                    st.line_chart(last_df, x=x_axis, y=y_axis)
                elif type_sel == "bar":
                    st.bar_chart(last_df, x=x_axis, y=y_axis)
                elif type_sel == "scatter":
                    st.scatter_chart(last_df, x=x_axis, y=y_axis)
            else:
                st.warning("Current dataset structure doesn't support automatic visualizations. Try executing a query returning multiple numerical or chronological values.")
        else:
            st.info("No active query dataset loaded yet. Please run a query first!")

    # ------------------ TAB 4: Raw Schema Metadata ------------------
    with tab_schema:
        st.markdown("### 📋 Cached Schema Definition")
        schema_json = {}
        for table in tables:
            try:
                schema_json[table] = db_mgr.get_schema_metadata(table)
            except Exception:
                pass
        st.json(schema_json)
