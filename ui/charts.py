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
    st.markdown("### 📊 Visualizations Dashboard")
    st.info("Run a query in the Direct SQL Editor or chat with the AI Analyst to generate tables. This tab automatically renders graphs based on the last executed query results.")
    
    last_df = None
    last_sql = ""
    if st.session_state.chat_history:
        last_msg = st.session_state.chat_history[-1]
        if last_msg.get("df") is not None:
            last_df = pd.DataFrame(last_msg["df"])
            last_sql = last_msg.get("sql", "Chat Query")
            
    if last_df is not None:
        st.markdown(f"**Visualizing results for:** `{last_sql}`")
        
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
