from fastapi import HTTPException, Depends, status, APIRouter
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from .. import schemas, oauth2
from core import models, database
import secrets, redis
from ..utils import hash_api_key
from typing import List
from core.redis_client import get_redis


router = APIRouter(
    prefix = "/api-keys",
    tags = ["API_Keys"]
)


@router.post("/", status_code=status.HTTP_201_CREATED, 
             response_model=schemas.ApiKeyResponse)
def create_api_key(key_options: schemas.createAPIkey,
                    db: Session = Depends(database.get_db), 
                    current_user: models.User = Depends(oauth2.get_current_user),
                    redis_client: redis.Redis = Depends(get_redis)):
    """
    Generate a new API key for the logged in user
    The key will be valid for 30 days (default) or some value 
    """
    new_key  = f"tf_{secrets.token_urlsafe(32)}"

    expires = datetime.now(timezone.utc) + timedelta(days=key_options.days)

    key_record = models.ApiKey(
        key_hash = hash_api_key(new_key),
        owner_id = current_user.id,
        expires_at = expires
    )

    db.add(key_record)
    db.commit()
    db.refresh(key_record)

    # Cache the API key
    api_key_key = f"user:profile:api_key:{key_record.key_hash}"
    api_key_info = {
        "api_key": key_record.key_hash,
        "owner_id": key_record.owner_id,
        "expires_at": key_record.expires_at if key_record.expires_at else None
    }

    

    return {
        "api_key": new_key,
        "expires_at": expires
    }



@router.get("/", response_model=List[schemas.ApiKeyInfo])
def get_user_api_keys(db: Session=Depends(database.get_db),
                      current_user: models.User = Depends(oauth2.get_current_user)):
    
    """
    Get the list of all the API keys for the current user.
    This does not return the keys themselves, only the safe metadata
    """

    keys = db.query(models.ApiKey).filter(
        models.ApiKey.owner_id == current_user.id
    ).all()




@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_api_key(key_id: int, db: Session = Depends(database.get_db),
                   current_user: models.User = Depends(oauth2.get_current_user)):
    """
    Remove (delete) an API key by its ID.
    """

    key_query = db.query(models.ApiKey).filter(
        models.ApiKey.id == key_id
    )
    key_to_delete = key_query.first()

    if key_to_delete == None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail = f"API Key with id: {key_id} not found"
        )
    
    if key_to_delete.owner_id != current_user.id:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail = "Not authorized to perform requested action."
        )
    
    key_query.delete(synchronize_session=False)
    db.commit()

    return