"""ExecMind - Chat session and message service."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.chat import ChatMessage, ChatSession
from app.utils.logging import get_logger

logger = get_logger("chat_service")


class ChatService:
    """Handles chat session and message management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: UUID,
        title: str = "New Chat",
        collection_id: Optional[UUID] = None,
    ) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            user_id=user_id,
            title=title,
            collection_id=collection_id,
        )
        self.db.add(session)
        await self.db.flush()

        logger.info(
            "chat_session_created",
            session_id=str(session.id),
            user_id=str(user_id),
        )
        return session

    async def list_sessions(
        self,
        user_id: UUID,
    ) -> list[ChatSession]:
        """List all chat sessions for a user, ordered by last updated."""
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> Optional[ChatSession]:
        """Get a chat session by ID, ensuring it belongs to the user."""
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete a chat session and all its messages."""
        session = await self.get_session(session_id, user_id)
        if session is None:
            raise ValueError("Sesi chat tidak ditemukan.")

        await self.db.delete(session)
        await self.db.flush()

    async def get_messages(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> list[ChatMessage]:
        """Get messages for a session, ordered by creation time."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_messages(
        self,
        session_id: UUID,
        limit: int = 10,
    ) -> list[ChatMessage]:
        """Get the most recent messages for context window."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Return in chronological order
        return messages

    async def save_user_message(
        self,
        session_id: UUID,
        content: str,
        attachments: list[dict] | None = None,
    ) -> ChatMessage:
        """Save a user message to the session."""
        message = ChatMessage(
            session_id=session_id,
            role="user",
            content=content,
            attachments=attachments or [],
        )
        self.db.add(message)

        # Increment message count
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(
                message_count=ChatSession.message_count + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )

        await self.db.flush()
        return message

    async def save_assistant_message(
        self,
        session_id: UUID,
        content: str,
        sources: list[dict] | None = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
    ) -> ChatMessage:
        """Save an assistant response message with metadata."""
        message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=content,
            sources=sources or [],
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        self.db.add(message)

        # Increment message count
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(
                message_count=ChatSession.message_count + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )

        await self.db.flush()
        return message

    async def update_feedback(
        self,
        message_id: UUID,
        feedback: int,
    ) -> None:
        """Update feedback on a message (1 = thumbs up, -1 = thumbs down)."""
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(feedback=feedback)
        )
        await self.db.flush()

    async def update_session_title(
        self,
        session_id: UUID,
        title: str,
    ) -> None:
        """Update chat session title (auto-generated from first message)."""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(title=title, updated_at=datetime.now(timezone.utc))
        )
        await self.db.flush()
