"""Unified Data Models.

Defines Pydantic models for type validation across services.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

class ToolResponse(BaseModel):
    is_success: bool = True
    result_content: str
    error_message: Optional[str] = None

class QueryResult(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float

class ExecutionMetrics(BaseModel):
    total_duration_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ColumnSchema(BaseModel):
    name: str
    data_type: str
    is_primary: bool
    foreign_reference: Optional[Dict[str, str]] = None

class DatabaseSchema(BaseModel):
    tables: Dict[str, List[ColumnSchema]]

class ChatMessage(BaseModel):
    role: str
    content: str
    tool_call_id: Optional[str] = None

class Conversation(BaseModel):
    history: List[ChatMessage]

class SummaryResponse(BaseModel):
    insights: str
    key_takeaways: List[str]

class VisualizationRecommendation(BaseModel):
    should_render: bool
    chart_type: str
    x_axis: str
    y_axis: str
    vega_lite_spec: Dict[str, Any]

class ConfigurationModel(BaseModel):
    model_name: str
    temperature: float
    max_retries: int
    timeout: float

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[str] = None

class AgentResponse(BaseModel):
    response_text: str
    sql_query: Optional[str] = None
    metrics: Optional[ExecutionMetrics] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)

