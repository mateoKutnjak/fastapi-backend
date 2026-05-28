from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.users.model import User

router = APIRouter()


@router.get("/")
async def read_users(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(func.count()).select_from(User))
    user_count = result.scalar_one()

    return {"message": f"Hello from users router! There are {user_count} users."}
