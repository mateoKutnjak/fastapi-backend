"""Avatar service and HTTP contracts, plus PostgreSQL concurrency coverage.

Real images and temporary storage are exercised. Most database calls are
mocked; the concurrency test uses the existing PostgreSQL test fixtures.
"""

import asyncio
import uuid
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.auth.dependencies import get_current_user_context
from app.api.v1.users import services
from app.api.v1.users.models import Role, User
from app.api.v1.users.router import router
from app.config import settings
from app.core.db import get_db
from app.core.exceptions.domain_exceptions import (
    AuthenticationFailedError,
    DomainError,
    FileDeleteError,
    FileEmptyError,
    FileSaveError,
    UserNotFoundError,
)
from app.core.exceptions.handlers import (
    database_exception_handler,
    domain_exception_handler,
    validation_exception_handler,
)
from app.core.storage import LocalStorage
from tests.test_images import image_bytes


@pytest.fixture
def avatar_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "local_storage_upload_dir", str(tmp_path))
    monkeypatch.setattr(
        settings, "accepted_image_formats", {"image/jpeg", "image/png", "image/webp"}
    )
    monkeypatch.setattr(settings, "max_user_avatar_bytes", 100_000)
    monkeypatch.setattr(settings, "max_user_avatar_pixels", 1000)
    user = SimpleNamespace(
        id=uuid.uuid4(),
        username="avatar-user",
        email="avatar@example.com",
        role=SimpleNamespace(name="user"),
        avatar_key=None,
    )
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=user),
        commit=AsyncMock(),
        rollback=AsyncMock(),
        delete=AsyncMock(),
    )
    storage = LocalStorage()
    monkeypatch.setattr(services, "get_storage", lambda: storage)
    return SimpleNamespace(user=user, db=db, storage=storage, root=tmp_path)


def upload(data=None, filename="photo.png"):
    return UploadFile(
        file=BytesIO(image_bytes() if data is None else data), filename=filename
    )


@pytest.mark.asyncio
async def test_replacement_keeps_old_until_commit(avatar_env):
    env = avatar_env
    env.user.avatar_key = "old.png"
    (env.root / "old.png").write_bytes(b"old")

    async def commit():
        assert (env.root / "old.png").exists()
        assert (env.root / env.user.avatar_key).exists()

    env.db.commit.side_effect = commit
    result = await services.update_user_avatar(env.db, env.user.id, upload())
    assert result is env.user
    assert not (env.root / "old.png").exists()
    assert (env.root / result.avatar_key).read_bytes() == image_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rollback_fails,cleanup_fails",
    [(False, False), (False, True), (True, False), (True, True)],
)
async def test_commit_failure_preserves_original_and_old_avatar(
    avatar_env, monkeypatch, rollback_fails, cleanup_fails
):
    env = avatar_env
    env.user.avatar_key = "old.png"
    (env.root / "old.png").write_bytes(b"old")
    original = SQLAlchemyError("commit failed")
    env.db.commit.side_effect = original
    if rollback_fails:
        env.db.rollback.side_effect = RuntimeError("rollback failed")
    delete = AsyncMock(wraps=env.storage.delete)
    if cleanup_fails:
        delete.side_effect = FileDeleteError()
    monkeypatch.setattr(env.storage, "delete", delete)
    with pytest.raises(SQLAlchemyError) as caught:
        await services.update_user_avatar(env.db, env.user.id, upload())
    assert caught.value is original
    env.db.rollback.assert_awaited_once()
    delete.assert_awaited_once()
    assert delete.call_args.args[0] != "old.png"
    assert (env.root / "old.png").read_bytes() == b"old"
    if not cleanup_fails:
        assert list(env.root.iterdir()) == [env.root / "old.png"]


@pytest.mark.asyncio
async def test_old_cleanup_failure_does_not_fail_upload(
    avatar_env, monkeypatch, caplog
):
    env = avatar_env
    env.user.avatar_key = "old.png"
    monkeypatch.setattr(env.storage, "delete", AsyncMock(side_effect=FileDeleteError()))
    result = await services.update_user_avatar(env.db, env.user.id, upload())
    assert (env.root / result.avatar_key).exists()
    env.db.rollback.assert_not_awaited()
    assert "previous avatar" in caplog.text


