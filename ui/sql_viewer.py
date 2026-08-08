"""SQL Code and Editor View panel.

Renders raw code query interfaces and formatting tools.
"""

import streamlit as st
import pandas as pd
import traceback
from core.security import SecurityValidator, SecurityValidationError
from services.summary_service import SummaryService
from config import settings

def render_sql_code(sql: str) -> None:
    """Renders SQL statement blocks."""
    with st.expander("💻 Generated SQL Code"):
        st.code(sql, language="sql")

def render_sql_executor_tab() -> None:
    """Renders the Raw SQL Executor panel."""
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
            
            from ui.results import render_results_table
            render_results_table(df)
            
            # Recommendations
            st.markdown("---")
            col_vis, col_ins = st.columns(2)
            
            with col_vis:
                st.markdown("#### 📊 Recommended Visualization")
                from ui.charts import render_recommended_chart
                render_recommended_chart(df)
                    
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
