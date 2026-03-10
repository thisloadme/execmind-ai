"""ExecMind - API dependencies for JWT validation and user injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import decode_token
from app.models.user import User


security_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Validate JWT access token and return the authenticated user.

    Args:
        credentials: Bearer token from Authorization header.
        db: Database session.

    Returns:
        Authenticated User object.

    Raises:
        HTTPException 401: If token is invalid or user not found.
        HTTPException 403: If user account is inactive or locked.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah kadaluarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun tidak aktif. Hubungi administrator.",
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun terkunci sementara. Coba lagi nanti.",
        )

    return user


def require_role(*allowed_roles: str):
    """Create a dependency that checks user role authorization.

    Args:
        allowed_roles: Tuple of role strings that are allowed access.

    Returns:
        FastAPI dependency function.
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki izin untuk mengakses sumber daya ini.",
            )
        return current_user

    return role_checker


# Convenience dependencies for common role checks
require_superadmin = require_role("superadmin")
require_admin = require_role("superadmin", "admin")
require_executive = require_role("superadmin", "admin", "executive")
require_any_authenticated = require_role("superadmin", "admin", "executive", "viewer")
