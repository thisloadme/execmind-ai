"""ExecMind - User management service."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.models.audit import AuditLog
from app.utils.logging import get_logger

logger = get_logger("user_service")


class UserService:
    """Handles user CRUD operations and permission management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str,
        role: str = "executive",
        position: Optional[str] = None,
        unit: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> User:
        """Create a new user account.

        Args:
            username: Unique username.
            email: Unique email address.
            password: Plaintext password (will be hashed).
            full_name: User's full name.
            role: User role (superadmin, admin, executive, viewer).
            position: Job position/title.
            unit: Organization unit.
            created_by: ID of the user creating this account.

        Returns:
            Created User object.

        Raises:
            ValueError: If username or email already exists.
        """
        # Check if username or email already exists
        existing = await self.db.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Username atau email sudah terdaftar.")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            position=position,
            unit=unit,
        )
        self.db.add(user)
        await self.db.flush()

        # Audit log
        audit = AuditLog(
            user_id=created_by,
            action="user_create",
            resource="user",
            resource_id=user.id,
            action_metadata={"username": username, "role": role},
        )
        self.db.add(audit)

        logger.info("user_created", user_id=str(user.id), username=username, role=role)
        return user

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get a user by their UUID.

        Args:
            user_id: User UUID.

        Returns:
            User object or None if not found.
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
        role_filter: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """List users with pagination and optional filters.

        Args:
            page: Page number (1-indexed).
            per_page: Items per page.
            status_filter: Filter by user status.
            role_filter: Filter by user role.

        Returns:
            Tuple of (list of users, total count).
        """
        query = select(User)
        count_query = select(func.count(User.id))

        if status_filter:
            query = query.where(User.status == status_filter)
            count_query = count_query.where(User.status == status_filter)
        if role_filter:
            query = query.where(User.role == role_filter)
            count_query = count_query.where(User.role == role_filter)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        offset = (page - 1) * per_page
        query = query.order_by(User.created_at.desc()).offset(offset).limit(per_page)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def update_user(
        self,
        user_id: UUID,
        updated_by: UUID,
        **update_data,
    ) -> User:
        """Update user details.

        Args:
            user_id: User UUID to update.
            updated_by: ID of the user performing the update.
            **update_data: Fields to update.

        Returns:
            Updated User object.

        Raises:
            ValueError: If user not found.
        """
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise ValueError("User tidak ditemukan.")

        for key, value in update_data.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)

        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Audit log
        audit = AuditLog(
            user_id=updated_by,
            action="user_update",
            resource="user",
            resource_id=user_id,
            action_metadata={"updated_fields": list(update_data.keys())},
        )
        self.db.add(audit)

        return user

    async def update_user_status(
        self,
        user_id: UUID,
        new_status: str,
        updated_by: UUID,
    ) -> User:
        """Change user status (activate, deactivate, unlock).

        Args:
            user_id: User UUID.
            new_status: New status value.
            updated_by: ID of the admin performing the action.

        Returns:
            Updated User object.

        Raises:
            ValueError: If user not found.
        """
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise ValueError("User tidak ditemukan.")

        old_status = user.status
        user.status = new_status
        user.updated_at = datetime.now(timezone.utc)

        # Reset lockout fields if unlocking
        if new_status == "active" and old_status == "locked":
            user.failed_attempts = 0
            user.locked_until = None

        await self.db.flush()

        action = "user_deactivate" if new_status == "inactive" else "user_update"
        audit = AuditLog(
            user_id=updated_by,
            action=action,
            resource="user",
            resource_id=user_id,
            action_metadata={"old_status": old_status, "new_status": new_status},
        )
        self.db.add(audit)

        return user

    async def delete_user(self, user_id: UUID, deleted_by: UUID) -> None:
        """Delete a user account (superadmin only).

        Args:
            user_id: User UUID to delete.
            deleted_by: ID of the superadmin performing deletion.

        Raises:
            ValueError: If user not found or trying to delete self.
        """
        if user_id == deleted_by:
            raise ValueError("Tidak dapat menghapus akun sendiri.")

        user = await self.get_user_by_id(user_id)
        if user is None:
            raise ValueError("User tidak ditemukan.")

        audit = AuditLog(
            user_id=deleted_by,
            action="user_deactivate",
            resource="user",
            resource_id=user_id,
            action_metadata={"username": user.username, "action": "deleted"},
        )
        self.db.add(audit)

        await self.db.delete(user)
        await self.db.flush()
