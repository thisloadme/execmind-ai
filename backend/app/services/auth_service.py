"""ExecMind - Authentication service with login, token rotation, and brute force protection."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.models.audit import AuditLog
from app.utils.logging import get_logger

logger = get_logger("auth_service")


class AuthService:
    """Handles authentication logic including login, token rotation, and account lockout."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Authenticate user with username and password.

        Implements brute force protection with account lockout after
        MAX_LOGIN_ATTEMPTS consecutive failures.

        Args:
            username: Login username.
            password: Plaintext password.
            ip_address: Client IP for audit logging.
            user_agent: Client user agent for audit logging.

        Returns:
            Dict with access_token, refresh_token, expires_in, and user info.

        Raises:
            ValueError: If credentials are invalid or account is locked.
        """
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if user is None:
            await self._log_audit("login_failed", ip_address, user_agent, action_metadata={"username": username})
            raise ValueError("Username atau password salah.")

        # Check if account is locked
        if user.is_locked:
            remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
            raise ValueError(
                f"Akun terkunci. Coba lagi dalam {remaining} menit."
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            await self._handle_failed_login(user, ip_address, user_agent)
            raise ValueError("Username atau password salah.")

        # Successful login - reset failed attempts
        user.failed_attempts = 0
        user.locked_until = None
        user.status = "active"
        user.last_login_at = datetime.now(timezone.utc)
        user.last_login_ip = ip_address

        # Generate tokens
        user_id_str = str(user.id)
        access_token = create_access_token(user_id_str, user.username, user.role)
        refresh_token = create_refresh_token(user_id_str)

        # Store refresh token hash
        await self._store_refresh_token(refresh_token, user.id)

        # Audit log
        await self._log_audit(
            "login",
            ip_address,
            user_agent,
            user_id=user.id,
            action_metadata={"username": user.username},
        )

        await self.db.flush()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user,
        }

    async def refresh_tokens(self, refresh_token_str: str) -> dict:
        """Rotate refresh token — revoke old, issue new pair.

        Args:
            refresh_token_str: Current refresh token string.

        Returns:
            Dict with new access_token, refresh_token, and expires_in.

        Raises:
            ValueError: If refresh token is invalid, expired, or revoked.
        """
        try:
            payload = decode_token(refresh_token_str)
        except Exception:
            raise ValueError("Refresh token tidak valid.")

        if payload.get("type") != "refresh":
            raise ValueError("Token bukan refresh token.")

        token_hash_value = hash_token(refresh_token_str)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
        )
        db_token = result.scalar_one_or_none()

        if db_token is None:
            raise ValueError("Refresh token tidak ditemukan.")

        if db_token.revoked:
            raise ValueError("Refresh token sudah dicabut.")

        if db_token.expires_at < datetime.now(timezone.utc):
            raise ValueError("Refresh token sudah kadaluarsa.")

        # Revoke old token
        db_token.revoked = True
        db_token.revoked_at = datetime.now(timezone.utc)

        # Get user
        user_id = UUID(payload["sub"])
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise ValueError("User tidak ditemukan atau tidak aktif.")

        # Create new token pair
        user_id_str = str(user.id)
        new_access = create_access_token(user_id_str, user.username, user.role)
        new_refresh = create_refresh_token(user_id_str)

        await self._store_refresh_token(new_refresh, user.id)
        await self.db.flush()

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def logout(self, refresh_token_str: str) -> None:
        """Revoke a refresh token on logout.

        Args:
            refresh_token_str: Refresh token to revoke.
        """
        token_hash_value = hash_token(refresh_token_str)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
        )
        db_token = result.scalar_one_or_none()

        if db_token and not db_token.revoked:
            db_token.revoked = True
            db_token.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
    ) -> None:
        """Change user password with old password verification.

        Args:
            user: Current authenticated user.
            old_password: Current password for verification.
            new_password: New password to set.

        Raises:
            ValueError: If old password is incorrect.
        """
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Password lama salah.")

        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def force_logout_user(self, user_id: UUID) -> int:
        """Revoke all active refresh tokens for a user (superadmin action).

        Args:
            user_id: User ID to force logout.

        Returns:
            Number of tokens revoked.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
            )
            .values(revoked=True, revoked_at=now)
        )
        await self.db.flush()
        return result.rowcount

    async def _handle_failed_login(
        self,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Increment failed login counter and lock account if threshold reached."""
        user.failed_attempts = (user.failed_attempts or 0) + 1

        if user.failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.status = "locked"
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES
            )
            logger.warning(
                "account_locked",
                user_id=str(user.id),
                username=user.username,
                failed_attempts=user.failed_attempts,
            )

        await self._log_audit(
            "login_failed",
            ip_address,
            user_agent,
            user_id=user.id,
            action_metadata={
                "username": user.username,
                "failed_attempts": user.failed_attempts,
            },
        )
        await self.db.flush()

    async def _store_refresh_token(self, token: str, user_id: UUID) -> None:
        """Store the hash of a refresh token in the database."""
        token_hash_value = hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        db_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash_value,
            expires_at=expires_at,
        )
        self.db.add(db_token)

    async def _log_audit(
        self,
        action: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        user_id: UUID | None = None,
        action_metadata: dict | None = None,
    ) -> None:
        """Create an audit log entry."""
        audit = AuditLog(
            user_id=user_id,
            action=action,
            resource="auth",
            ip_address=ip_address,
            user_agent=user_agent,
            action_metadata=action_metadata or {},
        )
        self.db.add(audit)
