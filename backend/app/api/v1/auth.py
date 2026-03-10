"""ExecMind - Authentication API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db_session
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UserInfo,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Authenticate user and return JWT access + refresh tokens."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    auth_service = AuthService(db)
    try:
        result = await auth_service.authenticate_user(
            username=body.username,
            password=body.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    user = result["user"]
    return LoginResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        user=UserInfo(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            email=user.email,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Rotate refresh token and issue new access + refresh token pair."""
    auth_service = AuthService(db)
    try:
        result = await auth_service.refresh_tokens(body.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Revoke refresh token to log out the user."""
    auth_service = AuthService(db)
    await auth_service.logout(body.refresh_token)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Change the current user's password with old password verification."""
    auth_service = AuthService(db)
    try:
        await auth_service.change_password(
            user=current_user,
            old_password=body.old_password,
            new_password=body.new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get the currently authenticated user's information."""
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        email=current_user.email,
    )
