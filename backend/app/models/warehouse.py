"""
Warehouse ORM model.

Represents a registered external data-warehouse connection
(PostgreSQL, MySQL, SQL Server, etc.) whose metadata and schema
the EADIP platform can inspect and analyse.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Warehouse(Base):
    """
    ``warehouses`` table – stores connection details for external
    data sources.

    Attributes
    ──────────
    id                  Auto-incrementing primary key.
    name                Human-readable label; unique across the platform.
    description         Optional notes about the warehouse.
    db_type             Database engine type (e.g. ``"PostgreSQL"``).
    host                Hostname or IP address of the database server.
    port                TCP port the database listens on.
    database_name       Catalog / schema name to connect to.
    username            Credentials – login name.
    encrypted_password  Credentials – encrypted at rest; never stored
                        in plaintext.
    is_active           Soft-delete / suspension flag.
    created_at          Row creation timestamp (UTC, set by the database).
    updated_at          Last-modified timestamp (UTC, auto-updated).
    """

    __tablename__ = "warehouses"

    # ── Primary key ──────────────────────────────────────────────
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ── Identity ─────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, # Nullable temporarily for migration
    )
    owner: Mapped["User"] = relationship("User", back_populates="warehouses")

    # ── Connection details ───────────────────────────────────────
    db_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Database engine: PostgreSQL, MySQL, SQL Server, etc.",
    )

    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    database_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ── Credentials ──────────────────────────────────────────────
    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    encrypted_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Encrypted at rest – never store plaintext passwords.",
    )

    # ── Status ───────────────────────────────────────────────────
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

    # ── Representation ───────────────────────────────────────────
    def __repr__(self) -> str:
        return (
            f"<Warehouse(id={self.id}, name={self.name!r}, "
            f"db_type={self.db_type!r}, host={self.host!r}, "
            f"is_active={self.is_active})>"
        )
