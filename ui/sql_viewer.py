"""SQL Code and Editor View panel.

Renders raw code query interfaces and formatting tools.
"""

import streamlit as st
import pandas as pd
import traceback
import os
from core.security import SecurityValidator, SecurityValidationError
from services.summary_service import SummaryService
from config import settings

def render_sql_code(sql: str) -> None:
    """Renders SQL statement blocks in a macOS-style code editor."""
    st.markdown(
        """
        <div class="mac-editor-frame">
            <div class="mac-editor-header">
                <div class="mac-dots">
                    <div class="mac-dot red"></div>
                    <div class="mac-dot yellow"></div>
                    <div class="mac-dot green"></div>
                </div>
                <div class="mac-filename">query.sql</div>
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    st.code(sql, language="sql")

def render_sql_executor_tab() -> None:
    """Renders the Raw SQL Executor panel."""
    st.markdown(
        """
        <div class="mac-editor-frame">
            <div class="mac-editor-header">
                <div class="mac-dots">
                    <div class="mac-dot red"></div>
                    <div class="mac-dot yellow"></div>
                    <div class="mac-dot green"></div>
                </div>
                <div class="mac-filename">direct_query.sql</div>
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    sql_input = st.text_area("Type your SELECT query here:", value="SELECT * FROM student_performance_dataset LIMIT 5;" if st.session_state.loaded_filename == "student_performance_dataset.csv" else "SELECT * FROM sqlite_master LIMIT 5;", height=150, label_visibility="collapsed")
    
    col_exec, col_clear = st.columns([1, 8])
    exec_clicked = col_exec.button("▶ Run query", type="primary")
    
    if exec_clicked and sql_input:
        try:
            # AST Safety check
            SecurityValidator.is_safe_statement(sql_input)
            
            # Execute Raw Query
            with st.spinner("Executing SQL query..."):
                res = st.session_state.db_manager.execute_raw(sql_input, timeout=settings.SQL_TIMEOUT_SEC)
                df = pd.DataFrame(res.rows, columns=res.columns)
                
            # Success status styled like the screenshot
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 0.5rem; margin-bottom: 1rem; font-family: 'Outfit', sans-serif; font-size: 0.9rem; color: #7B817C;">
                    <span style="color: #27c93f; font-size: 1.2rem;">●</span>
                    <span>executed in {res.execution_time_ms:.1f}ms &middot; {res.row_count} rows loaded</span>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            from ui.results import render_results_table
            render_results_table(df)
            
            # Split cards layout
            st.markdown("---")
            col_vis, col_ins = st.columns(2)
            
            with col_vis:
                st.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.75rem; letter-spacing: 0.5px; text-transform: uppercase;'>RECOMMENDED VISUALIZATION</div>", unsafe_allow_html=True)
                from ui.charts import render_recommended_chart
                render_recommended_chart(df)
                    
            with col_ins:
                st.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.75rem; letter-spacing: 0.5px; text-transform: uppercase;'>EXECUTIVE HIGHLIGHTS</div>", unsafe_allow_html=True)
                
                summary_service = SummaryService()
                summary = summary_service.summarize_results(df, context_prompt=sql_input)
                
                # Render highlights inside a clean card with a caution banner
                caution_item = None
                normal_items = []
                for item in summary.key_takeaways:
                    if any(w in item.lower() for w in ["student #5", "caution", "warning", "outlier", "risk", "anomaly", "yet scored", "but"]):
                        caution_item = item
                    else:
                        normal_items.append(item)
                        
                if not caution_item and len(summary.key_takeaways) > 2:
                    caution_item = summary.key_takeaways[-1]
                    normal_items = summary.key_takeaways[:-1]
                elif not caution_item:
                    normal_items = summary.key_takeaways
                    
                st.markdown(
                    f"""
                    <div class="card" style="background-color: #FFFFFF; border: 1px solid #E4E4DC; border-radius: 12px; padding: 1.25rem;">
                        <div style="font-size: 0.95rem; color: #1C1E1C; line-height: 1.5; margin-bottom: 1rem;">
                            {summary.insights}
                        </div>
                        <ul style="margin: 0; padding-left: 1.2rem; font-size: 0.9rem; color: #2D312E; line-height: 1.6;">
                            {"".join([f"<li>{item}</li>" for item in normal_items])}
                        </ul>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                if caution_item:
                    st.markdown(
                        f"""
                        <div style="background-color: rgba(192, 128, 48, 0.06); border: 1px solid rgba(192, 128, 48, 0.25); border-radius: 8px; padding: 0.75rem; display: flex; gap: 8px; align-items: start; margin-top: -0.5rem; margin-bottom: 1rem;">
                            <span style="font-size: 1.1rem; color: #C08030;">⚠️</span>
                            <div style="font-size: 0.85rem; color: #C08030; line-height: 1.4;">
                                {caution_item}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
        except SecurityValidationError as sec_err:
            st.error(f"🛡️ Security Block: {sec_err}")
        except Exception as e:
            st.error(f"❌ Execution Error: {e}")
            traceback.print_exc()
