import json
import decimal
import datetime
import pandas as pd
from typing import Any, Union, Dict, List

def format_value(val: Any) -> Any:
    """Formats single cell values (nulls, decimals, datetimes) safely."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "NULL"
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    return val

class ResultFormatter:
    """Exposes string serialization formatting utilities."""
    
    @staticmethod
    def df_to_markdown(df: pd.DataFrame, max_rows: int = 10) -> str:
        """Formats table results grid representation with spacing for markdown parsers."""
        if df.empty:
            return "\n\nEmpty Dataset\n\n"
        df_subset = df.head(max_rows)
        if hasattr(df_subset, "map"):
            formatted_df = df_subset.map(format_value)
        else:
            formatted_df = df_subset.applymap(format_value)
        try:
            return "\n\n" + formatted_df.to_markdown(index=False) + "\n\n"
        except ImportError:
            # Fallback to manual markdown formatter if tabulate is not installed
            cols = formatted_df.columns
            headers = "| " + " | ".join(map(str, cols)) + " |"
            divider = "| " + " | ".join(["---"] * len(cols)) + " |"
            rows = []
            for _, row in formatted_df.iterrows():
                rows.append("| " + " | ".join(map(str, row.values)) + " |")
            return "\n\n" + "\n".join([headers, divider] + rows) + "\n\n"



def format_results(data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]], format_type: str = "json") -> str:
    """Formats database query results cleanly across different output types.
    
    Args:
        data: The input dataset (DataFrame, list of dicts, or single dict).
        format_type: The output target ('json', 'markdown', 'csv', 'dict', 'terminal').
    """
    if isinstance(data, pd.DataFrame):
        df = data
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, dict):
        df = pd.DataFrame([data])
    else:
        df = pd.DataFrame()
        
    if df.empty:
        return "Empty results"
        
    if hasattr(df, "map"):
        df_formatted = df.map(format_value)
    else:
        df_formatted = df.applymap(format_value)
        
    fmt = format_type.lower().strip()
    
    if fmt == "json":
        dict_records = df_formatted.to_dict(orient="records")
        return json.dumps(dict_records, indent=2, default=str)
    elif fmt == "markdown":
        return ResultFormatter.df_to_markdown(df_formatted)

    elif fmt == "csv":
        return df_formatted.to_csv(index=False)
    elif fmt == "dict":
        return str(df_formatted.to_dict(orient="records"))
    elif fmt == "terminal":
        return df_formatted.to_string(index=False)
        
    return df_formatted.to_string(index=False)

