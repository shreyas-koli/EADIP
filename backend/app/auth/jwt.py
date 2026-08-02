"""
JWT access-token utilities.

Provides helpers to **create** and **decode** JSON Web Tokens used for
stateless authentication across the EADIP platform.  All cryptographic
parameters (secret, algorithm, TTL) are read from the central
application settings so they stay consistent and easy to rotate.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Mint a signed JWT containing the supplied claims.

    Parameters
    ──────────
    data : dict
        Arbitrary claims to embed in the token (e.g. ``{"sub": user.email}``).
        A shallow copy is made so the caller's dict is never mutated.
    expires_delta : timedelta | None
        Custom token lifetime.  Falls back to
        ``settings.ACCESS_TOKEN_EXPIRE_MINUTES`` when omitted.

    Returns
    ───────
    str
        An encoded JWT string ready for the ``Authorization: Bearer …``
        header.

    Example::

        token = create_access_token({"sub": "user@example.com"})
    """
    to_encode: dict = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    """
    Decode and validate a JWT, returning its payload.

    Parameters
    ──────────
    token : str
        The raw JWT string (without the ``Bearer `` prefix).

    Returns
    ───────
    dict | None
        The decoded claims on success, or ``None`` if the token is
        malformed, expired, or otherwise invalid.

    Notes
    ─────
    * **Expired tokens** raise ``ExpiredSignatureError`` internally,
      which is caught and converted to ``None``.
    * **Tampered / invalid tokens** raise ``JWTError``, also caught.
    * Callers should treat a ``None`` return as an authentication
      failure and respond with HTTP 401.

    Example::

        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_email = payload.get("sub")
    """
    try:
        payload: dict = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None
