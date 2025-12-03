import redis, time
from core.redis_client import get_redis 
from fastapi import Request, status, Depends, HTTPException
from .oauth2 import get_current_user
from core.models import User
from core.config import settings


class RateLimiter:
    """
    A Redis implemented sliding window rate limiter 
    """
    def __init__(self, limit: int, window_seconds: int):
        """
        Constructor to initialize the values
        limit (int): The maximum no of requests allowed 
        window_seconds (int): The duration of the time window
        """
        self.limit = limit
        self.window_seconds = window_seconds


    def is_rate_limited(self, redis_client: redis.Redis, identifier: str) -> bool:
        """
        Checks if the given identifier has exceeded the rate limit
        identifier is the unique key for the requester eg user.id 
        This function returns true if the request should be blocked, 
        false if the request should be allowed 
        """

        user_key = f"rate_limit:{identifier}"
        # store the current time in ms 
        current_time_ms = int(time.time() * 1000)

        # Create a pipeline to execute tasks one after the other 
        pipeline = redis_client.pipeline()
        # Remove timestamps older than the window
        oldest_allowed_time_ms = current_time_ms - (self.window_seconds * 1000)
        pipeline.zremrangebyscore(user_key, 0, oldest_allowed_time_ms)

        # Add the current request's timestamp
        pipeline.zadd(user_key, {current_time_ms: current_time_ms})
        # Count the number of requests in the current window
        pipeline.zcard(user_key)
        # Set an expiration on the key to auto-delete it for inactive users
        pipeline.expire(user_key, self.window_seconds)

        # Execute all commands in one go
        results = pipeline.execute()
        request_count = results[2]  # The result of the zcard command

        return request_count > self.limit



def user_rate_limiter(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user)
):
    """
    A FastAPI dependency that applies rate limiting based on the current user's ID.
    """
        
    limiter = RateLimiter(
        limit = settings.USER_RATE_LIMIT_PER_HOUR,
        window_seconds=3600 # 1 hour
    )

    user_identifier = f"user:{current_user.id}"

    if limiter.is_rate_limited(redis_client, user_identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Limit is {settings.USER_RATE_LIMIT_PER_HOUR}"
        )


def ip_rate_limiter(
        request 
):
    pass