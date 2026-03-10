"""ExecMind - Pydantic schemas for user management."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Request to create a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    position: Optional[str] = Field(None, max_length=255)
    unit: Optional[str] = Field(None, max_length=255)
    role: str = Field("executive", pattern="^(superadmin|admin|executive|viewer)$")


class UserUpdate(BaseModel):
    """Request to update user details."""
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    position: Optional[str] = Field(None, max_length=255)
    unit: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, pattern="^(superadmin|admin|executive|viewer)$")


class UserStatusUpdate(BaseModel):
    """Request to change user status (activate, deactivate, unlock)."""
    status: str = Field(..., pattern="^(active|inactive|locked)$")


class UserResponse(BaseModel):
    """Full user response with all fields."""
    id: UUID
    username: str
    email: str
    full_name: str
    position: Optional[str] = None
    unit: Optional[str] = None
    role: str
    status: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated list of users."""
    users: list[UserResponse]
    total: int
    page: int
    per_page: int
