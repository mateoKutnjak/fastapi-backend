import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete

from app.api.v1.auth.models import RefreshToken
from app.core.db import AsyncSessionLocal


async def cleanup_refresh_tokens() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
        )
        await db.commit()
        print(f"Deleted {result.rowcount} expired refresh token(s)")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(cleanup_refresh_tokens())
