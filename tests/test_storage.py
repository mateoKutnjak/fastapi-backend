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
    FileSaveError,
    StorageBackendNotSupportedError,
    StorageInvalidFilenameError,
    StorageInvalidFilePathError,
    StorageInvalidSubfolderFormatError,
)
from app.core.storage import LocalStorage, S3Storage, get_storage

MAX_FILENAME_BYTES = 255
SUBFOLDER = "avatars"


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
    first = await s3_storage.storage.save(
        "photo with spaces!.png", payload, ".png", subfolder="avatars"
    )
    second = await s3_storage.storage.save(
        "photo with spaces!.png", b"second", ".png", subfolder="avatars"
    )

    assert first != second
    assert first.startswith("avatars/")
    assert Path(first).name.startswith("photo_with_spaces_")
    assert first.endswith(".png")
    s3_storage.client.put_object.assert_any_call(
        Bucket="test-uploads", Key=first, Body=payload
    )
    s3_storage.client.put_object.assert_any_call(
        Bucket="test-uploads", Key=second, Body=b"second"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("subfolder", ["avatars", "users/avatars", "a-b_c/nested2"])
async def test_s3_save_supports_nested_subfolders(s3_storage, subfolder):
    filename = await s3_storage.storage.save(
        "portrait.png", b"image", ".png", subfolder=subfolder
    )

    s3_storage.client.put_object.assert_called_once_with(
        Bucket="test-uploads", Key=filename, Body=b"image"
    )
    assert filename.startswith(f"{subfolder}/")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subfolder",
    [
        "",
        ".",
        "..",
        "/avatars",
        "avatars/",
        "avatars//users",
        "avatars/../private",
        "a\\b",
        "a\x00b",
        "a:b",
    ],
)
async def test_s3_save_rejects_invalid_subfolders_without_request(
    s3_storage, subfolder
):
    with pytest.raises(StorageInvalidSubfolderFormatError):
        await s3_storage.storage.save(
            "photo.png", b"payload", ".png", subfolder=subfolder
        )
    s3_storage.client.put_object.assert_not_called()


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
    with pytest.raises(StorageInvalidFilenameError):
        await s3_storage.storage.save(filename, b"payload", ".png", subfolder="avatars")
    s3_storage.client.put_object.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extension", ["", "png", ".PNG", "../png", ".a/b", ".toolong1234"]
)
async def test_s3_save_rejects_invalid_extensions_without_request(
    s3_storage, extension
):
    with pytest.raises(StorageInvalidFilenameError):
        await s3_storage.storage.save(
            "photo.png", b"payload", extension, subfolder="avatars"
        )
    s3_storage.client.put_object.assert_not_called()


