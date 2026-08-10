"""
Authentication API router.

Thin HTTP layer that delegates all business logic to
``app.auth.service``.  Responsible only for request / response
mapping, status codes, and error translation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.auth.jwt import create_access_token
from app.auth.service import authenticate_user, get_current_user, register_user
from app.database.session import DBSession
from app.schemas.user import UserLogin, UserRegister, UserResponse

# ── Router ───────────────────────────────────────────────────────
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# ── OAuth2 scheme (reads the Bearer token from the header) ───────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ── POST /auth/register ─────────────────────────────────────────


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(user_data: UserRegister, db: DBSession):
    """
    Create a new user account.

    - Validates the payload via ``UserRegister``.
    - Delegates to ``register_user()`` in the service layer.
    - Returns **201** with the created user on success.
    - Returns **400** if the e-mail is already taken.
    """
    try:
        user = register_user(db, user_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return user


# ── POST /auth/login ────────────────────────────────────────────


@router.post(
    "/login",
    summary="Obtain an access token",
)
def login(credentials: UserLogin, db: DBSession):
    """
    Authenticate with e-mail and password.

    - Verifies credentials via ``authenticate_user()``.
    - Returns a signed JWT on success.
    - Returns **401** if the credentials are invalid.
    """
    user = authenticate_user(db, credentials.email, credentials.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ── POST /auth/token ─────────────────────────────────────────────


@router.post(
    "/token",
    summary="Obtain an access token (OAuth2 compatible)",
    include_in_schema=False,
)
def login_for_access_token(
    db: DBSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 compatible token login, required for Swagger UI.
    Maps the form's `username` field to the `email` field.
    """
    user = authenticate_user(db, form_data.username, form_data.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ── GET /auth/me ─────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
)
def me(db: DBSession, token: str = Depends(oauth2_scheme)):
    """
    Return the profile of the currently authenticated user.

    - Reads the JWT from the ``Authorization: Bearer …`` header.
    - Resolves the user via ``get_current_user()``.
    - Returns **401** if the token is invalid or the user no longer
      exists.
    """
    user = get_current_user(db, token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
