"""Roles and the user-role association table."""

from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Table, Uuid, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoleName(StrEnum):
    DOCUMENTATION_EXECUTIVE = "DOCUMENTATION_EXECUTIVE"
    DOCUMENTATION_MANAGER = "DOCUMENTATION_MANAGER"


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_user_roles_role_id", "role_id"),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    users: Mapped[list["User"]] = relationship(
        secondary=user_roles, back_populates="roles"
    )
