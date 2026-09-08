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

    database_url: str

    server_url: str
    api_prefix: str

    secret_key: SecretStr
    algorithm: str = "HS256"

    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 10080

    email_verification_token_expire_seconds: int = 3600

    # max_upload_size_bytes: int = 5 * 1024 * 1024  # 5 MB

    # reset_token_expire_minutes: int = 60

    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_starttls: bool = False
    mail_ssl_tls: bool = True
    suppress_send: bool = False

    # s3_bucket_name: str
    # s3_region: str = "eu-north-1"
    # s3_access_key_id: SecretStr | None = None
    # s3_secret_access_key: SecretStr | None = None
    # s3_endpoint_url: str | None = None


settings = Settings()
