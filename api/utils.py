from passlib.context import CryptContext
import hashlib
import redis, json
import logging
from datetime import datetime

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
def cache_api_key(redis_client: redis.Redis, api_key_data: dict, ttl: int=3600):
    """
    The functions creates a cache of the api key with the main caching key as api_key id 
    and creating mapping of api_key_hash with the api_key_id so cache can be checked 
    both ways 
    Args:
        api_key_data is a dict which contains the hashed api key, the api_key id and 
        expires at time 
    """
    api_key_cache = {
        "id": api_key_data['id'],
        "api_key": api_key_data['api_key'],
        "expires_at": datetime.isoformat(api_key_data['expires_at']),
        "owner_id": api_key_data['owner_id'],
        "user": api_key_data['user']
    }
    redis_client.setex(f"user:profile:api_key:{api_key_data['api_key']}", ttl, 
                       json.dumps(api_key_cache))
    logger.info(f"Cached api key details for the user with id:{api_key_cache['owner_id']}")


def check_cache_api(redis_client: redis.Redis, check_key: str):
    """
    Checks the cache for the api key with using the hashed key 
    """
    user_data = redis_client.get(check_key)
    if user_data:
        logger.info(f"Cache HIT for {check_key}")
        return json.loads(user_data)

    logger.info(f"Cache MISS for {check_key}")
    return None  # Cache miss


# ============== HELPER FUNCTION TO CREATE HASH FOR CACHE TASKS ===================
def generate_task_hash(user_id: int, title: str, payload: str) -> str:
    """
    Creates a deterministic SHA256 hash based on the user_id, task title and
    optional payload. The payload (if dict/list) is canonicalized with
    sorted keys so equivalent payloads produce the same hash.
    This is used for cache keys and lightweight duplicate detection.
    """
    title_norm = (title or "").strip().lower()

    if payload is None:
        payload_str = ""
    else:
        # Canonicalize JSON-like payloads for deterministic hashing
        try:
            if isinstance(payload, (dict, list)):
                payload_str = json.dumps(payload, sort_keys=True, 
                                         separators=(",", ":"), ensure_ascii=False)
            else:
                payload_str = str(payload)
        except Exception:
            # Fallback to string conversion if json serialization fails
            payload_str = str(payload)

    raw_string = f"{int(user_id)}:{title_norm}:{payload_str}"
    return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()


# ================== CACHE UTIL FUNCTIONS FOR TASKS ==================
def cache_task(redis_client: redis.Redis, task_data: dict):
    """
    We create a key based on the hash of the owner_id and title of the task 
    and then store it in the cache with the key as {task:hash}
    """
    # Support optional payload in task_data for more precise duplicate detection
    hash_val = generate_task_hash(int(task_data['owner_id']), task_data['title'], task_data['payload'])

    task_key = f"task:{hash_val}"

    redis_client.setex(task_key, 3600, json.dumps(task_data))
    logger.info(f"Cached task detils for the user:{task_data['owner_id']}")


def check_cache_task(redis_client: redis.Redis, task_title: str, owner_id: int, payload: str):
    """
    Here we check the cache based on hashed value of task_title and owner_id
    """
    # Backwards compatible: payload is optional and may be added later
    hash_val = generate_task_hash(owner_id, task_title, payload)
    
    task_key = f"task:{hash_val}"

    cached_task_data = redis_client.get(task_key)
    if cached_task_data:
        logger.info(f"Cache HIT for the key:{task_key}")
        return json.loads(cached_task_data)
    else:
        logger.info(f"Cache MISS for the key:{task_key}")
        return None