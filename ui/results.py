"""Results Table formatting.

Renders data outputs tables grid views and export CSV widgets.
"""

import streamlit as st
import pandas as pd

def render_results_table(df: pd.DataFrame, truncated: bool = False, total_rows: int = None, key: str = None) -> None:
    """Renders formatted table display with custom CSV downloader."""
    st.dataframe(df)
    
    row_count = len(df)
    if total_rows is None:
        total_rows = row_count
        
    if truncated or total_rows > row_count:
        st.warning(f"⚠️ Truncation Warning: Displaying only the first {row_count} rows of {total_rows} total rows.")
    else:
        st.info(f"Loaded {row_count} rows.")
        
    csv_data = df.to_csv(index=False).encode('utf-8')
    dl_key = key if key else "download_csv"
    st.download_button(
        "📥 Download CSV",
        data=csv_data,
        file_name="query_results.csv",
        mime="text/csv",
        key=dl_key
    )
