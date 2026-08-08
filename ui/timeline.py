"""Timeline / History Display panel.

Renders execution step histories log details.
"""

import streamlit as st
import datetime

def render_timeline(events: list) -> None:
    """Renders timelines elements logs."""
    st.markdown("### 🕒 Session Event Timeline")
    if not events:
        st.info("No query events recorded in this session yet.")
        return
        
    for ev in events:
        ev_type = ev.get("type")
        timestamp_str = ""
        if "timestamp" in ev:
            try:
                dt = datetime.datetime.fromtimestamp(ev["timestamp"])
                timestamp_str = f" *({dt.strftime('%H:%M:%S')})*"
            except Exception:
                pass
                
        if ev_type == "user_query":
            st.markdown(f"❓ **User Query**{timestamp_str}")
            st.info(ev.get("content"))
        elif ev_type == "agent_step":
            status_icon = "✅" if ev.get("status") == "SUCCESS" else "❌"
            st.markdown(f"🛠️ **Agent Tool: `{ev.get('tool')}`** {status_icon}{timestamp_str}")
            st.write(f"Step {ev.get('step')} completed in {ev.get('duration', 0.0):.1f}ms with status *{ev.get('status')}*.")
            if ev.get("status") == "FAILED" and ev.get("result"):
                st.error(f"Error: {ev.get('result')}")
        elif ev_type == "sql_generation":
            st.markdown(f"💻 **SQL Code Generated**{timestamp_str}")
            st.code(ev.get("sql"), language="sql")
        elif ev_type == "assistant_response":
            st.markdown(f"🤖 **Analyst Response**{timestamp_str}")
            st.success(ev.get("content"))
