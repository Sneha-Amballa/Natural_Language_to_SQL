import time
import logging
from typing import Callable, Any
from config import settings

logger = logging.getLogger("agent")

def is_retryable_exception(exc: Exception) -> bool:
    """Checks if the exception is transient and can be retried.
    
    Checks standard Groq/network exceptions.
    """
    exc_name = type(exc).__name__
    if exc_name in ("RateLimitError", "APIConnectionError", "InternalServerError", "APIResponseValidationError"):
        return True
    if hasattr(exc, "status_code"):
        status_code = getattr(exc, "status_code")
        if status_code in (429, 500, 502, 503, 504):
            return True
    if "ConnectionError" in exc_name or "Timeout" in exc_name:
        return True
    return False

def retry_llm_call(func: Callable, *args, **kwargs) -> Any:
    """Executes a callable wrapping it in an exponential backoff retry loop.
    
    Args:
        func: The function to execute.
        *args: Variable length argument list for the function.
        **kwargs: Arbitrary keyword arguments for the function.
        
    Returns:
        The return value of the wrapped function.
    """
    max_retries = settings.MAX_RETRIES
    delay = 1.0
    backoff_factor = 2.0
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                logger.error({
                    "event": "llm_retry_failed",
                    "error": str(e),
                    "attempt": attempt,
                    "max_retries": max_retries
                })
                break
                
            if is_retryable_exception(e):
                logger.warning({
                    "event": "llm_retry_attempt",
                    "error": str(e),
                    "attempt": attempt + 1,
                    "delay": delay
                })
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error({
                    "event": "llm_non_retryable_error",
                    "error": str(e),
                    "attempt": attempt + 1
                })
                raise e
                
    if last_exception:
        raise last_exception

def retry_on_exception(retries: int = 3, delay: float = 1.0) -> Callable:
    """Decorates execution components enforcing fallback execution attempts.
    
    Args:
        retries: Maximum number of retries.
        delay: Initial sleep delay in seconds.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt == retries:
                        break
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= 2.0
            if last_exc:
                raise last_exc
        return wrapper
    return decorator

