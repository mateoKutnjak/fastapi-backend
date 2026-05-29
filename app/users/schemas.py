import uuid

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str | None = Field(None, max_length=50)
    email: EmailStr = Field(max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserResponse(UserBase):
    pass


class UserResponsePrivate(UserResponse):
    id: uuid.UUID
