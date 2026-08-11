"""
Pydantic v2 schemas for warehouse connection management.

These schemas govern the data flowing in and out of the warehouse
API endpoints.  Sensitive fields (``password``) are accepted on
create / update but **never** exposed in responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ──────────────────────────────────────────────


class WarehouseCreate(BaseModel):
    """
    Schema for registering a new data-warehouse connection.

    All connection parameters are required; ``description`` is
    optional.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["Production DWH"],
        description="Unique human-readable label for this warehouse.",
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        examples=["Main analytics warehouse on AWS RDS."],
        description="Optional notes about the warehouse.",
    )

    db_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        examples=["PostgreSQL"],
        description="Database engine type (PostgreSQL, MySQL, SQL Server, etc.).",
    )

    host: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["db.example.com"],
        description="Hostname or IP address of the database server.",
    )

    port: int = Field(
        ...,
        gt=0,
        le=65535,
        examples=[5432],
        description="TCP port the database listens on.",
    )

    database_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["analytics"],
        description="Target database / catalog name.",
    )

    username: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["readonly_user"],
        description="Database login username.",
    )

    password: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["s3cur3P@ss!"],
        description="Plaintext password — encrypted before storage.",
    )


class WarehouseUpdate(BaseModel):
    """
    Schema for partially updating an existing warehouse connection.

    Every field is optional; only the supplied fields are modified.
    """

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated warehouse label.",
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Updated description.",
    )

    db_type: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Updated database engine type.",
    )

    host: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated hostname or IP.",
    )

    port: Optional[int] = Field(
        default=None,
        gt=0,
        le=65535,
        description="Updated port number.",
    )

    database_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated database name.",
    )

    username: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated login username.",
    )

    password: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New plaintext password — encrypted before storage.",
    )


# ── Response schemas ─────────────────────────────────────────────


class WarehouseResponse(BaseModel):
    """
    Schema returned for warehouse API responses.

    Excludes ``password`` / ``encrypted_password`` to prevent
    credential leakage.
    """

    id: int = Field(
        ...,
        description="Auto-generated primary key.",
    )

    owner_id: Optional[int] = Field(
        default=None,
        description="ID of the user who owns this warehouse.",
    )

    name: str = Field(
        ...,
        description="Unique warehouse label.",
    )

    description: Optional[str] = Field(
        default=None,
        description="Optional notes about the warehouse.",
    )

    db_type: str = Field(
        ...,
        description="Database engine type.",
    )

    host: str = Field(
        ...,
        description="Hostname or IP address.",
    )

    port: int = Field(
        ...,
        description="TCP port.",
    )

    database_name: str = Field(
        ...,
        description="Target database / catalog name.",
    )

    username: str = Field(
        ...,
        description="Database login username.",
    )

    is_active: bool = Field(
        ...,
        description="Whether the connection is active.",
    )

    created_at: datetime = Field(
        ...,
        description="UTC timestamp of registration.",
    )

    # ── Pydantic v2 ORM compatibility ────────────────────────────
    model_config = ConfigDict(
        from_attributes=True,
    )
