import uuid

from sqlalchemy import UUID, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.v1.users.models import User
from app.core.db import Base
from app.core.mixins import TimestampMixin


class PushNotificationToken(Base, TimestampMixin):
    __tablename__ = "push_notification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    token: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
    )
    fid: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    user: Mapped[User | None] = relationship(
        "User",
        lazy="selectin",
    )
