"""ExecMind - User management API endpoints."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin, require_superadmin
from app.core.database import get_db_session
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=UserListResponse)
async def list_users(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(active|inactive|locked)$"),
    role: Optional[str] = Query(None, pattern="^(superadmin|admin|executive|viewer)$"),
):
    """List all users with pagination and optional filters (admin+ only)."""
    user_service = UserService(db)
    users, total = await user_service.list_users(
        page=page,
        per_page=per_page,
        status_filter=status,
        role_filter=role,
    )

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Create a new user account (admin+ only)."""
    user_service = UserService(db)
    try:
        user = await user_service.create_user(
            username=body.username,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            role=body.role,
            position=body.position,
            unit=body.unit,
            created_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get user details by ID (admin+ only)."""
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan.",
        )

    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update user details (admin+ only)."""
    user_service = UserService(db)
    try:
        user = await user_service.update_user(
            user_id=user_id,
            updated_by=current_user.id,
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserResponse.model_validate(user)


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: UUID,
    body: UserStatusUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Activate, deactivate, or unlock a user account (admin+ only)."""
    user_service = UserService(db)
    try:
        user = await user_service.update_user_status(
            user_id=user_id,
            new_status=body.status,
            updated_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Delete a user account (superadmin only)."""
    user_service = UserService(db)
    try:
        await user_service.delete_user(
            user_id=user_id,
            deleted_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{user_id}/force-logout", status_code=status.HTTP_204_NO_CONTENT)
async def force_logout_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Force logout a user by revoking all their refresh tokens (superadmin only)."""
    auth_service = AuthService(db)
    revoked_count = await auth_service.force_logout_user(user_id)

    if revoked_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak memiliki sesi aktif.",
        )
