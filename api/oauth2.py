from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from . import schemas, database, models
from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

# SECRET_KEY 
# Algorithm
# Experation time

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

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


    
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
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