@pytest.mark.asyncio
async def test_s3_delete_uses_bucket_and_exact_key(s3_storage):
    key = "avatars/avatar_123.png"
    await s3_storage.storage.delete(key)

    s3_storage.client.delete_object.assert_called_once_with(
        Bucket="test-uploads", Key=key
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("subfolder", ["avatars", "users/avatars", "a-b_c/nested2"])
async def test_s3_delete_supports_nested_subfolders(s3_storage, subfolder):
    key = f"{subfolder}/avatar_123.png"
    await s3_storage.storage.delete(key)

    s3_storage.client.delete_object.assert_called_once_with(
        Bucket="test-uploads", Key=key
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    [
        "",
        ".",
        "..",
        "../outside",
        "/avatars/file.png",
        "avatars/../file.png",
        "avatars//file.png",
        "a\\b",
    ],
)
async def test_s3_delete_rejects_invalid_keys_without_request(s3_storage, key):
    with pytest.raises(
        (
            StorageInvalidFilenameError,
            StorageInvalidFilePathError,
            StorageInvalidSubfolderFormatError,
        )
    ):
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
        await s3_storage.storage.save(
            "photo.png", b"payload", ".png", subfolder="avatars"
        )

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
        await s3_storage.storage.delete("avatars/photo.png")

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
    first = await storage.save(
        filename, b"arbitrary file bytes", ".pdf", subfolder=SUBFOLDER
    )
    second = await storage.save(filename, b"second", ".pdf", subfolder=SUBFOLDER)
    assert first != second
    assert Path(first).parent.as_posix() == SUBFOLDER
    assert first.endswith(".pdf")
    assert len(first.encode()) < MAX_FILENAME_BYTES
    assert (storage.upload_dir / first).read_bytes() == b"arbitrary file bytes"
    assert (storage.upload_dir / second).read_bytes() == b"second"


@pytest.mark.asyncio
@pytest.mark.parametrize("subfolder", ["avatars", "users/avatars", "a-b_c/nested2"])
async def test_local_save_supports_nested_subfolders(storage, subfolder):
    filename = await storage.save("portrait.png", b"image", ".png", subfolder=subfolder)

    assert (storage.upload_dir / filename).read_bytes() == b"image"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subfolder",
    [
        "",
        ".",
        "..",
        "/avatars",
        "avatars/",
        "avatars//users",
        "avatars/../private",
        "a\\b",
        "a\x00b",
        "a:b",
    ],
)
async def test_local_save_rejects_invalid_subfolders_without_writing(
    storage, subfolder
):
    with pytest.raises(StorageInvalidSubfolderFormatError):
        await storage.save("photo.png", b"payload", ".png", subfolder=subfolder)
    assert list(storage.upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_local_save_translates_subfolder_creation_failure(storage):
    failure = PermissionError("directory creation denied")
    with patch.object(Path, "mkdir", side_effect=failure):
        with pytest.raises(FileSaveError) as caught:
            await storage.save("photo.png", b"payload", ".png", subfolder=SUBFOLDER)

    assert caught.value.__cause__ is failure


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", [None, "", ".", "..", "../x", "/outside/x", "a/b", "a\\b", "C:x", "a\x00b"]
)
async def test_invalid_names_never_touch_disk(storage, name):
    with pytest.raises(StorageInvalidFilenameError):
        await storage.save(name, b"test", ".png", subfolder=SUBFOLDER)
    assert list(storage.upload_dir.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,exception",
    [
        ("", StorageInvalidFilenameError),
        (".", StorageInvalidFilenameError),
        ("..", StorageInvalidFilenameError),
        ("../outside.png", StorageInvalidSubfolderFormatError),
        ("/avatars/file.png", StorageInvalidSubfolderFormatError),
        ("avatars/../file.png", StorageInvalidSubfolderFormatError),
        ("avatars//file.png", StorageInvalidSubfolderFormatError),
        ("avatars/a\\b.png", StorageInvalidFilenameError),
    ],
)
async def test_delete_rejects_invalid_full_keys(storage, key, exception):
    with pytest.raises(exception):
        await storage.delete(key)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extension", ["png", ".", ".PNG", "../png", ".a/b", ".a" * 10, ""]
)
async def test_invalid_extensions(storage, extension):
    with pytest.raises(StorageInvalidFilenameError):
        await storage.save("photo.png", b"test", extension, subfolder=SUBFOLDER)
    assert list(storage.upload_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_delete_is_idempotent_and_preserves_other_files(storage):
    key = await storage.save("file.txt", b"one", ".txt", subfolder=SUBFOLDER)
    other = await storage.save("file.txt", b"two", ".txt", subfolder=SUBFOLDER)
    await storage.delete(key)
    await storage.delete(key)
    assert not (storage.upload_dir / key).exists()
    assert (storage.upload_dir / other).read_bytes() == b"two"


@pytest.mark.asyncio
async def test_local_nested_subfolder_save_and_delete_round_trip(storage):
    subfolder = "users/avatars"
    key = await storage.save("photo.png", b"payload", ".png", subfolder=subfolder)

    await storage.delete(key)

    assert not (storage.upload_dir / key).exists()


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
            await storage.save("photo.png", b"abcdef", ".png", subfolder=SUBFOLDER)
    assert caught.value.__cause__ is failure
    remaining_files = [path for path in storage.upload_dir.rglob("*") if path.is_file()]
    if cleanup_fails:
        assert "partially written" in caplog.text
        assert len(remaining_files) == 1
        assert remaining_files[0].read_bytes() == b"ab"
    else:
        assert remaining_files == []


@pytest.mark.asyncio
async def test_delete_permission_failure(storage):
    failure = PermissionError("denied")
    with patch.object(Path, "unlink", side_effect=failure):
        with pytest.raises(FileDeleteError) as caught:
            await storage.delete(f"{SUBFOLDER}/photo.png")
    assert caught.value.__cause__ is failure


@pytest.mark.asyncio
async def test_missing_upload_directory_is_created(storage):
    storage.upload_dir = storage.upload_dir / "missing"
    key = await storage.save("photo.png", b"test", ".png", subfolder=SUBFOLDER)

    assert (storage.upload_dir / key).read_bytes() == b"test"


@pytest.mark.asyncio
async def test_deleting_symlink_does_not_delete_target(storage, tmp_path):
    target = tmp_path / "target.txt"
    target.write_bytes(b"keep")
    avatar_dir = tmp_path / SUBFOLDER
    avatar_dir.mkdir()
    (avatar_dir / "link.txt").symlink_to(target)
    await storage.delete(f"{SUBFOLDER}/link.txt")
    assert target.read_bytes() == b"keep"


@pytest.mark.parametrize("backend", ["typo", ""])
def test_unsupported_backend_is_rejected(monkeypatch, backend):
    monkeypatch.setattr(settings, "storage_backend", backend)
    with pytest.raises(StorageBackendNotSupportedError):
        # Current API raises generic Exception; require its specific message.
        get_storage()
