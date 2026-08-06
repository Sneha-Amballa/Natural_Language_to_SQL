import time
import threading
from typing import Dict, Any, Optional, Callable
from config import settings

class SchemaCache:
    """Caches tables catalogs references mapping models."""
    
    def __init__(self, ttl: Optional[int] = None):
        self.ttl = ttl if ttl is not None else settings.SCHEMA_CACHE_TTL_SEC
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
    def get(self, key: str, loader: Optional[Callable[[], Any]] = None) -> Optional[Any]:
        """Returns active cache records if TTL constraint permits."""
        with self._lock:
            now = time.time()
            if key in self._cache:
                entry = self._cache[key]
                if now - entry["timestamp"] < self.ttl:
                    return entry["val"]
                # Cache expired, remove it
                del self._cache[key]
                
            # If cache missed/expired and loader callback is supplied, run automatic refresh
            if loader:
                val = loader()
                self.set(key, val)
                return val
            return None
            
    def set(self, key: str, val: Any) -> None:
        """Inserts records indexing active system schemas."""
        with self._lock:
            self._cache[key] = {
                "val": val,
                "timestamp": time.time()
            }
            
    def delete(self, key: str) -> None:
        """Manually invalidates a specific cache record."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                
    def clear(self) -> None:
        """Manually purges all records in cache."""
        with self._lock:
            self._cache.clear()

# Singleton caching service instance
_global_schema_cache = SchemaCache()

def cache_schema(ttl: Optional[int] = None) -> SchemaCache:
    """Returns a thread-safe TTL schema cache configuration manager."""
    if ttl is None:
        return _global_schema_cache
    return SchemaCache(ttl)

