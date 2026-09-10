# from pydantic import SecretStr
import os

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database

    database_url: str

    # URL

    server_url: str
    api_prefix: str

    # Security

    secret_key: SecretStr
    algorithm: str = "HS256"

    # Authentication tokens

    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 10080

    # Email

    email_verification_token_expire_seconds: int = 3600

    # Admin

    admin_secret_key: SecretStr

    # Mail

    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_starttls: bool = False
    mail_ssl_tls: bool = True
    suppress_send: bool = False


settings = Settings()
