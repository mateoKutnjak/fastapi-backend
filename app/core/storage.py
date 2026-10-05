import logging
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.core.exceptions.domain_exceptions import (
    FileDeleteError,
    FileInvalidFilenameError,
    FileSaveError,
    StorageBackendNotSupportedError,
)


class Storage(ABC):
    @abstractmethod
    async def save(self, filename: str | None, data: bytes, extension: str) -> str:
        pass

    # @abstractmethod
    # async def load(self, file_path: str) -> bytes:
    #     pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass


class LocalStorage(Storage):
    def __init__(self):
        self.upload_dir = Path(settings.local_storage_upload_dir).resolve()
        # mkdir is not called here because it is called in main.py

    async def save(self, filename: str | None, data: bytes, extension: str) -> str:
        filename = validate_filename(filename)

        unique_filename = generate_unique_filename(filename, extension)
        file_path = self.upload_dir / unique_filename

        try:
            await run_in_threadpool(file_path.write_bytes, data)
        except OSError as e:
            try:
                await run_in_threadpool(file_path.unlink, missing_ok=True)
            except OSError:
                logging.exception("Failed to remove partially written upload")
            raise FileSaveError() from e

        return unique_filename

    # async def load()

    async def delete(self, key: str) -> None:
        filename = validate_filename(key)
        file_path = self.upload_dir / filename

        try:
            await run_in_threadpool(file_path.unlink, missing_ok=True)
        except OSError as e:
            raise FileDeleteError() from e


class S3Storage(Storage):
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
            region_name=settings.aws_region,
        )
        self.bucket_name = settings.aws_s3_bucket_name

    async def save(self, filename: str | None, data: bytes, extension: str) -> str:
        filename = validate_filename(filename)

        unique_filename = generate_unique_filename(filename, extension)

        try:
            await run_in_threadpool(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=unique_filename,
                Body=data,
            )
        except (BotoCoreError, ClientError, OSError) as e:
            raise FileSaveError() from e

        return unique_filename

    async def delete(self, key: str) -> None:
        filename = validate_filename(key)
        try:
            await run_in_threadpool(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=filename,
            )
        except (BotoCoreError, ClientError, OSError) as e:
            raise FileDeleteError() from e


def get_storage() -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage()
    if settings.storage_backend == "s3":
        return S3Storage()
    raise StorageBackendNotSupportedError()


def validate_filename(filename: str | None) -> str:
    if (
        not filename
        or filename in {".", ".."}
        or any(char in filename for char in ("\x00", "/", "\\", ":"))
    ):
        raise FileInvalidFilenameError()

    return filename


def generate_unique_filename(filename: str, extension: str) -> str:
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", extension):
        raise FileInvalidFilenameError()

    original = (filename).replace("\\", "/")
    stem = Path(original).stem
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)
    stem = stem.strip("_")[:100]

    return f"{stem}_{uuid.uuid4().hex}{extension}"
