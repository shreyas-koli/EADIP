"""
User ORM model.

Represents an application user with authentication credentials,
role-based access control, and audit timestamps.
"""

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class User(Base):
    """
    ``users`` table – stores identity and authentication data.

    Attributes
    ──────────
    id              Auto-incrementing primary key.
    full_name       Display name of the user.
    email           Unique login identifier; indexed for fast lookups.
    hashed_password Bcrypt / Argon2 hash – never store plaintext.
    role            Coarse-grained RBAC role (``"user"`` | ``"admin"`` | …).
    is_active       Soft-delete / suspension flag.
    created_at      Row creation timestamp (UTC, set by the database).
    updated_at      Last-modified timestamp (UTC, auto-updated on change).
    """

    __tablename__ = "users"

    # ── Primary key ──────────────────────────────────────────────
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ── Identity ─────────────────────────────────────────────────
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    # ── Authentication ───────────────────────────────────────────
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ── Authorisation ────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(20),
        default="user",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ── Audit timestamps ─────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    warehouses: Mapped[List["Warehouse"]] = relationship("Warehouse", back_populates="owner")

    # ── Representation ───────────────────────────────────────────
    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, email={self.email!r}, "
            f"role={self.role!r}, is_active={self.is_active})>"
        )
