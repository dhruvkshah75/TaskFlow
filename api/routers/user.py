from .. import schemas, utils
from fastapi import status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from core.database import get_db
from core import models
from sqlalchemy import or_
from core.redis_client import get_redis
import redis, json, logging
from ..utils import cache_user_data, check_cache_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags = ['Users']
)

# USER crud operations
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResponse)
def create_user(user_credentials: schemas.UserCreate, db: Session=Depends(get_db), 
                redis_client: redis.Redis = Depends(get_redis)):
    """
    This module provides CRUD operations for managing user accounts in the TaskFlow application.
    Key Features:
    1. **User Creation**:
    - Handles the creation of new user accounts.
    - Ensures that `email` and `username` are unique by checking both the Redis cache and the database.
    - Implements caching for user data using Redis to optimize performance and reduce database load.

    2. **User Retrieval**:
    - Provides an endpoint to fetch user details by `user_id`.
    - Returns user information in a structured response model.
    
    3. **Caching Strategy**:
    - Caches user data upon creation using `email` and `username` as keys.
    - Ensures quick validation of unique constraints for `email` and `username` during user creation.
    - Uses a Time-To-Live (TTL) of 1 hour for cached data to maintain consistency.

    4. **Logging**:
    - Logs cache hits, misses, and database queries to provide insights into the application's behavior.

    This module is designed to ensure efficient user management while maintaining data integrity 
    and performance through effective caching and logging practices.
    """
    # Check cache for email or username
    cached_user_data = check_cache_user(redis_client, user_credentials.email) or check_cache_user(redis_client, user_credentials.username)

    if cached_user_data:
        # CACHE HIT
        logger.info(f"Cache HIT: User data found for {user_credentials.email} or {user_credentials.username}")
        if cached_user_data['email'] == user_credentials.email:
            detail = "Email already registered"
        else:
            detail = "Username already registered"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    else:
        # CACHE MISS
        logger.info(f"Cache MISS: No user data found for {user_credentials.email} or {user_credentials.username}")

    # CACHE MISS: Check in the database
    existing_user = db.query(models.User).filter(
        or_(
            models.User.email == user_credentials.email,
            models.User.username == user_credentials.username
        )
    ).first()

    if existing_user:
        # Check which field already exists for a better error message
        if existing_user.email == user_credentials.email:
            detail = "Email already registered"
        else:
            detail = "Username already registered"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=detail)

    # Hash the password
    hashed_password = utils.hash(user_credentials.password)
    user_credentials.password = hashed_password

    # Create the new user from the input credentials
    new_user = models.User(**user_credentials.model_dump())

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Cache the new user data
    logger.info(f"Caching user data for user_id: {new_user.id}")
    cache_user_data(redis_client, {
        "id": new_user.id,
        "email": new_user.email,
        "username": new_user.username
    })

    return new_user



@router.get("/{id}", response_model=schemas.UserResponse)
def get_user(id: int, db: Session=Depends(get_db), redis_client: redis.Redis = Depends(get_redis)):
    """
    Fetch user details by user_id, utilizing Redis cache for optimization.
    """
    # Check cache for user data
    cached_user_data = check_cache_user(redis_client, f"user:profile:{id}")

    if cached_user_data:
        logger.info(f"Cache HIT: User with id:{id} found")
        user_data = schemas.UserResponse(**cached_user_data)
    else:
        logger.info(f"Cache MISS: Checking the database for User with id:{id}")
        user_search_query = db.query(models.User).filter(models.User.id == id)
        user = user_search_query.first()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"User with id: {id} not found")

        # Cache the user data for future requests
        user_data = schemas.UserResponse(**user)
        cache_user_data(redis_client, user_data.model_dump())

    return user_data