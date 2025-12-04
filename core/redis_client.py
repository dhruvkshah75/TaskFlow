import redis
from .config import settings

# Used for: Auth, Caching, Rate Limiting, and "High Priority" Tasks.
# This instance should be kept clean of bulk jobs to ensure low latency for users.
redis_high = redis.Redis(
    host=settings.REDIS_HOST_HIGH, port=settings.REDIS_PORT_HIGH, 
    db=0, decode_responses=True
)

# Used for: Bulk tasks, Reports, Image Processing, etc.
# It is okay if this instance gets backed up with thousands of items.
redis_low = redis.Redis(
    host=settings.REDIS_HOST_LOW, port=settings.REDIS_PORT_LOW, 
    db=0, decode_responses=True
)


def get_redis_client(priority: str = "low") -> redis.Redis:
    """
    Returns the appropriate Redis connection based on priority.
    Used by the Queue Manager (push_task) to route jobs.
    """
    if priority == "high":
        return redis_high
    return redis_low


def get_redis():
    """
    Default FastAPI dependency.
    We FORCE this to use 'redis_high' for system-critical operations
    like Rate Limiting, Authentication, and Caching.
    This ensures your Login/Auth never lags, even if the worker queue (redis_low) is full.
    """
    return redis_high