import logging
import os
import datetime
import json
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger
from config import settings

def setup_logging(level: str = "INFO") -> None:
    """Configures standard console, rotating file, and JSON logging."""
    root_logger = logging.getLogger()
    
    num_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(num_level)
    
    log_dir = os.path.dirname(settings.LOG_FILE_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    
    has_stream = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    has_file = any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    
    if not has_stream:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
    if not has_file:
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                settings.LOG_FILE_PATH,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception:
            pass


def log_agent_steps(
    run_id: str,
    question: str,
    tool_name: Optional[str] = None,
    execution_time: Optional[float] = None,
    arguments: Optional[Any] = None,
    sql: Optional[str] = None,
    rows_returned: Optional[int] = None,
    errors: Optional[str] = None,
    retry_count: int = 0,
    summary: Optional[str] = None
) -> None:
    """Writes a structured JSON log tracking agent steps and execution telemetry."""
    # Ensure logs are configured
    setup_logging(settings.LOG_LEVEL)
    
    logger = logging.getLogger("agent.steps")
    
    log_payload = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "run_id": run_id,
        "question": question,
        "tool_name": tool_name,
        "execution_time_ms": execution_time,
        "arguments": arguments,
        "generated_sql": sql,
        "rows_returned": rows_returned,
        "errors": errors,
        "retry_count": retry_count,
        "summary": summary
    }
    
    logger.info("Agent Step telemetry", extra={"agent_step": log_payload})

