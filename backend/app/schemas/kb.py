"""ExecMind - Pydantic schemas for Knowledge Base."""

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    """Request to create a KB collection."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    sensitivity: str = Field(
        "confidential",
        pattern="^(public|internal|confidential|top_secret)$",
    )


class CollectionUpdate(BaseModel):
    """Request to update a KB collection."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    sensitivity: Optional[str] = Field(
        None,
        pattern="^(public|internal|confidential|top_secret)$",
    )


class CollectionResponse(BaseModel):
    """KB collection response."""
    id: UUID
    name: str
    description: Optional[str] = None
    sensitivity: str
    qdrant_name: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionListResponse(BaseModel):
    """Paginated list of KB collections."""
    collections: list[CollectionResponse]
    total: int


class DocumentUploadMeta(BaseModel):
    """Metadata for document upload (sent in form fields)."""
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=255)
    doc_date: Optional[date] = None


class DocumentResponse(BaseModel):
    """Document response with indexing status."""
    id: UUID
    collection_id: UUID
    original_name: str
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    doc_date: Optional[date] = None
    status: str
    chunk_count: int = 0
    file_size: int
    mime_type: str
    error_message: Optional[str] = None
    uploaded_by: Optional[UUID] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    documents: list[DocumentResponse]
    total: int


class AccessRuleCreate(BaseModel):
    """Request to grant access to a collection."""
    user_id: Optional[UUID] = None
    role: Optional[str] = Field(
        None,
        pattern="^(superadmin|admin|executive|viewer)$",
    )


class AccessRuleResponse(BaseModel):
    """Access rule response."""
    id: UUID
    collection_id: UUID
    user_id: Optional[UUID] = None
    role: Optional[str] = None
    granted_by: Optional[UUID] = None
    granted_at: datetime

    class Config:
        from_attributes = True
