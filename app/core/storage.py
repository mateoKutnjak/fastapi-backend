import logging
import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

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
        filename = self.validate_filename(filename)

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
        filename = self.validate_filename(key)
        file_path = self.upload_dir / filename

        try:
            await run_in_threadpool(file_path.unlink, missing_ok=True)
        except OSError as e:
            raise FileDeleteError() from e

    def validate_filename(self, filename: str | None) -> str:
        if (
            not filename
            or filename in {".", ".."}
            or any(char in filename for char in ("\x00", "/", "\\", ":"))
        ):
            raise FileInvalidFilenameError()

        return filename


def get_storage() -> Storage:
    if settings.storage_backend != "local":
        raise StorageBackendNotSupportedError()
    return LocalStorage()


def generate_unique_filename(filename: str, extension: str) -> str:
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", extension):
        raise FileInvalidFilenameError()

    original = (filename).replace("\\", "/")
    stem = Path(original).stem
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)
    stem = stem.strip("_")[:100]

    return f"{stem}_{uuid.uuid4().hex}{extension}"
