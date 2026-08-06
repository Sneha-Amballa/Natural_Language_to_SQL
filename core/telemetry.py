"""System Structured Logger.

Exposes JSON formatting logger structures.
"""

from typing import Dict, Any
from models.models import ExecutionMetrics

import logging
import os
from typing import Dict, Any
from pythonjsonlogger import jsonlogger
from models.models import ExecutionMetrics
from config import settings

class StructuredTelemetryLogger:
    """JSON log aggregations and metrics reporting utility."""
    
    def __init__(self, name: str = "agent"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        
        # Avoid duplicating handlers if they are already added
        if not self.logger.handlers:
            # Create logs directory if it does not exist
            log_dir = os.path.dirname(settings.LOG_FILE_PATH)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                
            formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            # Rotating file handler
            try:
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    settings.LOG_FILE_PATH,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5,
                    encoding="utf-8"
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception:
                pass
        
    def log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Logs structured event maps."""
        self.logger.info(f"Event: {event_type}", extra={"event_type": event_type, **payload})
        
    def log_metrics(self, metrics: ExecutionMetrics) -> None:
        """Reports processing time metrics parameters."""
        self.logger.info("Metrics report", extra={"metrics": metrics.model_dump()})

