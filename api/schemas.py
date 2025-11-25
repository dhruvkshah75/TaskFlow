from pydantic import BaseModel, EmailStr
from datetime import datetime 
from typing import Optional

# schema for the user creation
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# schema for the user login information
class UserLogin(BaseModel):
    identifier: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str

class Token_data(BaseModel):
    id: Optional[int] = None

