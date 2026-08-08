"""Centralized Configuration Module.

Loads configuration parameters from environment variables or .env file
with runtime constraints validation.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    """Application configuration loaded from environment or .env file."""
    
    # Groq LLM configuration
    GROQ_API_KEY: Optional[SecretStr] = Field(None, env="GROQ_API_KEY")
    LLM_MODEL: str = Field("llama-3.3-70b-versatile", env="LLM_MODEL")

    TEMPERATURE: float = Field(0.0, env="LLM_TEMPERATURE")
    MAX_RETRIES: int = Field(3, env="AGENT_MAX_RETRIES")
    
    # SQLite Database configurations
    SQL_TIMEOUT_SEC: float = Field(5.0, env="SQL_TIMEOUT_SEC")
    MAX_QUERY_ROWS: int = Field(1000, env="MAX_QUERY_ROWS")
    SCHEMA_CACHE_TTL_SEC: int = Field(300, env="SCHEMA_CACHE_TTL_SEC")
    
    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = Field(50, env="MAX_UPLOAD_SIZE_MB")
    SAMPLE_ROWS_LIMIT: int = Field(3, env="SAMPLE_ROWS_LIMIT")
    
    # Chart logic thresholds
    CHART_DEFAULT_THRESHOLD: int = Field(50, env="CHART_DEFAULT_THRESHOLD")
    
    # Telemetry logging limits
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    LOG_FILE_PATH: str = Field("logs/agent.log", env="LOG_FILE_PATH")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
