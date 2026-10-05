"""Local storage contracts and mocked S3 storage behavior."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import SecretStr

from app.config import settings
from app.core.exceptions.domain_exceptions import (
    FileDeleteError,
    FileInvalidFilenameError,
    FileSaveError,
    StorageBackendNotSupportedError,
)
from app.core.storage import LocalStorage, S3Storage, get_storage

MAX_FILENAME_BYTES = 255


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "local_storage_upload_dir", str(tmp_path))
    return LocalStorage()


@pytest.fixture
def s3_storage(monkeypatch):
    monkeypatch.setattr(settings, "aws_access_key_id", "test-access-key")
    monkeypatch.setattr(settings, "aws_secret_access_key", SecretStr("test-secret-key"))
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_s3_bucket_name", "test-uploads")
    client = Mock()
    client_factory = Mock(return_value=client)
    monkeypatch.setattr("app.core.storage.boto3.client", client_factory)
    storage = S3Storage()
    return SimpleNamespace(
        storage=storage, client=client, client_factory=client_factory
    )


def test_s3_storage_configures_client_from_settings(s3_storage):
    s3_storage.client_factory.assert_called_once_with(
        "s3",
        aws_access_key_id="test-access-key",
        aws_secret_access_key=SecretStr("test-secret-key").get_secret_value(),
        region_name="us-east-1",
    )
    assert s3_storage.storage.bucket_name == "test-uploads"


@pytest.mark.asyncio
async def test_s3_save_uploads_exact_bytes_with_unique_safe_keys(s3_storage):
    payload = b"arbitrary image bytes\x00"
    first = await s3_storage.storage.save("photo with spaces!.png", payload, ".png")
    second = await s3_storage.storage.save("photo with spaces!.png", b"second", ".png")

    assert first != second
    assert Path(first).name == first
    assert first.startswith("photo_with_spaces_")
    assert first.endswith(".png")
    s3_storage.client.put_object.assert_any_call(
        Bucket="test-uploads", Key=first, Body=payload
    )
    s3_storage.client.put_object.assert_any_call(
        Bucket="test-uploads", Key=second, Body=b"second"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        None,
        "",
        ".",
        "..",
        "../outside.png",
        "/outside.png",
        "a/b.png",
        "a\\b.png",
        "a\x00b",
    ],
)
async def test_s3_save_rejects_invalid_names_without_request(s3_storage, filename):
    with pytest.raises(FileInvalidFilenameError):
        await s3_storage.storage.save(filename, b"payload", ".png")
    s3_storage.client.put_object.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extension", ["", "png", ".PNG", "../png", ".a/b", ".toolong1234"]
)
async def test_s3_save_rejects_invalid_extensions_without_request(
    s3_storage, extension
):
    with pytest.raises(FileInvalidFilenameError):
        await s3_storage.storage.save("photo.png", b"payload", extension)
    s3_storage.client.put_object.assert_not_called()


@pytest.mark.asyncio
async def test_s3_delete_uses_bucket_and_exact_key(s3_storage):
    await s3_storage.storage.delete("avatar_123.png")

    s3_storage.client.delete_object.assert_called_once_with(
        Bucket="test-uploads", Key="avatar_123.png"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [None, "", ".", "..", "../outside", "a/b", "a\\b"])
async def test_s3_delete_rejects_invalid_keys_without_request(s3_storage, key):
    with pytest.raises(FileInvalidFilenameError):
        await s3_storage.storage.delete(key)
    s3_storage.client.delete_object.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        OSError("socket failure"),
        ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "PutObject",
        ),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
    ],
    ids=["os-error", "aws-client-error", "endpoint-error"],
)
@pytest.mark.asyncio
async def test_s3_save_translates_client_failures_and_preserves_cause(
    s3_storage, failure
):
    s3_storage.client.put_object.side_effect = failure

    with pytest.raises(FileSaveError) as caught:
        await s3_storage.storage.save("photo.png", b"payload", ".png")

    assert caught.value.__cause__ is failure


@pytest.mark.parametrize(
    "failure",
    [
        OSError("socket failure"),
        ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "DeleteObject",
        ),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
    ],
    ids=["os-error", "aws-client-error", "endpoint-error"],
)
@pytest.mark.asyncio
async def test_s3_delete_translates_client_failures_and_preserves_cause(
    s3_storage, failure
):
    s3_storage.client.delete_object.side_effect = failure

    with pytest.raises(FileDeleteError) as caught:
        await s3_storage.storage.delete("photo.png")

    assert caught.value.__cause__ is failure


def test_get_storage_selects_s3_backend(monkeypatch, s3_storage):
    monkeypatch.setattr(settings, "storage_backend", "s3")

    assert isinstance(get_storage(), S3Storage)


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


@pytest.mark.parametrize("backend", ["typo", ""])
def test_unsupported_backend_is_rejected(monkeypatch, backend):
    monkeypatch.setattr(settings, "storage_backend", backend)
    with pytest.raises(StorageBackendNotSupportedError):
        # Current API raises generic Exception; require its specific message.
        get_storage()
