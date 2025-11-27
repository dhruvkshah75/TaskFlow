import redis
from .config import settings

REDIS_HOST = settings.REDIS_HOST
REDIS_PORT = settings.REDIS_PORT

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, 
                           db=0, decode_responses=True)

def get_redis():
    """FastAPI dependency to get the Redis client."""
    return redis_client