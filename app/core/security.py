import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import jwt
from pwdlib import PasswordHash

from app.config import settings
from app.core.exceptions.http_exceptions import UnauthorizedException


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_token(
    subject: uuid.UUID | str, token_type: TokenType, expires_delta: int | None = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
            if token_type == TokenType.ACCESS
            else settings.refresh_token_expire_minutes
        )

    payload = {"sub": str(subject), "exp": expire, "type": str(token_type)}

    return jwt.encode(
        payload, settings.secret_key.get_secret_value(), algorithm=settings.algorithm
    )


def verify_token(token: str, expected_type: TokenType) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub", "type"]},
        )

    except jwt.DecodeError:
        raise UnauthorizedException(detail="Token is malformed")

    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(
            detail="Token has expired",
        )

    except jwt.InvalidTokenError, ValueError:
        raise UnauthorizedException(
            detail="Invalid authentication credentials",
        )

    if payload.get("type") != str(expected_type):
        raise UnauthorizedException(
            detail="Invalid token type",
        )

    return uuid.UUID(payload.get("sub"))
