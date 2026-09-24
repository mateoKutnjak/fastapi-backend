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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: Password


class SetPasswordRequest(BaseModel):
    new_password: Password


class SessionMetadata(BaseModel):
    device_name: str | None = Field(default=None, max_length=255)
    device_id: str | None = Field(default=None, max_length=255)
    user_agent: str | None = Field(default=None, max_length=512)
    ip_address: str | None = Field(default=None, max_length=45)
