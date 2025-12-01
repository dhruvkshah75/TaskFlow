from fastapi import APIRouter, Depends, status, HTTPException, Response
from .. import oauth2, utils, schemas
from core import models, database
from sqlalchemy.orm import Session
from sqlalchemy import or_
from core.redis_client import get_redis
import redis, json

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
    This module handles the authentication endpoint (/login) for users. 
    It uses a Redis-backed caching strategy (Read-Through Cache) to store user credentials 
    (hashedpassword and ID)for faster subsequent lookups.  On cache miss, it fetches user data from the PostgreSQL database 
    and populates the cache. It performs password verification and issues a JWT access token upon successful authentication, 
    while invalidating the cache if password verification fails to ensure data consistency.

    This summarizes the core logic:
    1.  Endpoint: /login
    2.  Strategy: Redis Caching (Read-Through)
    3.  Fallback: Database lookup
    4.  Action: Password verification & JWT issuance
    5.  Safety: Cache invalidation on failure
    """

    identifier = user_credentials.identifier
    # cache key for the current user who is trying to login This is what we search in in the redis-cache 
    cache_key = f"user:cache:{identifier}"

    # now we try to fetch the user from cache with this cache_key
    cached_user_data = redis_client.get(cache_key)
    user_data = None

    if cached_user_data: 
        # we found the data in the cache
        user_data = json.loads(cached_user_data)  # store as json
    else: 
        # Not in cache then check in database 
        user_email_query = db.query(models.User).filter(
            or_(
                models.User.email == user_credentials.identifier,
                models.User.username == user_credentials.identifier
            )
        )

        user = user_email_query.first()

        if user:
            # Account exists but not in cache, so we now store in cache for further use 
            user_data = {
                "id": user.id,
                "password": user.password  # Hashed password
            }
            # Save to Redis cache for 1 hour 
            redis_client.setex(cache_key, 3600, json.dumps(user_data))
        else: 
            pass # user not in database 

    # Account does not exist
    if user_data == None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail=f'Invalid Credentials')
    else:
        # Password is incorrect then raise exception and delete the cache based on cache_key 
        if not utils.verify(user_credentials.password, user_data["password"]):
            redis_client.delete(cache_key)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                                detail=f'Invalid Credentials')
        
    # create a token from the oauth2.py with the payload data as user_id
    access_token = oauth2.create_access_token(data={"user_id": user_data["id"]})
    
    return {"access_token": access_token, "token_type": "bearer"}
