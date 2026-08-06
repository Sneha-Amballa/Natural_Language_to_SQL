from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ToolRequest(BaseModel):
    """Payload sent to invoke a tool."""
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class ToolResponse(BaseModel):
    """Result payload returned by tool execution."""
    is_success: bool = True
    result_content: str
    error_message: Optional[str] = None

class ToolMetadata(BaseModel):
    """Metadata describing a tool for API bindings."""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

class ValidationResult(BaseModel):
    """Structure holding validation outcome metrics."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)

class SchemaResult(BaseModel):
    """Details outlining database table columns and indexes configuration."""
    table_name: str
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    indexes: List[Dict[str, Any]] = Field(default_factory=list)

class QueryResult(BaseModel):
    """Structured details from database SELECT operations."""
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float

class SampleRowsResult(BaseModel):
    """Rows payload formatting container."""
    table_name: str
    columns: List[str]
    rows: List[List[Any]]
    formatted_content: str

class IndexSuggestion(BaseModel):
    """Analysis indexing performance recommendation payload."""
    table_name: str
    suggested_index_name: str
    target_columns: List[str]
    reasoning: str
    estimated_improvement: str
