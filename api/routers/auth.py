from fastapi import APIRouter, Depends, status, HTTPException, Response
from .. import oauth2, utils, schemas
from core import models, database
from sqlalchemy.orm import Session
from sqlalchemy import or_
from core.redis_client import get_redis
import redis, json, logging 
from ..utils import cache_user_data, check_cache_user
from ..rate_limiter import user_rate_limiter

logger = logging.getLogger(__name__)  # to make logs 

router = APIRouter(
    tags=['Authentication']
)


@router.post("/login", response_model=schemas.Token)
def login(
    user_credentials: schemas.UserLogin, 
    db: Session=Depends(database.get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Handles user authentication and caching.
    """
    # check the cache using the utils.py function 
    cached_user_data = check_cache_user(redis_client, f"user:identifier:{user_credentials.identifier}")

    if cached_user_data:
        logger.info(f"Cache HIT: User:{user_credentials.identifier} found in the cache")
        # cached_user_data may already be a dict (returned by check_cache_user)
        if isinstance(cached_user_data, dict):
            user = cached_user_data
        elif isinstance(cached_user_data, (str, bytes, bytearray)):
            # if it is a JSON string for some reason, decode it
            user = json.loads(cached_user_data)

        if not utils.verify(user_credentials.password, user['password']):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail=f'Invalid Credentials')
        
        access_token = oauth2.create_access_token(data={"user_id": user['id']})

        return {"access_token": access_token, "token_type": "bearer"}

    else:
        # Query user by email or username
        logger.info(f"Cache MISS: User:{user_credentials.identifier} not found in cache")
        user_email_query = db.query(models.User).filter(
            or_(
                models.User.email == user_credentials.identifier,
                models.User.username == user_credentials.identifier
            )
        )
        user = user_email_query.first()

        # Account does not exist
        if user is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                                detail=f'Invalid Credentials')
        # Password verification
        if not utils.verify(user_credentials.password, user.password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                                detail=f'Invalid Credentials')
        # Cache user data using utils function
        user_cache = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "password": user.password
        }
        cache_user_data(redis_client, user_cache)

        # Create JWT access token
        access_token = oauth2.create_access_token(data={"user_id": user.id})

        return {"access_token": access_token, "token_type": "bearer"}
