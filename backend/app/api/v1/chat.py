"""ExecMind - Chat API endpoints with SSE streaming."""

import base64
import json
import os
import shutil
from typing import Annotated
from uuid import UUID

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db_session
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionResponse,
    FeedbackRequest,
)
from app.services.chat_service import ChatService
from app.services.kb_service import KBService
from app.services.rag.document_processor import DocumentProcessor
from app.services.rag.query_engine import RAGQueryEngine
from app.utils.logging import get_logger

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = get_logger("chat_router")


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """List all chat sessions for the current user."""
    chat_service = ChatService(db)
    sessions = await chat_service.list_sessions(current_user.id)

    return ChatSessionListResponse(
        sessions=[ChatSessionResponse.model_validate(s) for s in sessions],
        total=len(sessions),
    )


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    body: ChatSessionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Create a new chat session."""
    chat_service = ChatService(db)
    session = await chat_service.create_session(
        user_id=current_user.id,
        title=body.title,
        collection_id=body.collection_id,
    )

    return ChatSessionResponse.model_validate(session)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get session details with messages."""
    chat_service = ChatService(db)
    session = await chat_service.get_session(session_id, current_user.id)

    if session is None:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan.")

    return ChatSessionResponse.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get all messages in a chat session."""
    chat_service = ChatService(db)
    session = await chat_service.get_session(session_id, current_user.id)

    if session is None:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan.")

    messages = await chat_service.get_messages(session_id)
    return [ChatMessageResponse.model_validate(m) for m in messages]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Delete a chat session and all its messages."""
    chat_service = ChatService(db)
    try:
        await chat_service.delete_session(session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


async def save_chat_metadata(session_id: UUID, state: dict, body_content: str, session_title: str):
    """Background task to save the assistant's response to the database."""
    try:
        from app.core.database import async_session_factory
        async with async_session_factory() as save_db:
            save_service = ChatService(save_db)
            await save_service.save_assistant_message(
                session_id=session_id,
                content=state["full_response"],
                sources=state["sources"],
                tokens_used=state["tokens"],
                latency_ms=state["latency"],
            )

            # Auto-generate title from first message if still default
            if session_title == "New Chat" and body_content:
                preview_title = body_content[:80]
                if len(body_content) > 80:
                    preview_title += "..."
                await save_service.update_session_title(session_id, preview_title)

            await save_db.commit()
    except Exception as e:
        logger.error("save_response_failed", error=str(e))


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    content: str = Form(..., min_length=1, max_length=2000),
    files: list[UploadFile] | None = File(None),
):
    """Send a message and receive a streaming SSE response from the AI.

    The response is delivered via Server-Sent Events with three event types:
    - 'token': individual response tokens
    - 'sources': document source citations
    - 'done': completion metadata (tokens_used, latency_ms)
    """
    chat_service = ChatService(db)
    session = await chat_service.get_session(session_id, current_user.id)

    if session is None:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan.")

    # Save user message
    user_msg_content = content
    if files:
        file_names = [f.filename for f in files if f.filename]
        if file_names:
            user_msg_content += f"\n\n*[Dilampirkan: {', '.join(file_names)}]*"
    
    # Process uploaded files to add to context and save physically
    file_context = ""
    saved_attachments = []
    image_b64s = []
    
    if files:
        processor = DocumentProcessor()
        upload_dir = os.path.join("data", "chat_uploads", str(session_id))
        os.makedirs(upload_dir, exist_ok=True)

        for file in files:
            if not file.filename:
                continue
            
            try:
                # Generate unique but readable filename
                safe_filename = file.filename.replace(" ", "_").replace("/", "-")
                file_path = os.path.join(upload_dir, safe_filename)
                
                # Check if file exists, append number if it does to avoid overwrite
                base, ext = os.path.splitext(safe_filename)
                counter = 1
                while os.path.exists(file_path):
                    file_path = os.path.join(upload_dir, f"{base}_{counter}{ext}")
                    safe_filename = f"{base}_{counter}{ext}"
                    counter += 1

                # Read into memory for extraction
                file_bytes = await file.read()
                
                # Save physically
                with open(file_path, "wb") as f:
                    f.write(file_bytes)
                
                # Add to DB references
                saved_attachments.append({
                    "filename": safe_filename,
                    "content_type": file.content_type,
                    "path": file_path,
                })
                
                # Extract text for LLM Context
                extracted = processor.extract_text_from_bytes(file_bytes, file.filename, file.content_type)
                if extracted:
                    file_context += f"\n\n--- Isi dari lampiran '{file.filename}' ---\n{extracted}"
                
                # If it's an image, encode to base64 for LLM Vision support
                if file.content_type.startswith("image/"):
                    b64_str = base64.b64encode(file_bytes).decode('utf-8')
                    image_b64s.append(b64_str)
            except Exception as e:
                logger.error("file_save_or_extract_failed", file=file.filename, error=str(e))

    # Save user message with physical attachments listed
    await chat_service.save_user_message(session_id, user_msg_content, saved_attachments)

    # If we have file context, inject it into the message sent to LLM
    final_query = content
    if file_context:
        final_query = f"Pengguna melampirkan file berikut sebagai konteks tambahan:\n{file_context}\n\nPertanyaan pengguna: {content}"

    stream_state = {
        "full_response": "",
        "sources": [],
        "tokens": 0,
        "latency": 0,
    }

    async def event_stream():
        """Generate SSE events from the RAG query engine."""
        query_engine = RAGQueryEngine()

        try:
            collection = None
            if session.collection_id:
                kb_service = KBService(db)
                collection = await kb_service.get_collection(session.collection_id)

            # Retrieve previous chat history for LLM Context Window
            # Adding +1 to limit because the current user message was just saved to DB
            recent_msgs = await chat_service.get_recent_messages(
                session_id, limit=settings.CONVERSATION_CONTEXT_WINDOW + 1
            )
            
            history = []
            for m in recent_msgs:
                if m.role in ("user", "assistant"):
                    history.append({"role": m.role, "content": m.content})
            
            # Remove the last message from history as it corresponds to the current query
            # and query_engine will already append it automatically.
            if history and history[-1]["role"] == "user":
                history = history[:-1]
            
            if collection:
                # RAG-augmented query
                try:
                    from qdrant_client import QdrantClient
                    qdrant = QdrantClient(url=settings.QDRANT_URL)
                    query_engine = RAGQueryEngine(qdrant_client=qdrant)
                except Exception:
                    query_engine = RAGQueryEngine()

                stream = query_engine.query_streaming(
                    query=final_query,
                    collection_name=collection.qdrant_name,
                    collection_id=str(collection.id),
                    conversation_history=history,
                    images=image_b64s if image_b64s else None,
                )
            else:
                # Simple chat without RAG
                stream = query_engine.simple_chat(
                    query=final_query,
                    conversation_history=history,
                    images=image_b64s if image_b64s else None,
                )

            async for chunk in stream:
                chunk_type = chunk.get("type")

                if chunk_type == "token":
                    yield f"event: token\ndata: {json.dumps({'content': chunk['content']})}\n\n"
                    stream_state["full_response"] += chunk.get("content", "")

                elif chunk_type == "sources":
                    stream_state["sources"] = chunk.get("sources", [])
                    yield f"event: sources\ndata: {json.dumps({'sources': stream_state['sources']})}\n\n"

                elif chunk_type == "action":
                    yield f"event: action\ndata: {json.dumps({'action_name': chunk.get('action_name'), 'payload': chunk.get('payload')})}\n\n"

                elif chunk_type == "done":
                    stream_state["tokens"] = chunk.get("tokens_used", 0)
                    stream_state["latency"] = chunk.get("latency_ms", 0)
                    if chunk.get("full_response"):
                        stream_state["full_response"] = chunk.get("full_response")

                    yield f"event: done\ndata: {json.dumps({'tokens_used': stream_state['tokens'], 'latency_ms': stream_state['latency']})}\n\n"

        except Exception as e:
            logger.error("streaming_error", error=str(e), session_id=str(session_id))
            error_msg = "Terjadi kesalahan saat memproses pertanyaan Anda."
            yield f"event: token\ndata: {json.dumps({'content': error_msg})}\n\n"
            stream_state["full_response"] += error_msg
            yield f"event: done\ndata: {json.dumps({'tokens_used': 0, 'latency_ms': 0})}\n\n"
        finally:
            # Use asyncio.create_task to detach from the request lifecycle completely.
            # This ensures the DB save executes even if the generator gets a CancelledError
            # from the client disconnecting mid-stream.
            asyncio.create_task(
                save_chat_metadata(
                    session_id=session_id,
                    state=stream_state,
                    body_content=content,
                    session_title=session.title,
                )
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(
    message_id: UUID,
    body: FeedbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Submit feedback on a message (thumbs up: 1, thumbs down: -1)."""
    chat_service = ChatService(db)
    await chat_service.update_feedback(message_id, body.feedback)


@router.get("/sessions/{session_id}/attachments/{filename}")
async def get_attachment(
    session_id: UUID,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Serve an uploaded attachment for a chat session."""
    chat_service = ChatService(db)
    
    # Verify the user actually owns this session before serving the file
    session = await chat_service.get_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan.")
        
    file_path = os.path.join("data", "chat_uploads", str(session_id), filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File lampiran tidak ditemukan.")
        
    return FileResponse(file_path)
