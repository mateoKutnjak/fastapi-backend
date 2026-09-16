from pydantic import BaseModel, EmailStr, Field

from app.core.passwords import Password


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: Password


class GoogleAuthRequest(BaseModel):
    id_token: str
