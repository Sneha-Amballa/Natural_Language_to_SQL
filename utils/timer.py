import time
import logging
import threading
import functools
from typing import Callable, Any, List, Optional
from contextlib import ContextDecorator

logger = logging.getLogger("agent")

# Thread-local storage for nested timing stacks
_local_timer_stack = threading.local()

class Timer(ContextDecorator):
    """Timing utility that works as a decorator and context manager.
    
    Supports hierarchical nested timer measurements.
    """
    
    def __init__(self, name: str = "execution_block"):
        self.name = name
        self.start_time: Optional[float] = None
        self.elapsed: Optional[float] = None
        
    def __enter__(self):
        self.start_time = time.perf_counter()
        if not hasattr(_local_timer_stack, "stack"):
            _local_timer_stack.stack = []
            
        parent = _local_timer_stack.stack[-1] if _local_timer_stack.stack else None
        # Track depth for nesting visual prints if necessary
        self.depth = len(_local_timer_stack.stack)
        _local_timer_stack.stack.append(self)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter()
        self.elapsed = (end_time - self.start_time) * 1000.0  # ms
        
        if hasattr(_local_timer_stack, "stack") and _local_timer_stack.stack:
            _local_timer_stack.stack.pop()
            
        logger.info({
            "event": "execution_time",
            "block_name": self.name,
            "duration_ms": self.elapsed,
            "depth": self.depth,
            "status": "SUCCESS" if exc_type is None else "FAILED"
        })
        
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def inner(*args, **kwargs):
            # If default name, use the function name
            original_name = self.name
            if original_name == "execution_block":
                self.name = func.__name__
            try:
                with self:
                    return func(*args, **kwargs)
            finally:
                self.name = original_name
        return inner

def measure_execution_time(name: str = "block") -> Timer:
    """Timing utility providing context manager and decorator configurations."""
    return Timer(name)

def measure_time(func: Callable) -> Callable:
    """Decorator logging exact transaction process runtime durations."""
    return Timer()(func)

