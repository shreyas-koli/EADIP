"""
Password hashing and verification module.

Uses ``bcrypt`` via **passlib** to produce secure, salted hashes.
All authentication flows should delegate to this module rather
than calling hashing primitives directly.
"""

from passlib.context import CryptContext

# ── Hashing configuration ────────────────────────────────────────
# • schemes        – bcrypt is the primary (and only) algorithm.
# • deprecated     – "auto" will transparently re-hash values that
#                    use a deprecated scheme on next verification.
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Return a bcrypt hash of the given plaintext password.

    Parameters
    ──────────
    password : str
        The user's plaintext password.

    Returns
    ───────
    str
        A salted bcrypt hash string safe for database storage.

    Example::

        hashed = hash_password("s3cur3P@ss!")
        # "$2b$12$..."
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against an existing hash.

    Parameters
    ──────────
    plain_password : str
        The password supplied by the user at login.
    hashed_password : str
        The stored bcrypt hash from the database.

    Returns
    ───────
    bool
        ``True`` if the password matches, ``False`` otherwise.

    Example::

        if verify_password("s3cur3P@ss!", user.hashed_password):
            grant_access(user)
    """
    return _pwd_context.verify(plain_password, hashed_password)
