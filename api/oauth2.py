from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from . import schemas
from core import database, models
from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session
from core.config import settings

from core.redis_client import get_redis
from .utils import verify_hash, hash_value 
import redis



oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

# SECRET_KEY 
# Algorithm
# Experation time

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

RATE_LIMIT_PER_HOUR = settings.RATE_LIMIT_PER_HOUR
USER_RATE_LIMIT_PER_HOUR = settings.USER_RATE_LIMIT_PER_HOUR
MAX_FAILED_ATTEMPTS = settings.MAX_FAILED_ATTEMPTS
LOCKOUT_DURATION_SECONDS = settings.LOCKOUT_DURATION_SECONDS

api_key_header = APIKeyHeader(name="X-API-Key")


# the token consists of payload data
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) 
    # this means it will expire 30 minutes after the current time
    to_encode.update({"exp": expire})

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return token




def verify_access_token(token: str, credentials_exception):
    """
    To check if no manupilations have been made to our token and token has not expired 
    """
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get("user_id")

        if id is None:
            raise credentials_exception
        token_data = schemas.Token_data(id=id)
    except JWTError:
        raise credentials_exception
    
    return token_data



def get_current_user_token(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    """
    This function returns the current user that is trying to access the the reuqest like posting a post, updating a post
    deleting a post etc, by checking if the token to that user is valid or not 
    """
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                          detail=f"Could not validate credentials",
                                          headers={"WWW-Authenticate": "Bearer"})
    
    token_data = verify_access_token(token, credentials_exception)
    
    user = db.query(models.User).filter(models.User.id == token_data.id).first()

    return user




def get_user_from_api_key(key: str, db: Session, redis_client: redis.Redis):
    """
    Authenticates a user via an API key.
    Handles lockouts, expiration, and rate limiting.
    (This is not a dependency itself but a helper for the master function).
    """
    hashed_key_for_redis = hash_value(key)

    lockout_redis_key = f"lockout:{hashed_key_for_redis}"

    if redis_client.exists(lockout_redis_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail="Account locked due to too many failed attempts.")

    all_keys = db.query(models.ApiKey).all()

    valid_key_record = next((k for k in all_keys if verify_hash(key, k.key_hash)), None)

    if not valid_key_record:
        failed_attempts_key = f"failed_attempts:{hashed_key_for_redis}"

        current_failures = redis_client.incr(failed_attempts_key)

        redis_client.expire(failed_attempts_key, LOCKOUT_DURATION_SECONDS)

        if current_failures >= MAX_FAILED_ATTEMPTS:
            redis_client.setex(lockout_redis_key, LOCKOUT_DURATION_SECONDS, "locked")
            redis_client.delete(failed_attempts_key)

        return None

    successful_auth_failed_attempts_key = f"failed_attempts:{hashed_key_for_redis}"

    redis_client.delete(successful_auth_failed_attempts_key)

    if not valid_key_record.is_active or (valid_key_record.expires_at and valid_key_record.expires_at < datetime.now(timezone.utc)):
        return None 





def get_current_user(
    token: str = Depends(oauth2_scheme),
    api_key: str = Depends(api_key_header),
    db: Session = Depends(database.get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    The primary security dependency for API endpoints.
    Authenticates a user via EITHER a JWT Bearer Token OR an X-API-Key header
    and applies the appropriate rate limit.
    """
    user = None
    
    # Priority 1: Try to authenticate with JWT
    if token:
        user = get_current_user_token(token=token, db=db)
        if user:
            # Apply user-based rate limiting for JWT sessions
            current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
            redis_key = f"rate_limit:user:{user.id}:{current_hour}"
            request_count = redis_client.incr(redis_key)

            if request_count == 1:
                redis_client.expire(redis_key, 3600)

            if request_count > USER_RATE_LIMIT_PER_HOUR:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
                                    detail="User rate limit exceeded.")

    # Priority 2: If no valid user from JWT, try API key
    if not user and api_key:
        user = get_user_from_api_key(key=api_key, db=db, redis_client=redis_client)

    # If after checking both methods, we still have no user, then fail.
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user


## Make changes to the code by adding a different function for rate limit checking 