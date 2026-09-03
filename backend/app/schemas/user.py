from pydantic import BaseModel, EmailStr
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    tiktok_token: Optional[str] = None
    instagram_token: Optional[str] = None
    youtube_token: Optional[str] = None


class UserResponse(UserBase):
    id: str
    is_active: bool
    tiktok_token: Optional[str] = None
    instagram_token: Optional[str] = None
    youtube_token: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
