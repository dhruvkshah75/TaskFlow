from passlib.context import CryptContext
import hashlib
import redis, json
import logging

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# ====================== HASH UTILS FOR PASSWORD =========================

def hash(password: str):
    return pwd_context.hash(password)

# compare the raw password with the database's hashed password
def verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def hash_value(value: str) -> str:
    """
    Hashes a given string value using bcrypt.
    """
    return pwd_context.hash(value)

# ================ HASH UTILS FOR API KEYS ========================

def verify_hash(plain_value: str, hashed_value: str) -> bool:
    """
    Verifies a plain string value against a hashed value.
    Returns True if they match, False otherwise.
    """
    return pwd_context.verify(plain_value, hashed_value)



def hash_api_key(key: str) -> str:
    """
    Generates a deterministic SHA256 hash for API Keys.
    Use this for BOTH creating the key (in users.py) and verifying it (in security.py).
    """
    return hashlib.sha256(key.encode()).hexdigest()


# ================ CACHE UTIL FUNCTIONS FOR USER DATA INFORMATION ===============================

def cache_user_data(redis_client: redis.Redis, user: dict):
    """
    Cache user data with mappings for email, username, and user_id.
    Args:
        redis_client (redis.Redis): Redis client instance.
        user (object): User object containing id, email, and username.
    """
    # Create mappings for email and username to user_id
    redis_client.setex(f"user:identifier:{user['email']}", 3600, f"user:profile:{user['id']}")
    redis_client.setex(f"user:identifier:{user['username']}", 3600, f"user:profile:{user['id']}")

    # Store user data using user_id
    user_data = {
        "id": user['id'],
        "email": user['email'],
        "username": user['username'],
        "password": user['password']
    }

    redis_client.setex(f"user:profile:{user['id']}", 3600, json.dumps(user_data))
    logger.info(f"Cached user data for user_id: {user['id']}")


def check_cache_user(redis_client: redis.Redis, identifier_or_id: str):
    """
    Check if user data exists in the cache using email, username, or user_id.
    Args:
        redis_client (redis.Redis): Redis client instance.
        identifier_or_id (str): Email, username, or user_id to check in the cache.
    Returns:
        dict or None: Cached user data if found, otherwise None.
    """
    # Check if the identifier is already a user profile key (pointer)
    # e.g. "user:profile:{id}"
    if str(identifier_or_id).startswith("user:profile:"):
        user_profile_key = str(identifier_or_id)
    else:
        # identifier_or_id is expected to be email or username
        user_profile_key = redis_client.get(identifier_or_id)
        logger.info(user_profile_key)

    if user_profile_key:
        # Fetch user data using user_id
        user_data = redis_client.get(user_profile_key)
        if user_data:
            logger.info(f"Cache hit for {identifier_or_id}")
            return json.loads(user_data)

    logger.info(f"Cache miss for {identifier_or_id}")
    return None  # Cache miss


# ========================= CACHE UTIL FUNCTIONS FOR API-KEYS =================================
def cache_api_key(redis_client: redis.Redis, api_key_data: dict):
    """
    The functions creates a cache of the api key with the main caching key as api_key id 
    and creating mapping of api_key_hash with the api_key_id so cache can be checked 
    both ways 
    Args:
        api_key_data is a dict which contains the hashed api key, the api_key id and 
        expires at time 
    """
    redis_client.setex(f"api_key:{api_key_data['api_key']}", 3600, 
                       f"user:profile:key_id:{api_key_data['id']}")
    api_key_cache = {
        "id": api_key_data['id'],
        "api_key": api_key_data['api_key'],
        "expires_at": api_key_data['expires_at']
    }

    redis_client.setex()

    