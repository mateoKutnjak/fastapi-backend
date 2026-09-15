import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import settings
from app.core.exceptions.domain_exceptions import ExpiredTokenError, InvalidTokenError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def generate_random_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(
    subject: uuid.UUID | str,
    expires_delta: int | None = None,
) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + timedelta(minutes=expires_delta)
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    payload = {"sub": str(subject), "exp": expire}

    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def verify_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )

    except jwt.DecodeError as e:
        raise InvalidTokenError("Token is malformed") from e

    except jwt.ExpiredSignatureError as e:
        raise ExpiredTokenError() from e

    except (jwt.InvalidTokenError, ValueError) as e:
        raise InvalidTokenError("Invalid authentication credentials") from e

    return uuid.UUID(payload.get("sub"))


def hash_string(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
