from app.core.db import AsyncSession
from app.users import seeds as users_seed


async def seed_db(db: AsyncSession):
    await users_seed.seed(db)
