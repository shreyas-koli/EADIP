"""
Pydantic v2 schemas for user authentication and serialisation.

These schemas form the data-transfer layer between the API boundary
and the service / persistence layers.  They validate incoming payloads
and shape outgoing responses so internal model details never leak.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ── Request schemas ──────────────────────────────────────────────


class UserRegister(BaseModel):
    """
    Schema for new-user registration requests.

    Validates that the caller provides a display name, a valid
    e-mail address, and a password that meets the minimum length
    requirement.
    """

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["Shreyas Koli"],
        description="Display name of the user.",
    )

    email: EmailStr = Field(
        ...,
        examples=["shreyas@example.com"],
        description="Unique e-mail address used for login.",
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        examples=["s3cur3P@ss!"],
        # description="Plaintext password (min 8 characters).",
        description="Password must contain at least 8 characters.",
    )

    @field_validator("password")
    @classmethod
    def validate_password_byte_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 bytes due to bcrypt limitations.")
        return v


class UserLogin(BaseModel):
    """
    Schema for login / token-issuance requests.

    Only the credentials are required — no profile fields.
    """

    email: EmailStr = Field(
        ...,
        examples=["shreyas@example.com"],
        description="Registered e-mail address.",
    )

    password: str = Field(
        ...,
        examples=["s3cur3P@ss!"],
        description="Plaintext password to verify.",
    )


# ── Response schemas ─────────────────────────────────────────────


class UserResponse(BaseModel):
    """
    Schema returned for user-facing API responses.

    Excludes sensitive fields (``hashed_password``, ``updated_at``)
    and enables ORM mode so SQLAlchemy model instances can be
    serialised directly.
    """

    id: int = Field(
        ...,
        description="Auto-generated primary key.",
    )

    full_name: str = Field(
        ...,
        description="Display name of the user.",
    )

    email: EmailStr = Field(
        ...,
        description="Unique e-mail address.",
    )

    role: str = Field(
        ...,
        description="Authorisation role (e.g. 'user', 'admin').",
    )

    is_active: bool = Field(
        ...,
        description="Whether the account is active.",
    )

    created_at: datetime = Field(
        ...,
        description="UTC timestamp of account creation.",
    )

    # ── Pydantic v2 ORM compatibility ────────────────────────────
    model_config = ConfigDict(
        from_attributes=True,
    )
