"""Visualization Charts Dashboard rendering.

Handles Altair visual graphs plotting configs templates.
"""

import streamlit as st
import pandas as pd
from services.visualization_service import VisualizationService

def render_recommended_chart(df: pd.DataFrame) -> None:
    """Renders visual graphs based on recommendation models rules."""
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

def render_visualizations_tab() -> None:
    """Renders full charts tab visualization selector."""
    st.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.75rem; letter-spacing: 0.5px; text-transform: uppercase;'>VISUALIZATIONS DASHBOARD</div>", unsafe_allow_html=True)
    
    last_df = None
    last_sql = ""
    if st.session_state.chat_history:
        # Traverse history backwards to find the last message with query data
        for last_msg in reversed(st.session_state.chat_history):
            if last_msg.get("df_data") is not None:
                last_df = pd.DataFrame(last_msg["df_data"])
                last_sql = last_msg.get("sql", "Chat Query")
                break
            elif last_msg.get("df") is not None:
                last_df = pd.DataFrame(last_msg["df"])
                last_sql = last_msg.get("sql", "Chat Query")
                break
                
    if last_df is not None:
        vis_service = VisualizationService()
        rec = vis_service.get_recommendation(last_df)
        
        if rec.should_render:
            # Side-by-side dropdown selectors
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                chart_option = st.selectbox("CHART TYPE", ["Recommended", "Bar", "Line", "Scatter", "Pie"])
            with col2:
                x_axis = st.selectbox("X-AXIS", last_df.columns, index=list(last_df.columns).index(rec.x_axis) if rec.x_axis in last_df.columns else 0)
            with col3:
                y_axis = st.selectbox("Y-AXIS", last_df.columns, index=list(last_df.columns).index(rec.y_axis) if rec.y_axis in last_df.columns else 0)
            with col4:
                st.selectbox("GROUP BY", ["None"] + list(last_df.columns), index=0)
                
            type_sel = rec.chart_type if chart_option == "Recommended" else chart_option.lower()
            
            # Chart title styled cleanly
            title_str = f"{y_axis.replace('_', ' ').capitalize()} by {x_axis.replace('_', ' ')}"
            st.markdown(f"#### {title_str}")
            
            if type_sel == "line":
                st.line_chart(last_df, x=x_axis, y=y_axis)
            elif type_sel == "bar":
                st.bar_chart(last_df, x=x_axis, y=y_axis)
            elif type_sel == "scatter":
                st.scatter_chart(last_df, x=x_axis, y=y_axis)
            elif type_sel == "pie":
                import altair as alt
                c = alt.Chart(last_df).mark_arc().encode(
                    theta=alt.Theta(field=y_axis, type="quantitative"),
                    color=alt.Color(field=x_axis, type="nominal"),
                    tooltip=[x_axis, y_axis]
                ).properties(height=350)
                st.altair_chart(c, use_container_width=True)
                
            st.markdown("<div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-top: 1.5rem; margin-bottom: 0.5rem; letter-spacing: 0.5px;'>SQL QUERY</div>", unsafe_allow_html=True)
            st.code(last_sql, language="sql")
        else:
            st.warning("Current dataset structure doesn't support automatic visualizations. Try executing a query returning multiple numerical or chronological values.")
    else:
        st.info("No active query dataset loaded yet. Please run a query first in the AI Analyst tab or SQL Editor!")
