from typing import Annotated

from pydantic import StringConstraints

from app.config import settings

Password = Annotated[
    str,
    StringConstraints(
        min_length=settings.password_min_length,
        max_length=settings.password_max_length,
    ),
]
