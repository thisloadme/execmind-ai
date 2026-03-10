"""ExecMind - Knowledge Base API endpoints."""

import os
import shutil
import uuid as uuid_module
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin, require_superadmin
from app.core.config import settings
from app.core.database import get_db_session
from app.models.user import User
from app.schemas.kb import (
    AccessRuleCreate,
    AccessRuleResponse,
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
    DocumentListResponse,
    DocumentResponse,
)
from app.services.kb_service import KBService
from app.utils.logging import get_logger

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])
logger = get_logger("kb_router")


# ─── Collections ───────────────────────────────────

@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List KB collections accessible to the current user."""
    kb_service = KBService(db)
    collection_data = await kb_service.list_collections(
        user_id=current_user.id,
        user_role=current_user.role,
    )

    collections = [CollectionResponse(**c) for c in collection_data]
    return CollectionListResponse(collections=collections, total=len(collections))


@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    body: CollectionCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Create a new KB collection (admin+ only)."""
    kb_service = KBService(db)
    collection = await kb_service.create_collection(
        name=body.name,
        description=body.description,
        sensitivity=body.sensitivity,
        created_by=current_user.id,
    )

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        sensitivity=collection.sensitivity,
        qdrant_name=collection.qdrant_name,
        document_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get collection details by ID."""
    kb_service = KBService(db)
    collection = await kb_service.get_collection(collection_id)

    if collection is None:
        raise HTTPException(status_code=404, detail="Collection tidak ditemukan.")

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        sensitivity=collection.sensitivity,
        qdrant_name=collection.qdrant_name,
        document_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.put("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: uuid_module.UUID,
    body: CollectionUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update collection details (admin+ only)."""
    kb_service = KBService(db)
    try:
        collection = await kb_service.update_collection(
            collection_id=collection_id,
            updated_by=current_user.id,
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        sensitivity=collection.sensitivity,
        qdrant_name=collection.qdrant_name,
        document_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Delete a collection and all its documents (superadmin only)."""
    kb_service = KBService(db)
    try:
        qdrant_name = await kb_service.delete_collection(
            collection_id=collection_id,
            deleted_by=current_user.id,
        )
        
        # Delete Qdrant collection
        if qdrant_name:
            try:
                from qdrant_client import QdrantClient
                from app.services.rag.indexer import QdrantIndexer
                qdrant = QdrantClient(url=settings.QDRANT_URL)
                indexer = QdrantIndexer(qdrant)
                indexer.delete_collection(qdrant_name)
            except Exception as q_err:
                logger.warning(f"Failed to delete qdrant collection {qdrant_name}: {q_err}")

        # Delete physical directory
        collection_dir = os.path.join(
            settings.DOCUMENT_STORAGE_PATH,
            str(collection_id),
        )
        if os.path.exists(collection_dir):
            try:
                shutil.rmtree(collection_dir)
            except Exception as f_err:
                logger.warning(f"Failed to delete directory {collection_dir}: {f_err}")

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Documents ─────────────────────────────────────

@router.get("/collections/{collection_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    collection_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    document_status: Optional[str] = Query(None, alias="status"),
):
    """List documents in a collection."""
    kb_service = KBService(db)
    documents, total = await kb_service.list_documents(
        collection_id=collection_id,
        page=page,
        per_page=per_page,
        status_filter=document_status,
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
    )


@router.post(
    "/collections/{collection_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    collection_id: uuid_module.UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
):
    """Upload a document for indexing (admin+ only).

    The document is saved to disk and a background job processes it.
    """
    # Validate file size
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File terlalu besar. Maksimal {settings.MAX_FILE_SIZE_MB}MB.",
        )
    await file.seek(0)

    # Validate MIME type
    content_type = file.content_type or "application/octet-stream"
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
    }
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipe file tidak didukung: {content_type}",
        )

    # Check collection exists
    kb_service = KBService(db)
    collection = await kb_service.get_collection(collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection tidak ditemukan.")

    # Save file to disk
    doc_id = str(uuid_module.uuid4())
    collection_dir = os.path.join(
        settings.DOCUMENT_STORAGE_PATH,
        str(collection_id),
    )
    os.makedirs(collection_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename or "")[1]
    stored_path = os.path.join(collection_dir, f"{doc_id}{file_ext}")

    with open(stored_path, "wb") as f:
        f.write(content)

    # Create document record
    document = await kb_service.create_document(
        collection_id=collection_id,
        original_name=file.filename or "unnamed",
        stored_path=stored_path,
        file_size=len(content),
        mime_type=content_type,
        uploaded_by=current_user.id,
        title=title,
        description=description,
        category=category,
    )

    # Ensure document is committed before background task runs
    await db.commit()
    await db.refresh(document)

    # Queue background indexing
    background_tasks.add_task(
        _process_document_background,
        document_id=str(document.id),
        collection_id=str(collection_id),
        qdrant_collection_name=collection.qdrant_name,
        file_path=stored_path,
        mime_type=content_type,
        doc_title=title or file.filename or "unnamed",
        doc_category=category,
        sensitivity=collection.sensitivity,
    )

    return DocumentResponse.model_validate(document)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get document details and indexing status."""
    kb_service = KBService(db)
    document = await kb_service.get_document(document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")

    return DocumentResponse.model_validate(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Delete a document and its vector chunks (admin+ only)."""
    kb_service = KBService(db)
    try:
        doc = await kb_service.delete_document(
            document_id=document_id,
            deleted_by=current_user.id,
        )
        
        # Get collection to find qdrant_name
        collection = await kb_service.get_collection(doc.collection_id)
        
        # Delete from Qdrant
        if collection and collection.qdrant_name:
            try:
                from qdrant_client import QdrantClient
                from app.services.rag.indexer import QdrantIndexer
                qdrant = QdrantClient(url=settings.QDRANT_URL)
                indexer = QdrantIndexer(qdrant)
                indexer.delete_by_document(collection.qdrant_name, str(document_id))
            except Exception as q_err:
                logger.warning(f"Failed to delete vectors for {document_id}: {q_err}")

        # Delete physical file
        if doc.stored_path and os.path.exists(doc.stored_path):
            try:
                os.unlink(doc.stored_path)
            except Exception as f_err:
                logger.warning(f"Failed to delete file {doc.stored_path}: {f_err}")

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Access Control ────────────────────────────────

@router.get("/collections/{collection_id}/access", response_model=list[AccessRuleResponse])
async def list_access_rules(
    collection_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List access rules for a collection (admin+ only)."""
    kb_service = KBService(db)
    rules = await kb_service.list_access_rules(collection_id)
    return [AccessRuleResponse.model_validate(r) for r in rules]


@router.post(
    "/collections/{collection_id}/access",
    response_model=AccessRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_access(
    collection_id: uuid_module.UUID,
    body: AccessRuleCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Grant a user or role access to a collection (admin+ only)."""
    kb_service = KBService(db)
    try:
        access = await kb_service.grant_access(
            collection_id=collection_id,
            granted_by=current_user.id,
            user_id=body.user_id,
            role=body.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return AccessRuleResponse.model_validate(access)


@router.delete(
    "/collections/{collection_id}/access/{access_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_access(
    collection_id: uuid_module.UUID,
    access_id: uuid_module.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Revoke an access rule (admin+ only)."""
    kb_service = KBService(db)
    await kb_service.revoke_access(access_id)


# ─── Background Task ──────────────────────────────

async def _process_document_background(
    document_id: str,
    collection_id: str,
    qdrant_collection_name: str,
    file_path: str,
    mime_type: str,
    doc_title: str,
    doc_category: str | None,
    sensitivity: str,
) -> None:
    """Background task to process and index a document."""
    from app.core.database import async_session_factory
    from app.services.kb_service import KBService
    from app.services.rag.document_processor import DocumentProcessor
    from app.services.rag.indexer import QdrantIndexer

    logger.info("background_indexing_started", document_id=document_id)

    async with async_session_factory() as db:
        kb_service = KBService(db)
        document_id_uuid = uuid_module.UUID(document_id)

        try:
            await kb_service.update_document_status(document_id_uuid, "processing")
            await db.commit()

            # Process document
            processor = DocumentProcessor()
            points = await processor.process_document(
                file_path=file_path,
                mime_type=mime_type,
                document_id=document_id,
                collection_id=collection_id,
                doc_title=doc_title,
                doc_category=doc_category,
                sensitivity=sensitivity,
            )

            # Index into Qdrant
            try:
                from qdrant_client import QdrantClient
                qdrant = QdrantClient(url=settings.QDRANT_URL)
                indexer = QdrantIndexer(qdrant)
                indexer.ensure_collection(qdrant_collection_name)
                indexer.upsert_points(qdrant_collection_name, points)
            except Exception as e:
                logger.warning("qdrant_indexing_failed", error=str(e))

            # Update status
            await kb_service.update_document_status(
                document_id_uuid,
                "indexed",
                chunk_count=len(points),
            )
            await db.commit()

            logger.info(
                "background_indexing_complete",
                document_id=document_id,
                chunks=len(points),
            )

        except Exception as e:
            logger.error(
                "background_indexing_failed",
                document_id=document_id,
                error=str(e),
            )
            await kb_service.update_document_status(
                document_id_uuid,
                "failed",
                error_message=str(e),
            )
            await db.commit()
