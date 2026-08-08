"""Chat Interface Panel.

Handles conversational flow states and integrates all execution elements inline.
"""

import streamlit as st
import pandas as pd
import os
import json
import traceback
from agent.orchestrator import SQLAgent
from config import settings

def render_chat_tab() -> None:
    """Renders the AI chat interface."""
    groq_api_key = st.session_state.get("groq_api_key", "")
    if not groq_api_key:
        st.warning("⚠️ Please enter your Groq API key in the sidebar to use AI Analyst.")
        
    # Display chat messages from st.session_state.chat_history in a scrollable container
    st.markdown('<div class="chat-container-wrapper">', unsafe_allow_html=True)
    message_container = st.container(height=550, border=False)
    st.markdown('</div>', unsafe_allow_html=True)
    with message_container:
        for idx, msg in enumerate(st.session_state.chat_history):
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    st.write(msg["content"])
                else:
                    # Assistant message details rendered sequentially
                    # 1. AI Analyst Explanation
                    st.write(msg["content"])
                
                # 2. Optional "Analysis Steps" section
                if "steps" in msg and msg["steps"]:
                    steps = msg["steps"]
                    visible_steps = [s for s in steps if s.get("tool_called") not in ["validate_sql", "sanitize_sql"]]
                    
                    if visible_steps:
                        with st.expander("🔎 Analysis Steps"):
                            metadata_bullets = []
                            has_get_schema = any(s.get("tool_called") == "get_schema" for s in steps)
                            has_list_tables = any(s.get("tool_called") == "list_tables" for s in steps)
                            has_count_rows = any(s.get("tool_called") == "count_rows" for s in steps)
                            has_get_column_stats = any(s.get("tool_called") == "get_column_stats" for s in steps)
                            has_find_column_values = any(s.get("tool_called") == "find_column_values" for s in steps)
                            has_run_query = any(s.get("tool_called") == "run_query" for s in steps)
                            has_validation = any(s.get("tool_called") == "validate_sql" for s in steps)
                            validation_success = any(s.get("tool_called") == "validate_sql" and s.get("status") == "SUCCESS" for s in steps)
                            
                            has_agg = False
                            for s in steps:
                                if s.get("tool_called") == "run_query" and "sql" in s.get("arguments", "").lower():
                                    sql_lower = s.get("arguments").lower()
                                    if any(agg in sql_lower for agg in ["count(", "sum(", "avg(", "min(", "max("]):
                                        has_agg = True
                                        
                            if has_agg:
                                metadata_bullets.append("• Classified as aggregation")
                            if has_get_schema or has_list_tables:
                                metadata_bullets.append("• Inspected table schema")
                            if has_count_rows:
                                metadata_bullets.append("• Used count_rows")
                            if has_get_column_stats:
                                metadata_bullets.append("• Used get_column_stats")
                            if has_find_column_values:
                                metadata_bullets.append("• Used find_column_values")
                            if any("sql" in s.get("arguments", "") for s in steps):
                                metadata_bullets.append("• Generated SQL")
                            if has_validation and validation_success:
                                metadata_bullets.append("• SQL validation passed")
                            if has_run_query:
                                run_success = any(s.get("tool_called") == "run_query" and s.get("status") == "SUCCESS" for s in steps)
                                if run_success:
                                    metadata_bullets.append("• Query executed successfully")
                                    
                            for bullet in metadata_bullets:
                                st.markdown(bullet)
                                
                            if metadata_bullets and visible_steps:
                                st.markdown("---")
                                
                            for step in visible_steps:
                                tool_name = step.get("tool_called", "")
                                status = step.get("status", "")
                                status_symbol = "✓" if status == "SUCCESS" else "✗"
                                st.markdown(f"Tool: {tool_name}")
                                st.markdown(f"Status: {status_symbol}")
                                st.markdown("")
                
                # 3. Generated SQL (macOS editor style)
                if "sql" in msg and msg["sql"]:
                    corrected_automatically = any(
                        step.get("tool_called") == "run_query" and step.get("status") == "FAILED"
                        for step in msg.get("steps", [])
                    )
                    st.markdown(
                        """
                        <div class="mac-editor-frame">
                            <div class="mac-editor-header">
                                <div class="mac-dots">
                                    <div class="mac-dot red"></div>
                                    <div class="mac-dot yellow"></div>
                                    <div class="mac-dot green"></div>
                                </div>
                                <div class="mac-filename">generated_query.sql</div>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    st.code(msg["sql"], language="sql")
                    if corrected_automatically:
                        st.info("SQL corrected automatically after validation error.")
                            
                # Reconstruct query results
                df = None
                if "df" in msg and msg["df"] is not None:
                    df = pd.DataFrame(msg["df"])
                elif "df_data" in msg and msg["df_data"] is not None:
                    df = pd.DataFrame(msg["df_data"])
                    
                # 4. Query Result Table
                if df is not None:
                    st.markdown("📊 **Query Result**")
                    truncated = msg.get("truncated", False)
                    total_rows = msg.get("total_rows", len(df))
                    from ui.results import render_results_table
                    render_results_table(df, truncated=truncated, total_rows=total_rows, key=f"chat_table_{idx}")
                    
                    # 5. Inline Visualization (only when appropriate and not technical metadata)
                    from services.visualization_service import VisualizationService
                    vis_service = VisualizationService()
                    
                    user_q = ""
                    if idx > 0 and st.session_state.chat_history[idx - 1]["role"] == "user":
                        user_q = st.session_state.chat_history[idx - 1]["content"]
                        
                    is_technical = False
                    if msg.get("sql"):
                        sql_lower = msg["sql"].lower()
                        if any(term in sql_lower for term in ["sqlite_master", "sqlite_sequence", "rootpage"]):
                            is_technical = True
                    if any(any(term in str(col).lower() for term in ["sqlite_master", "sqlite_sequence", "rootpage", "tbl_name"]) for col in df.columns):
                        is_technical = True
                        
                    if not is_technical and vis_service.should_show_chart(df, user_q):
                        rec = vis_service.get_recommendation(df)
                        if rec.should_render:
                            st.markdown(f"📈 **Visualization ({rec.chart_type.capitalize()} Chart)**")
                            if rec.chart_type == "bar":
                                st.bar_chart(df, x=rec.x_axis, y=rec.y_axis)
                            elif rec.chart_type == "line":
                                st.line_chart(df, x=rec.x_axis, y=rec.y_axis)
                            elif rec.chart_type == "scatter":
                                st.scatter_chart(df, x=rec.x_axis, y=rec.y_axis)
                                
                # 6. Executive Highlights
                if "highlights" in msg and msg["highlights"]:
                    st.markdown("### 💡 Executive Highlights")
                    for item in msg["highlights"].get("key_takeaways", []):
                        st.markdown(f"• {item}")
                        
    # Chat input
    if groq_api_key:
        user_prompt = st.chat_input("Ask the AI Analyst a question...")
        if user_prompt:
            import time
            from services.history_service import SessionHistoryService
            from models.models import ChatMessage
            
            with message_container.chat_message("user"):
                st.write(user_prompt)
                
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            st.session_state.events.append({
                "type": "user_query",
                "content": user_prompt,
                "timestamp": time.time()
            })
            
            with message_container.chat_message("assistant"):
                with st.status("AI Analyst is thinking...") as status_block:
                    try:
                        agent = SQLAgent(st.session_state.db_path)
                        agent.setup_system_context()
                        for hist in st.session_state.chat_history[:-1]:
                            agent.memory.add_message(hist["role"], hist["content"])
                            
                        response = agent.execute(user_prompt)
                        
                        for step in response.steps:
                            st.session_state.events.append({
                                "type": "agent_step",
                                "step": step["step"],
                                "tool": step["tool_called"],
                                "status": step["status"],
                                "duration": step["duration_ms"],
                                "result": str(step.get("result", "")),
                                "timestamp": time.time()
                            })
                                
                        status_block.update(label="Analysis Completed!", state="complete")
                    except Exception as e:
                        status_block.update(label="Analysis Failed", state="error")
                        st.error(f"Error running agent loop: {e}")
                        traceback.print_exc()
                        response = None
                        
                if response:
                    st.session_state.events.append({
                        "type": "assistant_response",
                        "content": response.response_text,
                        "timestamp": time.time()
                    })
                    
                    df_res = None
                    truncated = False
                    total_rows = None
                    
                    # Extract dataset result and metadata from run_query tool response payload
                    for step in reversed(response.steps):
                        if step.get("tool_called") == "run_query" and step.get("status") == "SUCCESS":
                            try:
                                payload = json.loads(step.get("result", "{}"))
                                columns = payload.get("columns", [])
                                rows = payload.get("rows", [])
                                df_res = pd.DataFrame(rows, columns=columns)
                                truncated = payload.get("metadata", {}).get("truncated", False)
                                total_rows = payload.get("total_db_rows", len(df_res))
                                break
                            except Exception:
                                pass
                                
                    # Fallback if no run_query step was successfully parsed but SQL was generated
                    if df_res is None and response.sql_query:
                        try:
                            query_res = st.session_state.db_manager.execute_raw(response.sql_query)
                            df_res = pd.DataFrame(query_res.rows, columns=query_res.columns)
                            truncated = False
                            total_rows = len(df_res)
                        except Exception as q_err:
                            st.warning(f"Could not load data results: {q_err}")
                            
                    # Generate highlights once
                    highlights = None
                    if df_res is not None and not df_res.empty:
                        try:
                            from services.summary_service import SummaryService
                            summary_service = SummaryService()
                            summary = summary_service.summarize_results(df_res, context_prompt=user_prompt)
                            highlights = {
                                "insights": summary.insights,
                                "key_takeaways": summary.key_takeaways
                            }
                        except Exception as sum_err:
                            highlights = {
                                "insights": f"Analysis of {len(df_res)} rows.",
                                "key_takeaways": [f"Row count: {len(df_res)}", f"Columns: {', '.join(df_res.columns)}"]
                            }
                            
                    hist_entry = {
                        "role": "assistant",
                        "content": response.response_text,
                        "steps": response.steps,
                        "sql": response.sql_query,
                        "df": df_res.to_dict(orient="list") if df_res is not None else None,
                        "df_data": df_res.to_dict(orient="list") if df_res is not None else None,
                        "truncated": truncated,
                        "total_rows": total_rows,
                        "highlights": highlights
                    }
                    st.session_state.chat_history.append(hist_entry)
                    
                    # Save session
                    try:
                        chat_msgs = [
                            ChatMessage(role=m["role"], content=m["content"], tool_call_id=m.get("tool_call_id"))
                            for m in st.session_state.chat_history
                        ]
                        history_service = SessionHistoryService()
                        history_service.save_session(
                            session_id=st.session_state.session_id,
                            history=chat_msgs,
                            events=st.session_state.events,
                            raw_history=st.session_state.chat_history
                        )
                    except Exception as save_err:
                        st.error(f"Failed to save session state.")
                        
                    st.rerun()
