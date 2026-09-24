import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete, or_

from app.api.v1.auth.models import Session
from app.core.db import AsyncSessionLocal


async def cleanup_refresh_tokens() -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Session).where(
                or_(
                    Session.expires_at <= now,
                    Session.absolute_expires_at <= now,
                    Session.revoked_at.is_not(None),
                )
            )
        )
        await db.commit()
        print(f"Deleted {result.rowcount} expired or revoked session(s)")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(cleanup_refresh_tokens())
