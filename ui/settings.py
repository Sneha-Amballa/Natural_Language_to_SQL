"""Application Control Settings Panel.

Renders runtime control settings widgets.
"""

import streamlit as st
import os

def render_api_key_settings() -> None:
    """Renders Groq API Key settings input."""
    if "groq_api_key" not in st.session_state:
        st.session_state.groq_api_key = ""
        
    api_key_input = st.text_input(
        "Groq API Key", 
        type="password", 
        placeholder="gsk_...",
        value=st.session_state.groq_api_key,
        help="Supply your Groq API Key to enable the AI Analyst."
    )
    
    if api_key_input != st.session_state.groq_api_key:
        st.session_state.groq_api_key = api_key_input
        st.rerun()
        
    if st.session_state.groq_api_key:
        st.markdown(
            """
            <div style='margin-bottom: 1.5rem;'>
                <div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.5rem; letter-spacing: 0.5px;'>CONNECTION</div>
                <div class="status-connected" style="width: 100%; text-align: center;">● Groq API connected</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style='margin-bottom: 1.5rem;'>
                <div style='font-size: 0.75rem; font-weight: 700; color: #7B817C; margin-bottom: 0.5rem; letter-spacing: 0.5px;'>CONNECTION</div>
                <div class="status-disconnected" style="width: 100%; text-align: center;">○ Groq API key required</div>
            </div>
            """, 
            unsafe_allow_html=True
        )

def render_control_settings() -> dict:
    """Legacy stub method."""
    return {}
