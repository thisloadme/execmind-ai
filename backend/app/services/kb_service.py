"""ExecMind - Knowledge Base management service."""

import re
import uuid as uuid_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.kb import CollectionAccess, Document, KBCollection
from app.utils.logging import get_logger

logger = get_logger("kb_service")


class KBService:
    """Handles Knowledge Base collection and document management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Collection Methods ─────────────────────────────

    async def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
        sensitivity: str = "confidential",
        created_by: Optional[UUID] = None,
    ) -> KBCollection:
        """Create a new KB collection with auto-generated Qdrant name.

        Args:
            name: Display name for the collection.
            description: Optional description.
            sensitivity: Data sensitivity level.
            created_by: ID of the creating user.

        Returns:
            Created KBCollection object.
        """
        # Generate safe Qdrant collection name
        safe_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        qdrant_name = f"kb_{safe_name}_{uuid_module.uuid4().hex[:8]}"

        collection = KBCollection(
            name=name,
            description=description,
            sensitivity=sensitivity,
            qdrant_name=qdrant_name,
            created_by=created_by,
        )
        self.db.add(collection)
        await self.db.flush()

        # Audit log
        audit = AuditLog(
            user_id=created_by,
            action="collection_create",
            resource="collection",
            resource_id=collection.id,
            action_metadata={"name": name, "sensitivity": sensitivity},
        )
        self.db.add(audit)

        logger.info(
            "collection_created",
            collection_id=str(collection.id),
            name=name,
            qdrant_name=qdrant_name,
        )
        return collection

    async def list_collections(
        self,
        user_id: Optional[UUID] = None,
        user_role: Optional[str] = None,
    ) -> list[dict]:
        """List collections accessible to a user, including document count.

        Args:
            user_id: Requesting user ID for access filtering.
            user_role: User role for role-based access.

        Returns:
            List of collection dicts with document_count.
        """
        query = select(KBCollection).order_by(KBCollection.created_at.desc())

        # Superadmin and admin can see all
        if user_role not in ("superadmin", "admin"):
            # Filter by user-specific or role-based access
            accessible_ids_query = select(CollectionAccess.collection_id).where(
                (CollectionAccess.user_id == user_id)
                | (CollectionAccess.role == user_role)
            )
            query = query.where(KBCollection.id.in_(accessible_ids_query))

        result = await self.db.execute(query)
        collections = list(result.scalars().all())

        # Get document counts
        collection_data = []
        for collection in collections:
            count_result = await self.db.execute(
                select(func.count(Document.id)).where(
                    Document.collection_id == collection.id,
                    Document.status != "deleted",
                )
            )
            doc_count = count_result.scalar() or 0
            collection_data.append({
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "sensitivity": collection.sensitivity,
                "qdrant_name": collection.qdrant_name,
                "document_count": doc_count,
                "created_at": collection.created_at,
                "updated_at": collection.updated_at,
            })

        return collection_data

    async def get_collection(self, collection_id: UUID) -> Optional[KBCollection]:
        """Get a collection by ID."""
        result = await self.db.execute(
            select(KBCollection).where(KBCollection.id == collection_id)
        )
        return result.scalar_one_or_none()

    async def update_collection(
        self,
        collection_id: UUID,
        updated_by: UUID,
        **update_data,
    ) -> KBCollection:
        """Update collection details."""
        collection = await self.get_collection(collection_id)
        if collection is None:
            raise ValueError("Collection tidak ditemukan.")

        for key, value in update_data.items():
            if value is not None and hasattr(collection, key):
                setattr(collection, key, value)

        collection.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return collection

    async def delete_collection(
        self,
        collection_id: UUID,
        deleted_by: UUID,
    ) -> str:
        """Delete a collection and return its Qdrant name for cleanup.

        Returns:
            The qdrant_name for external cleanup.
        """
        collection = await self.get_collection(collection_id)
        if collection is None:
            raise ValueError("Collection tidak ditemukan.")

        qdrant_name = collection.qdrant_name

        audit = AuditLog(
            user_id=deleted_by,
            action="collection_delete",
            resource="collection",
            resource_id=collection_id,
            action_metadata={"name": collection.name},
        )
        self.db.add(audit)

        await self.db.delete(collection)
        await self.db.flush()

        return qdrant_name

    # ─── Document Methods ──────────────────────────────

    async def create_document(
        self,
        collection_id: UUID,
        original_name: str,
        stored_path: str,
        file_size: int,
        mime_type: str,
        uploaded_by: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        doc_date=None,
    ) -> Document:
        """Create a document record (status: uploading)."""
        doc = Document(
            collection_id=collection_id,
            original_name=original_name,
            stored_path=stored_path,
            file_size=file_size,
            mime_type=mime_type,
            title=title or original_name,
            description=description,
            category=category,
            doc_date=doc_date,
            uploaded_by=uploaded_by,
            status="uploading",
        )
        self.db.add(doc)
        await self.db.flush()

        audit = AuditLog(
            user_id=uploaded_by,
            action="doc_upload",
            resource="document",
            resource_id=doc.id,
            action_metadata={"filename": original_name, "collection_id": str(collection_id)},
        )
        self.db.add(audit)

        return doc

    async def list_documents(
        self,
        collection_id: UUID,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
    ) -> tuple[list[Document], int]:
        """List documents in a collection with pagination."""
        query = select(Document).where(
            Document.collection_id == collection_id,
            Document.status != "deleted",
        )
        count_query = select(func.count(Document.id)).where(
            Document.collection_id == collection_id,
            Document.status != "deleted",
        )

        if status_filter:
            query = query.where(Document.status == status_filter)
            count_query = count_query.where(Document.status == status_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        query = query.order_by(Document.created_at.desc()).offset(offset).limit(per_page)
        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """Get a document by ID."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def update_document_status(
        self,
        document_id: UUID,
        new_status: str,
        chunk_count: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Update document indexing status."""
        doc = await self.get_document(document_id)
        if doc is None:
            return

        doc.status = new_status
        doc.chunk_count = chunk_count
        doc.error_message = error_message
        doc.updated_at = datetime.now(timezone.utc)

        if new_status == "indexed":
            doc.indexed_at = datetime.now(timezone.utc)

        await self.db.flush()

    async def delete_document(
        self,
        document_id: UUID,
        deleted_by: UUID,
    ) -> Document:
        """Soft-delete a document by setting status to 'deleted'."""
        doc = await self.get_document(document_id)
        if doc is None:
            raise ValueError("Dokumen tidak ditemukan.")

        doc.status = "deleted"
        doc.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            user_id=deleted_by,
            action="doc_delete",
            resource="document",
            resource_id=document_id,
            action_metadata={"filename": doc.original_name},
        )
        self.db.add(audit)
        await self.db.flush()

        return doc

    # ─── Access Control Methods ────────────────────────

    async def list_access_rules(self, collection_id: UUID) -> list[CollectionAccess]:
        """List access rules for a collection."""
        result = await self.db.execute(
            select(CollectionAccess).where(
                CollectionAccess.collection_id == collection_id
            )
        )
        return list(result.scalars().all())

    async def grant_access(
        self,
        collection_id: UUID,
        granted_by: UUID,
        user_id: Optional[UUID] = None,
        role: Optional[str] = None,
    ) -> CollectionAccess:
        """Grant access to a collection for a user or role."""
        if user_id is None and role is None:
            raise ValueError("Harus menyertakan user_id atau role.")

        access = CollectionAccess(
            collection_id=collection_id,
            user_id=user_id,
            role=role,
            granted_by=granted_by,
        )
        self.db.add(access)
        await self.db.flush()
        return access

    async def revoke_access(self, access_id: UUID) -> None:
        """Remove an access rule."""
        result = await self.db.execute(
            select(CollectionAccess).where(CollectionAccess.id == access_id)
        )
        access = result.scalar_one_or_none()
        if access:
            await self.db.delete(access)
            await self.db.flush()
