import asyncio

from app.core.db import AsyncSessionLocal
from app.core.seed import seed_db


async def seed():
    async with AsyncSessionLocal as db:
        await seed_db(db)


if __name__ == "__main__":
    asyncio.run(seed())
