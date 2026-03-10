"""ExecMind - Pydantic schemas for authentication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request with username and password."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT access and refresh token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Refresh token rotation request."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password change request requiring old password verification."""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserInfo(BaseModel):
    """Minimal user info returned in auth responses."""
    id: UUID
    username: str
    full_name: str
    role: str
    email: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Full login response with tokens and user info."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo
