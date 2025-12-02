from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from . import schemas
from core import database, models
from fastapi import Depends, status, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session
from core.config import settings

# Use the dedicated redis client file
from core.redis_client import get_redis
from .utils import hash_api_key 
import redis, json, logging
from datetime import datetime

logger = logging.getLogger(__name__)

# the auto error means that even if the token method fails the api key method might work so try that 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login', auto_error=False) 
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Config
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
MAX_FAILED_ATTEMPTS = settings.MAX_FAILED_ATTEMPTS
LOCKOUT_DURATION_SECONDS = settings.LOCKOUT_DURATION_SECONDS


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) 
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token




def verify_access_token(token: str, credentials_exception):
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get("user_id")
        if id is None:
            raise credentials_exception
        token_data = schemas.Token_data(id=id)
    except JWTError:
        raise credentials_exception
    return token_data



def handle_auth_failure(redis_client: redis.Redis, client_ip: str):
    """
    Helper to increment failed attempts and lock out IP if limit reached.
    """
    failed_attempts_key = f"failed:ip:{client_ip}"
    ip_lockout_key = f"lockout:ip:{client_ip}"

    current_failures = redis_client.incr(failed_attempts_key)
    
    # Set expiry on first failure
    if current_failures == 1:
        redis_client.expire(failed_attempts_key, LOCKOUT_DURATION_SECONDS)

    # Check threshold
    if current_failures >= MAX_FAILED_ATTEMPTS:
        redis_client.setex(ip_lockout_key, LOCKOUT_DURATION_SECONDS, "locked")
        redis_client.delete(failed_attempts_key)




def check_ip_lockout(redis_client: redis.Redis, client_ip: str):
    """
    Helper to check if IP is currently locked out.
    """
    ip_lockout_key = f"lockout:ip:{client_ip}"
    if redis_client.exists(ip_lockout_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Too many failed attempts. Try again later."
        )
    



def get_current_user_token(token: str, db: Session, redis_client: redis.Redis, client_ip: str):
    """
    Verifies JWT, fetches user data from cache or DB, and returns a consistent user object.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        # 1. Verify JWT signature and get user ID
        token_data = verify_access_token(token, credentials_exception)

        user_id = token_data.id
        user_profile_key = f"user:profile:id:{user_id}"
        # 2. Check cache first
        cached_user_profile = redis_client.get(user_profile_key)

        if cached_user_profile:
            logger.info(f"Cache HIT: User with the id:{id} found")
            user_dict = json.loads(cached_user_profile)
            user = schemas.UserResponse(**user_dict)
        else:
            logger.info(f"Cache MISS: Searching the database for user with the id:{id}")
            user_from_db = db.query(models.User).filter(models.User.id == user_id).first()
            if not user_from_db:
                raise credentials_exception

            user_data_to_cache = {
                "id": user_from_db.id,
                "email": user_from_db.email,
                "username": user_from_db.username
            }

            # Populate the cache for the next request
            redis_client.setex(
                user_profile_key, 3600,
                json.dumps(user_data_to_cache)
            )
            user = user_from_db

        # 3. SUCCESS! Forgive any IP-based lockouts
        redis_client.delete(f"lockout:ip:{client_ip}")
        redis_client.delete(f"failed:ip:{client_ip}")

        return user

    except Exception:
        # 4. FAILURE: Handle failed attempts and IP lockouts
        handle_auth_failure(redis_client, client_ip)
        check_ip_lockout(redis_client, client_ip)
        raise credentials_exception




def get_user_from_api_key(api_key: str, db: Session, client_ip: str, redis_client: redis.Redis):
    """
    Authenticates via API Key with IP-based lockout protection.
    """
    # 1. Check IP Lockout
    check_ip_lockout(redis_client, client_ip)

    # 2. Hash the key for lookup
    hashed_api_key = hash_api_key(api_key)
    # 3. Fast Database Lookup with JOIN
    result = db.query(models.ApiKey).filter(
            models.ApiKey.key_hash == hashed_api_key,
            models.ApiKey.is_active == True
        ).first()

    # 4. Handle Failure
    if not result:
        handle_auth_failure(redis_client, client_ip)
        return None

    api_key_record = result

    # 5. Handle Success (Clear failures)
    redis_client.delete(f"failed:ip:{client_ip}")
    # 6. Check Expiration
    if api_key_record.expires_at and api_key_record.expires_at < datetime.now(timezone.utc):
        return None
    # 7. Auditing: Update last_used_at
    api_key_record.last_used_at = datetime.now(timezone.utc)
    db.commit()

    # retrieving the user
    user = db.query(models.User).filter(
        models.User.id == api_key_record.owner_id
    ).first()
    
    return user



def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    api_key: str = Depends(api_key_header),
    db: Session = Depends(database.get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    client_ip = request.client.host
    user = None

    # 1. JWT Check
    if token:
        try:
            user = get_current_user_token(token, db, redis_client, client_ip)
        except HTTPException as e:
            # If token failure triggered a 403 Lockout, stop here.
            if e.status_code == status.HTTP_403_FORBIDDEN:
                raise e
            # If it was just invalid (401), ignore and try API Key next
            pass

    # 2. API Key Check
    if not user and api_key:
        user = get_user_from_api_key(api_key, db, client_ip, redis_client)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Set the user_id on request state so RateLimiter (or other dependencies) can use it
    # request.state.user_id = user.id
    
    return user