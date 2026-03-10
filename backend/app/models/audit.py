"""ExecMind - SQLAlchemy Audit Log model (append-only)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    String,
    Text,
    text,
)
import sqlalchemy
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """Append-only audit log for tracking all system activities."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sqlalchemy.ForeignKey("users.id", ondelete="SET NULL"),
        index=True
    )
    action: Mapped[str] = mapped_column(
        Enum(
            "login", "logout", "login_failed", "password_change",
            "doc_upload", "doc_delete", "doc_update", "doc_view",
            "collection_create", "collection_delete",
            "user_create", "user_update", "user_deactivate",
            "chat_query", "export_audit_log",
            name="audit_action",
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    resource: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action_metadata: Mapped[dict | None] = mapped_column(JSONB, server_default="'{}'")
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        index=True,
    )
