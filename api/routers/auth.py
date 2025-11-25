from fastapi import APIRouter, Depends, status, HTTPException, Response
from .. import oauth2, utils, schemas
from core import models, database
from sqlalchemy.orm import Session
from sqlalchemy import or_

router = APIRouter(
    tags=['Authentication']
)


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session=Depends(database.get_db)):
    """
    It is post operation as the user provides in with the email and password
    Checks if the email is present in the database or not and then 
    verifies if the password is correct with the help of utils.py file 
    and creates a jwt token for the user
    """
    user_email_query = db.query(models.User).filter(
        or_(
            models.User.email == user_credentials.identifier,
            models.User.username_id == user_credentials.identifier
        )
    )

    user = user_email_query.first()

    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                            detail=f'Invalid Credentials')
    else:
        if not utils.verify(user_credentials.password, user.password):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                                detail=f'Invalid Credentials')
    # create a token from the oauth2.py with the payload data as user_id
    access_token = oauth2.create_access_token(data={"user_id": user.id})

    
    return {"access_token": access_token, "token_type": "bearer"}
