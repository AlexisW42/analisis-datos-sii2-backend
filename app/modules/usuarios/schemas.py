from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    admin = "admin"
    analista = "analista"
    user = "user"

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    rol: Optional[UserRole] = UserRole.analista

class UserRegister(UserBase):
    password: str = Field(min_length=6)

class UserLogin(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    rol: UserRole

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
