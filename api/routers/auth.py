from fastapi import APIRouter, Depends, status, HTTPException, Response
from .. import oauth2, utils, schemas
from core import models, database
from sqlalchemy.orm import Session
from sqlalchemy import or_
from core.redis_client import get_redis
import redis, json, logging 

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
    user_key_email = f"user:profile:email:{user_credentials.identifier}"
    user_key_username = f"user:profile:username:{user_credentials.identifier}"

    cached_user_data = redis_client.get(user_key_email) or redis_client.get(user_key_username)

    if cached_user_data:
        logger.info(f"Cache HIT: User:{user_credentials.identifier} found in the cache")
        user_data = json.loads(cached_user_data)
        user = schemas.UserResponse(**user_data)

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

    # Cache user data
    user_profile_key = f"user:profile:id:{user.id}"
    user_data_to_cache = {
        "id": user.id,
        "email": user.email,
        "username": user.username
    }
    redis_client.setex(user_profile_key, 3600, json.dumps(user_data_to_cache))

    # Create JWT access token
    access_token = oauth2.create_access_token(data={"user_id": user.id})

    return {"access_token": access_token, "token_type": "bearer"}
