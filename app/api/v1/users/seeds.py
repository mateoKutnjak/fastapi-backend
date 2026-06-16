from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSession
from app.api.v1.users import constants
from app.api.v1.users.models import Permission, Role


async def _seed_roles(db: AsyncSession):
    roles = constants.ROLE_PERMISSIONS.keys()

    stmt = insert(Role).values([{"name": role} for role in roles])
    stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
    await db.execute(stmt)


async def _seed_permissions(db: AsyncSession):
    permissions = set(
        perm for perms in constants.ROLE_PERMISSIONS.values() for perm in perms
    )

    stmt = insert(Permission).values([{"name": perm} for perm in permissions])
    stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
    await db.execute(stmt)


async def _seed_role_permissions(db: AsyncSession):
    for role_name, role_permissions in constants.ROLE_PERMISSIONS.items():
        result = await db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.name == role_name)
        )
        role = result.scalar_one_or_none()

        if not role:
            print(f"Role '{role_name}' not found, skipping...")
            continue

        existing_permission_names = {p.name for p in role.permissions}

        for permission_name in role_permissions:
            result = await db.execute(
                select(Permission).where(Permission.name == permission_name)
            )
            permission = result.scalar_one_or_none()

            if not permission:
                print(f"Permission '{permission_name}' not found, skipping...")
                continue

            if permission.name not in existing_permission_names:
                role.permissions.append(permission)
                print(f"Permission '{permission_name}' assigned to role '{role_name}'.")


async def seed(db: AsyncSession):

    await _seed_roles(db)
    await _seed_permissions(db)
    await _seed_role_permissions(db)

    await db.commit()
