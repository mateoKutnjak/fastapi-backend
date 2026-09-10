import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str | None = Field(None, max_length=50)
    email: EmailStr = Field(max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    identifier: str = Field(max_length=255)
    password: str


class UserResponse(UserBase):
    role: RoleResponse


class UserResponsePrivate(UserResponse):
    id: uuid.UUID