@pytest.mark.asyncio
async def test_save_failure_does_not_change_user(avatar_env, monkeypatch):
    env = avatar_env
    env.user.avatar_key = "old.png"
    monkeypatch.setattr(env.storage, "save", AsyncMock(side_effect=FileSaveError()))
    with pytest.raises(FileSaveError):
        await services.update_user_avatar(env.db, env.user.id, upload())
    assert env.user.avatar_key == "old.png"
    env.db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_user_does_not_read_upload(avatar_env):
    avatar_env.db.scalar.return_value = None
    file = SimpleNamespace(read=AsyncMock())
    with pytest.raises(UserNotFoundError):
        await services.update_user_avatar(avatar_env.db, uuid.uuid4(), file)
    file.read.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_is_bounded(avatar_env):
    file = SimpleNamespace(filename="photo.png", read=AsyncMock(return_value=b""))
    with pytest.raises(FileEmptyError):
        await services.update_user_avatar(avatar_env.db, avatar_env.user.id, file)
    file.read.assert_awaited_once_with(settings.max_user_avatar_bytes + 1)
    avatar_env.db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "commit_fails,cleanup_fails", [(False, False), (True, False), (False, True)]
)
async def test_user_deletion_cleanup(
    avatar_env, monkeypatch, commit_fails, cleanup_fails
):
    env = avatar_env
    env.user.avatar_key = "old.png"
    (env.root / "old.png").write_bytes(b"old")
    delete = AsyncMock(wraps=env.storage.delete)
    if cleanup_fails:
        delete.side_effect = FileDeleteError()
    monkeypatch.setattr(env.storage, "delete", delete)
    if commit_fails:
        env.db.commit.side_effect = SQLAlchemyError("commit failed")
        with pytest.raises(SQLAlchemyError):
            await services.delete_user_by_id(env.db, env.user.id)
        delete.assert_not_awaited()
    else:
        await services.delete_user_by_id(env.db, env.user.id)
        delete.assert_awaited_once_with("old.png")
    assert (env.root / "old.png").exists() == (commit_fails or cleanup_fails)


@pytest.fixture
def avatar_app(avatar_env):
    app = FastAPI()
    app.include_router(router, prefix="/users")
    app.mount("/uploads", StaticFiles(directory=str(avatar_env.root)))
    app.add_exception_handler(DomainError, domain_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    async def session():
        yield avatar_env.db

    async def current_user():
        return SimpleNamespace(user=avatar_env.user)

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user_context] = current_user
    return app


@pytest.mark.asyncio
async def test_delete_avatar_http_clears_key_and_removes_file(avatar_env, avatar_app):
    env = avatar_env
    env.user.avatar_key = "avatar.png"
    (env.root / env.user.avatar_key).write_bytes(b"avatar")

    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.delete("/users/me/avatar")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["avatar_key"] is None
    assert env.user.avatar_key is None
    assert not (env.root / "avatar.png").exists()
    env.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_avatar_http_without_avatar_is_harmless(
    avatar_env, avatar_app, monkeypatch
):
    monkeypatch.setattr(
        services,
        "get_storage",
        lambda: pytest.fail("storage should not be initialized"),
    )

    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.delete("/users/me/avatar")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["avatar_key"] is None
    assert avatar_env.user.avatar_key is None
    avatar_env.db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
async def test_upload_http_normalizes_extension_and_serves_bytes(
    avatar_env, avatar_app, fmt
):
    data = image_bytes(fmt)
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/users/me/avatar",
            files={"file": ("photo.abc", data, "application/octet-stream")},
        )
        assert response.status_code == status.HTTP_200_OK
        key = response.json()["avatar_key"]
        assert key == avatar_env.user.avatar_key
        assert key.endswith("." + fmt.lower())
        downloaded = await client.get("/uploads/" + key)
        assert downloaded.status_code == status.HTTP_200_OK
        assert downloaded.content == data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected_code,expected_status",
    [(b"", "empty_file", 400), (b"text", "unsupported_image_format", 415)],
)
async def test_http_invalid_upload_has_no_side_effects(
    avatar_env, avatar_app, payload, expected_code, expected_status
):
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/users/me/avatar", files={"file": ("photo.png", payload, "image/png")}
        )
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    avatar_env.db.commit.assert_not_awaited()
    assert list(avatar_env.root.iterdir()) == []


@pytest.mark.asyncio
async def test_http_missing_file(avatar_app):
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put("/users/me/avatar")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_http_unauthenticated(avatar_env, avatar_app):
    async def deny():
        raise AuthenticationFailedError()

    avatar_app.dependency_overrides[get_current_user_context] = deny
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/users/me/avatar",
            files={"file": ("photo.png", image_bytes(), "image/png")},
        )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    avatar_env.db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,code",
    [
        (FileSaveError(), "file_save_error"),
        (SQLAlchemyError("commit failed"), "database_error"),
    ],
)
async def test_http_server_errors(avatar_env, avatar_app, monkeypatch, failure, code):
    if isinstance(failure, FileSaveError):
        monkeypatch.setattr(avatar_env.storage, "save", AsyncMock(side_effect=failure))
    else:
        avatar_env.db.commit.side_effect = failure
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/users/me/avatar",
            files={"file": ("photo.png", image_bytes(), "image/png")},
        )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["error"]["code"] == code
    assert list(avatar_env.root.iterdir()) == []


