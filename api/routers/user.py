from .. import schemas, utils, oauth2
from fastapi import status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from core.database import get_db
from core import models
from sqlalchemy import or_
from core.redis_client import get_redis
import redis, json, logging

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
    user_key_email = f"user:profile:email:{user_credentials.email}"
    user_key_username = f"user:profile:username:{user_credentials.username}"

    user_data_email = redis_client.get(user_key_email)
    user_data_username = redis_client.get(user_key_username)

    if user_data_email:
        logger.info(f"Cache HIT: Email {user_credentials.email} already registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email already registered"
        )
    elif user_data_username:
        logger.info(f"Cache HIT: Username {user_credentials.username} already registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username already registered"
        ) 
    else:
        logger.info(f"Cache MISS: Checking database for {user_credentials.email} or {user_credentials.username}")
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
            logger.info(f"Database HIT: {detail}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=detail)
    
    # hash the password 
    hashed_password = utils.hash(user_credentials.password)
    user_credentials.password = hashed_password
    
    # Create the new user from the input credentials
    new_user = models.User(**user_credentials.model_dump())

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    add_user_key_email = f"user:profile:email:{new_user.email}"
    add_user_key_username = f"user:profile:username:{new_user.username}"
    add_user_key_id = f"user:profile:id:{new_user.id}"

    user_data_to_cache = {
        "id": new_user.id,
        "email": new_user.email,
        "username": new_user.username
    }

    redis_client.setex(add_user_key_email, 3600, 
                       json.dumps(user_data_to_cache))
    redis_client.setex(add_user_key_username, 3600,
                       json.dumps(user_data_to_cache))
    redis_client.setex(add_user_key_id, 3600,
                       json.dumps(user_data_to_cache))

    return new_user



@router.get("/{id}", response_model=schemas.UserResponse)
def get_user(id: int, db: Session=Depends(get_db), redis_client: redis.Redis = Depends(get_redis)):

    user_key_id = f"user:profile:id:{id}"

    user_data_cached = redis_client.get(user_key_id)

    if user_data_cached:
        logger.info(f"Cache HIT: User with id:{id} found")
        user_data_json = json.loads(user_data_cached)
        user_data = schemas.UserResponse(**user_data_json)

    else:
        logger.info(f"Cache MISS: Checking the databse for User with id:{id}")
        user_search_query = db.query(models.User).filter(models.User.id == id)
        if user_search_query.first() == None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="User with id: {id} not found")
        user_data = user_search_query.first()

    return user_data