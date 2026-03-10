"""ExecMind - Pydantic schemas for chat."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    """Request to create a new chat session."""
    title: str = Field("New Chat", max_length=500)
    collection_id: Optional[UUID] = None


class ChatSessionResponse(BaseModel):
    """Chat session response with metadata."""
    id: UUID
    user_id: UUID
    collection_id: Optional[UUID] = None
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionListResponse(BaseModel):
    """Paginated list of chat sessions."""
    sessions: list[ChatSessionResponse]
    total: int


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    content: str = Field(..., min_length=1, max_length=2000)


class SourceCitation(BaseModel):
    """Document source citation returned with assistant responses."""
    doc_id: str
    doc_title: str
    page: int = 0
    score: float = 0.0
    text_preview: str = ""


class ChatMessageResponse(BaseModel):
    """Chat message response including source citations."""
    id: UUID
    session_id: UUID
    role: str
    content: str
    sources: list[SourceCitation] = []
    attachments: list[dict] = []
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    feedback: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackRequest(BaseModel):
    """Request to submit feedback on a message (thumbs up/down)."""
    feedback: int = Field(..., ge=-1, le=1)
