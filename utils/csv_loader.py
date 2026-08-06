"""CSV File Loader.

Reads raw CSV tables importing them directly to temporary SQLite tables.
"""

import pandas as pd
import sqlite3

import pandas as pd
import sqlite3
import re

import pandas as pd
import sqlite3
import re
import os

class CSVLoader:
    """Converts flat CSV frames to database structures."""
    
    @staticmethod
    def _clean_headers(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column headers to be clean, sql-safe identifiers."""
        new_columns = []
        seen = {}
        for col in df.columns:
            col_str = str(col).strip()
            col_clean = re.sub(r'[^a-zA-Z0-9_]', '_', col_str)
            col_clean = re.sub(r'_+', '_', col_clean)
            col_clean = col_clean.strip('_').lower()
            
            if col_clean and col_clean[0].isdigit():
                col_clean = "col_" + col_clean
            if not col_clean:
                col_clean = f"col_{len(new_columns)}"
                
            base_col = col_clean
            counter = 1
            while col_clean in seen:
                col_clean = f"{base_col}_{counter}"
                counter += 1
            seen[col_clean] = True
            new_columns.append(col_clean)
            
        df.columns = new_columns
        return df

    @staticmethod
    def import_csv(csv_path: str, conn: sqlite3.Connection, table_name: str) -> None:
        """Imports CSV datasets supporting large files, duplicates, chunked loads, and encoding fallbacks."""
        # Slugify table name to make it a safe SQL identifier
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name.strip()).lower()
        table_name = re.sub(r'_+', '_', table_name).strip('_')
        if table_name and table_name[0].isdigit():
            table_name = "tbl_" + table_name
        if not table_name:
            table_name = "csv_data"
            
        chunk_size = 5000
        try:
            # Encoding detection sequence
            encodings = ["utf-8", "latin-1", "cp1252", "utf-16", "utf-8-sig"]
            detected_enc = "utf-8"
            sample_df = None
            
            for enc in encodings:
                try:
                    sample_df = pd.read_csv(csv_path, encoding=enc, nrows=2)
                    detected_enc = enc
                    break
                except Exception:
                    continue
                    
            if sample_df is None:
                sample_df = pd.read_csv(csv_path, nrows=2)
                detected_enc = None
                
            cleaned_sample = CSVLoader._clean_headers(sample_df)
            column_names = list(cleaned_sample.columns)
            
            # Stream/chunk large files to database
            reader = pd.read_csv(csv_path, encoding=detected_enc, chunksize=chunk_size)
            first_chunk = True
            
            for chunk in reader:
                if len(chunk.columns) == len(column_names):
                    chunk.columns = column_names
                else:
                    chunk = CSVLoader._clean_headers(chunk)
                    
                if_exists_action = "replace" if first_chunk else "append"
                chunk.to_sql(table_name, conn, if_exists=if_exists_action, index=False)
                first_chunk = False
                
        except Exception as e:
            raise ValueError(f"Failed to import CSV: {e}") from e


