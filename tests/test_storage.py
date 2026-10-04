"""Local storage contracts; all filesystem effects stay in tmp_path."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import settings
from app.core.exceptions.domain_exceptions import (
    FileDeleteError,
    FileInvalidFilenameError,
    FileSaveError,
    StorageBackendNotSupportedError,
)
from app.core.storage import LocalStorage, get_storage

MAX_FILENAME_BYTES = 255


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "local_storage_upload_dir", str(tmp_path))
    return LocalStorage()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    ["photo.jpg", "my photo!.jpg", "你好.png", "a" * 300 + ".png", ".hidden"],
)
async def test_save_unique_safe_names_and_exact_bytes(storage, filename):
    first = await storage.save(filename, b"arbitrary file bytes", ".pdf")
    second = await storage.save(filename, b"second", ".pdf")
    assert first != second
    assert Path(first).name == first
    assert first.endswith(".pdf")
    assert len(first.encode()) < MAX_FILENAME_BYTES
    assert (storage.upload_dir / first).read_bytes() == b"arbitrary file bytes"
    assert (storage.upload_dir / second).read_bytes() == b"second"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", [None, "", ".", "..", "../x", "/outside/x", "a/b", "a\\b", "C:x", "a\x00b"]
)
async def test_invalid_names_never_touch_disk(storage, name):
    with pytest.raises(FileInvalidFilenameError):
        await storage.save(name, b"test", ".png")
    with pytest.raises(FileInvalidFilenameError):
        await storage.delete(name)
    assert list(storage.upload_dir.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extension", ["png", ".", ".PNG", "../png", ".a/b", ".a" * 10, ""]
)
async def test_invalid_extensions(storage, extension):
    with pytest.raises(FileInvalidFilenameError):
        await storage.save("photo.png", b"test", extension)
    assert list(storage.upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_delete_is_idempotent_and_preserves_other_files(storage):
    key = await storage.save("file.txt", b"one", ".txt")
    other = await storage.save("file.txt", b"two", ".txt")
    await storage.delete(key)
    await storage.delete(key)
    assert not (storage.upload_dir / key).exists()
    assert (storage.upload_dir / other).read_bytes() == b"two"


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_partial_write_failure_preserves_cause(storage, cleanup_fails, caplog):
    original_write = Path.write_bytes
    original_unlink = Path.unlink
    failure = OSError("disk full")

    def fail_write(path, data):
        original_write(path, data[:2])
        raise failure

    def unlink(path, **kwargs):
        if cleanup_fails:
            raise PermissionError("cleanup denied")
        return original_unlink(path, **kwargs)

    with (
        patch.object(Path, "write_bytes", fail_write),
        patch.object(Path, "unlink", unlink),
    ):
        with pytest.raises(FileSaveError) as caught:
            await storage.save("photo.png", b"abcdef", ".png")
    assert caught.value.__cause__ is failure
    if cleanup_fails:
        assert "partially written" in caplog.text
    else:
        assert list(storage.upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_delete_permission_failure(storage):
    failure = PermissionError("denied")
    with patch.object(Path, "unlink", side_effect=failure):
        with pytest.raises(FileDeleteError) as caught:
            await storage.delete("photo.png")
    assert caught.value.__cause__ is failure


@pytest.mark.asyncio
async def test_missing_upload_directory_is_save_error(storage):
    storage.upload_dir = storage.upload_dir / "missing"
    with pytest.raises(FileSaveError):
        await storage.save("photo.png", b"test", ".png")


@pytest.mark.asyncio
async def test_deleting_symlink_does_not_delete_target(storage, tmp_path):
    target = tmp_path / "target.txt"
    target.write_bytes(b"keep")
    (tmp_path / "link.txt").symlink_to(target)
    await storage.delete("link.txt")
    assert target.read_bytes() == b"keep"


@pytest.mark.parametrize("backend", ["s3", "typo", ""])
def test_unsupported_backend_is_rejected(monkeypatch, backend):
    monkeypatch.setattr(settings, "storage_backend", backend)
    with pytest.raises(StorageBackendNotSupportedError):
        # Current API raises generic Exception; require its specific message.
        get_storage()
