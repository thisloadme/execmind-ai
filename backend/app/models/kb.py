"""ExecMind - SQLAlchemy Knowledge Base models."""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
import sqlalchemy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KBCollection(Base):
    """Knowledge Base collection for grouping related documents."""

    __tablename__ = "kb_collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sensitivity: Mapped[str] = mapped_column(
        Enum(
            "public", "internal", "confidential", "top_secret",
            name="kb_sensitivity",
            create_type=False,
        ),
        nullable=False,
        server_default="confidential",
        index=True,
    )
    qdrant_name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sqlalchemy.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Relationships
    documents = relationship("Document", back_populates="collection")
    access_rules = relationship("CollectionAccess", back_populates="collection", cascade="all, delete-orphan")


class CollectionAccess(Base):
    """Access control rule for a KB collection (user-specific or role-based)."""

    __tablename__ = "collection_access"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sqlalchemy.ForeignKey("kb_collections.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sqlalchemy.ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str | None] = mapped_column(
        Enum(
            "superadmin", "admin", "executive", "viewer",
            name="user_role",
            create_type=False,
        ),
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Relationships
    collection = relationship("KBCollection", back_populates="access_rules")


class Document(Base):
    """Document record stored within a KB collection."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sqlalchemy.ForeignKey("kb_collections.id", ondelete="CASCADE"),
        nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(255))
    doc_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        Enum(
            "uploading", "processing", "indexed", "failed", "deleted",
            name="doc_status",
            create_type=False,
        ),
        nullable=False,
        server_default="uploading",
        index=True,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sqlalchemy.ForeignKey("users.id", ondelete="SET NULL")
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Relationships
    collection = relationship("KBCollection", back_populates="documents")
