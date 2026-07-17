import json
from typing import Any, Optional
import redis

from backend.config import settings

# Initialize Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def get_cache(key: str) -> Optional[Any]:
    """Retrieve and deserialize a value from Redis."""
    try:
        val = redis_client.get(key)
        if val:
            return json.loads(val)
        return None
    except Exception as e:
        print(f"[Redis Warning] Error reading from cache for key {key}: {e}")
        return None

def set_cache(key: str, value: Any, ex: Optional[int] = None) -> bool:
    """Serialize and store a value in Redis with an optional expiration in seconds."""
    try:
        val = json.dumps(value)
        redis_client.set(name=key, value=val, ex=ex)
        return True
    except Exception as e:
        print(f"[Redis Warning] Error writing to cache for key {key}: {e}")
        return False

def delete_cache(key: str) -> bool:
    """Delete a specific key from Redis."""
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"[Redis Warning] Error deleting cache for key {key}: {e}")
        return False

def delete_cache_pattern(pattern: str) -> bool:
    """Delete all keys matching a specific pattern (e.g., 'session:user_id:*')."""
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        return True
    except Exception as e:
        print(f"[Redis Warning] Error deleting cache pattern {pattern}: {e}")
        return False
