from app.api.v1.users import seeds as users_seed
from app.core.db import AsyncSession


async def seed_db(db: AsyncSession):
    await users_seed.seed(db)
