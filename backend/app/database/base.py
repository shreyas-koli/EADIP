"""
SQLAlchemy 2.0 declarative base module.

All ORM models across the application should inherit from ``Base``
so they share a single metadata registry and are discoverable by
Alembic migrations.

Example::

    from app.database.base import Base

    class User(Base):
        __tablename__ = "users"

        id: Mapped[int] = mapped_column(primary_key=True)
        email: Mapped[str] = mapped_column(unique=True, index=True)
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Application-wide declarative base.

    All future models will inherit from this class:

    * ``User``
    * ``Document``
    * ``Agent``
    * ``AuditLog``
    * ... (add models as the platform grows)
    """

    pass
