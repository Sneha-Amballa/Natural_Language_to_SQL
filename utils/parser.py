"""Response Markdown Blocks Parser.

Extracts generated codes blocks from raw texts outputs.
"""

import re
from typing import Tuple

import re
import json
from typing import Tuple, Dict, Any, List, Optional

class MarkdownParser:
    """Parses generated code nodes components."""
    
    @staticmethod
    def parse_sql_block(text: str) -> Tuple[str, str]:
        """Splits thought logs from SQL blocks syntax models."""
        pattern = r"```sql\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            sql_code = match.group(1).strip()
            thought_log = text.replace(match.group(0), "").strip()
            return thought_log, sql_code
        return text.strip(), ""

def repair_json_string(text: str) -> str:
    """Attempts to repair common malformed JSON issues."""
    repaired = text.strip()
    if repaired.startswith("```"):
        lines = repaired.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        repaired = "\n".join(lines).strip()
        
    # Replace single quotes around keys and string values with double quotes
    repaired = re.sub(r"'(\w+)'\s*:", r'"\1":', repaired)
    repaired = re.sub(r":\s*'([^']*)'", r': "\1"', repaired)
    repaired = re.sub(r",\s*'([^']*)'", r', "\1"', repaired)
    repaired = re.sub(r"\[\s*'([^']*)'", r'[ "\1"', repaired)
    return repaired

def parse_llm_response(text: str) -> Dict[str, Any]:
    """Extracts tool calls, arguments, and assistant responses from raw text.
    
    Supports malformed JSON recovery and standardization.
    """
    result = {
        "tool_calls": [],
        "assistant_response": "",
        "sql_query": ""
    }
    
    if not text:
        return result
        
    thought, sql = MarkdownParser.parse_sql_block(text)
    if sql:
        result["sql_query"] = sql
        result["assistant_response"] = thought
        result["tool_calls"].append({
            "name": "run_query",
            "arguments": {"sql": sql}
        })
        
    json_block = ""
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if json_match:
        json_block = json_match.group(1).strip()
    else:
        trimmed = text.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            json_block = trimmed
            
    if json_block:
        data = None
        try:
            data = json.loads(json_block)
        except Exception:
            try:
                repaired = repair_json_string(json_block)
                data = json.loads(repaired)
            except Exception:
                pass
                
        if isinstance(data, dict):
            t_calls = data.get("tool_calls") or data.get("tool") or []
            if isinstance(t_calls, dict):
                t_calls = [t_calls]
            elif isinstance(t_calls, str):
                try:
                    t_calls = json.loads(t_calls)
                except Exception:
                    t_calls = [{"name": t_calls, "arguments": data.get("arguments") or {}}]
                    
            normalized_calls = []
            for tc in t_calls:
                if isinstance(tc, dict) and "name" in tc:
                    name = tc["name"]
                    args = tc.get("arguments") or tc.get("args") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {"raw_value": args}
                    normalized_calls.append({
                        "name": name,
                        "arguments": args
                    })
            if normalized_calls:
                result["tool_calls"] = normalized_calls
                
            resp = data.get("assistant_response") or data.get("response") or data.get("content") or ""
            if resp:
                result["assistant_response"] = resp
                
    if not result["assistant_response"]:
        result["assistant_response"] = thought if sql else text.strip()
        
    return result

def parse_tables_from_sql(sql: str) -> List[str]:
    """Parses referenced table names from a SQL query string using regex/sqlglot."""
    import sqlglot
    from sqlglot import exp
    tables = []
    try:
        parsed = sqlglot.parse(sql, read="sqlite")
        for expression in parsed:
            if not expression:
                continue
            for node in expression.walk():
                if isinstance(node, exp.Table):
                    tables.append(node.name)
    except Exception:
        # Fallback to regex
        matches = re.findall(r"\bfrom\s+(\w+)\b|\bjoin\s+(\w+)\b", sql, re.IGNORECASE)
        for match in matches:
            for group in match:
                if group:
                    tables.append(group)
    return list(set(tables))

def parse_key_value_config(text: str) -> Dict[str, str]:
    """Parses standard key-value or environment variables formats."""
    config = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            config[key.strip()] = val.strip()
    return config