@pytest.mark.asyncio
async def test_concurrent_replacements_leave_no_orphans(  # noqa: PLR0915
    avatar_env, monkeypatch, test_engine, setup_database
):
    """Use real row locks and verify a preloaded user is refreshed after waiting."""

    env = avatar_env
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    first_saved = asyncio.Event()
    release_first = asyncio.Event()
    keys = []
    tasks = []
    real_save = env.storage.save
    (env.root / "old.png").write_bytes(b"old")

    async def save(*args, **kwargs):
        key = await real_save(*args, **kwargs)
        keys.append(key)
        if not first_saved.is_set():
            first_saved.set()
            await asyncio.wait_for(release_first.wait(), timeout=10)
        return key

    monkeypatch.setattr(env.storage, "save", save)
    try:
        async with factory() as seed:
            role_id = await seed.scalar(select(Role.id).where(Role.name == "user"))
            assert role_id is not None
            seed.add(
                User(
                    id=user_id,
                    email=f"avatar-concurrency-{user_id.hex}@example.com",
                    role_id=role_id,
                    avatar_key="old.png",
                )
            )
            await seed.commit()

        async with factory() as first, factory() as second:
            # Model authentication preloading the user before the avatar service.
            stale_user = await second.get(User, user_id)
            assert stale_user.avatar_key == "old.png"
            first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
            second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
            assert first_pid != second_pid
            tasks.append(
                asyncio.create_task(
                    services.update_user_avatar(first, user_id, upload())
                )
            )
            try:
                await asyncio.wait_for(first_saved.wait(), timeout=5)
                tasks.append(
                    asyncio.create_task(
                        services.update_user_avatar(second, user_id, upload())
                    )
                )
                # Observe an actual PostgreSQL lock wait, rather than assuming
                # scheduling order or requiring both requests to reach save().
                async with test_engine.connect() as observer:
                    async with asyncio.timeout(5):
                        while True:
                            blockers = await observer.scalar(
                                text("SELECT pg_blocking_pids(:pid)"),
                                {"pid": second_pid},
                            )
                            if first_pid in blockers:
                                break
                            if tasks[1].done():
                                tasks[1].result()
                                pytest.fail("Second replacement bypassed the row lock")
                            await asyncio.sleep(0.01)
                assert len(keys) == 1
                release_first.set()
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
            finally:
                release_first.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        async with factory() as verify:
            current = await verify.get(User, user_id)
            assert current.avatar_key == keys[-1]
            assert set(path.name for path in env.root.iterdir()) == {current.avatar_key}
            assert (env.root / current.avatar_key).read_bytes() == image_bytes()
        assert len(keys) == len(tasks)
        assert keys[0] != keys[1]
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit_type", ["bytes", "pixels"])
async def test_http_limits_preserve_existing_avatar(
    avatar_env, avatar_app, monkeypatch, limit_type
):
    env = avatar_env
    env.user.avatar_key = "old.png"
    (env.root / "old.png").write_bytes(b"old")
    field = (
        "max_user_avatar_bytes" if limit_type == "bytes" else "max_user_avatar_pixels"
    )
    monkeypatch.setattr(settings, field, 1)
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/users/me/avatar",
            files={"file": ("photo.png", image_bytes(), "image/png")},
        )
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["error"]["code"] == "file_size_exceeded"
    assert env.user.avatar_key == "old.png"
    assert list(env.root.iterdir()) == [env.root / "old.png"]
    env.db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_invalid_filename(avatar_env, avatar_app):
    async with AsyncClient(
        transport=ASGITransport(app=avatar_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/users/me/avatar",
            files={"file": ("../photo.png", image_bytes(), "image/png")},
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "file_invalid_filename"
    assert list(avatar_env.root.iterdir()) == []


@pytest.mark.asyncio
async def test_delete_user_without_avatar_does_not_initialize_storage(
    avatar_env, monkeypatch
):
    factory = AsyncMock()
    monkeypatch.setattr(services, "get_storage", factory)
    await services.delete_user_by_id(avatar_env.db, avatar_env.user.id)
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_database_read_failure_does_not_read_upload(avatar_env):
    avatar_env.db.scalar.side_effect = SQLAlchemyError("read failed")
    file = SimpleNamespace(read=AsyncMock())
    with pytest.raises(SQLAlchemyError):
        await services.update_user_avatar(avatar_env.db, avatar_env.user.id, file)
    file.read.assert_not_awaited()
