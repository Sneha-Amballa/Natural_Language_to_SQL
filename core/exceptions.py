"""Custom Exceptions Definitions.

Standardizes application exception boundaries.
"""

class BaseAgentException(Exception):
    """System-wide base exception type."""
    pass

class DatabaseConnectionError(BaseAgentException):
    """Raised when database connection failures occur."""
    pass

class SecurityValidationError(BaseAgentException):
    """Raised when security scans block request structures."""
    pass

class QueryExecutionError(BaseAgentException):
    """Raised when database transaction queries fail execution."""
    pass

class LLMCallError(BaseAgentException):
    """Raised when Groq API connectivity issues happen."""
    pass
