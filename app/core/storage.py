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
    FileSaveError,
    StorageBackendNotSupportedError,
    StorageInvalidFilenameError,
    StorageInvalidFilePathError,
    StorageInvalidSubfolderFormatError,
)


class Storage(ABC):
    @abstractmethod
    async def save(
        self, filename: str | None, data: bytes, extension: str, subfolder: str
    ) -> str:
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

    async def save(
        self, filename: str | None, data: bytes, extension: str, subfolder: str
    ) -> str:
        validate_filename(filename)
        validate_subfolder(subfolder)

        unique_filename = generate_unique_filename(filename, extension)
        file_path = self.upload_dir / subfolder / unique_filename

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except (FileNotFoundError, OSError) as e:
            logging.exception("Failed to create upload directory")
            raise FileSaveError() from e

        try:
            await run_in_threadpool(file_path.write_bytes, data)
        except OSError as e:
            try:
                await run_in_threadpool(file_path.unlink, missing_ok=True)
            except OSError:
                logging.exception("Failed to remove partially written upload")
            raise FileSaveError() from e

        return f"{subfolder}/{unique_filename}"

    # async def load()

    async def delete(self, key: str) -> None:
        validate_file_path(key)

        file_path = self.upload_dir / key

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

    async def save(
        self, filename: str | None, data: bytes, extension: str, subfolder: str
    ) -> str:
        validate_filename(filename)
        validate_subfolder(subfolder)

        unique_filename = generate_unique_filename(filename, extension)

        try:
            await run_in_threadpool(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=f"{subfolder}/{unique_filename}",
                Body=data,
            )
        except (BotoCoreError, ClientError, OSError) as e:
            raise FileSaveError() from e

        return f"{subfolder}/{unique_filename}"

    async def delete(self, key: str) -> None:
        validate_file_path(key)

        try:
            await run_in_threadpool(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=key,
            )
        except (BotoCoreError, ClientError, OSError) as e:
            raise FileDeleteError() from e


def get_storage() -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage()
    if settings.storage_backend == "s3":
        return S3Storage()
    raise StorageBackendNotSupportedError()


def validate_file_path(file_path: str) -> None:
    parts = file_path.split("/")

    if len(parts) == 0:
        raise StorageInvalidFilePathError()
    elif len(parts) == 1:
        validate_filename(parts[0])
    elif len(parts) > 1:
        validate_subfolder("/".join(parts[:-1]))
        validate_filename(parts[-1])


def validate_filename(filename: str | None) -> None:
    if (
        not filename
        or filename in {".", ".."}
        or any(char in filename for char in ("\x00", "/", "\\", ":"))
    ):
        raise StorageInvalidFilenameError()


def validate_subfolder(subfolder: str) -> None:
    parts = subfolder.split("/")
    if (
        not subfolder
        or any("\\" in part for part in parts)
        or any(char in part for part in parts for char in ("\x00", ":"))
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise StorageInvalidSubfolderFormatError()


def generate_unique_filename(filename: str, extension: str) -> str:
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", extension):
        raise StorageInvalidFilenameError()

    original = (filename).replace("\\", "/")
    stem = Path(original).stem
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)
    stem = stem.strip("_")[:100]

    return f"{stem}_{uuid.uuid4().hex}{extension}"
