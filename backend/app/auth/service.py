"""
Authentication service layer.

Contains pure business logic for user registration, credential
verification, and token-based identity resolution.  This module is
**route-agnostic** — it receives a database session and returns
domain objects, leaving HTTP concerns to the API layer.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRegister


# ── Query helpers ────────────────────────────────────────────────


def get_user_by_email(db: Session, email: str) -> User | None:
    """
    Look up a user by their e-mail address.

    Parameters
    ──────────
    db    : Active SQLAlchemy session.
    email : The e-mail to search for (case-sensitive).

    Returns
    ───────
    User | None
        The matching ``User`` row, or ``None`` if no account exists
        with the given address.
    """
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalars().first()


# ── Registration ─────────────────────────────────────────────────


def register_user(db: Session, user_data: UserRegister) -> User:
    """
    Create a new user account.

    Workflow
    ────────
    1. Check that the e-mail is not already taken.
    2. Hash the plaintext password.
    3. Persist the new ``User`` row.
    4. Return the created user (with database-generated fields).

    Parameters
    ──────────
    db        : Active SQLAlchemy session.
    user_data : Validated registration payload.

    Returns
    ───────
    User
        The newly created user instance.

    Raises
    ──────
    ValueError
        If a user with the same e-mail already exists.
    """
    existing = get_user_by_email(db, user_data.email)
    if existing is not None:
        raise ValueError(f"Email '{user_data.email}' is already registered.")

    if len(user_data.password.encode("utf-8")) > 72:
        raise ValueError("Password cannot exceed 72 bytes due to bcrypt limitations.")

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ── Authentication ───────────────────────────────────────────────


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """
    Verify a user's credentials.

    Parameters
    ──────────
    db       : Active SQLAlchemy session.
    email    : The e-mail supplied at login.
    password : The plaintext password to check.

    Returns
    ───────
    User | None
        The authenticated ``User`` if the credentials are valid,
        or ``None`` if the e-mail is unknown **or** the password
        does not match.

    Security note
    ─────────────
    Returning ``None`` for *both* failure modes prevents
    user-enumeration attacks.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


# ── Token-based identity resolution ─────────────────────────────


def get_current_user(db: Session, token: str) -> User | None:
    """
    Resolve the currently authenticated user from a JWT.

    Parameters
    ──────────
    db    : Active SQLAlchemy session.
    token : The raw JWT string (without the ``Bearer `` prefix).

    Returns
    ───────
    User | None
        The user identified by the token's ``sub`` claim, or
        ``None`` if the token is invalid / expired or the
        referenced user no longer exists.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None

    email: str | None = payload.get("sub")
    if email is None:
        return None

    return get_user_by_email(db, email)
