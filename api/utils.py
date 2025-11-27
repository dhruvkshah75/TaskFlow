from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

def verify_hash(plain_value: str, hashed_value: str) -> bool:
    """
    Verifies a plain string value against a hashed value.
    Returns True if they match, False otherwise.
    """
    return pwd_context.verify(plain_value, hashed_value)