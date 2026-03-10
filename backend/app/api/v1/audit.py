"""ExecMind - Audit log API endpoints."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.database import get_db_session
from app.models.audit import AuditLog
from app.models.user import User
from app.utils.logging import get_logger

router = APIRouter(prefix="/audit", tags=["Audit"])
logger = get_logger("audit_router")


class AuditLogResponse:
    """Audit log entry response (used for JSON serialization)."""
    pass


@router.get("/logs")
async def list_audit_logs(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List audit logs with filtering and pagination (admin+ only)."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
        count_query = count_query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
        count_query = count_query.where(AuditLog.created_at <= end_date)

    # Total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginated results
    offset = (page - 1) * per_page
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    logs = list(result.scalars().all())

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action,
                "resource": log.resource,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "metadata": log.action_metadata,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/logs/export")
async def export_audit_logs(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """Export audit logs as JSON or CSV (admin+ only)."""
    import csv
    import io
    import json

    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    result = await db.execute(query)
    logs = list(result.scalars().all())

    log_dicts = [
        {
            "id": log.id,
            "user_id": str(log.user_id) if log.user_id else None,
            "action": log.action,
            "resource": log.resource,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "metadata": json.dumps(log.action_metadata) if log.action_metadata else "{}",
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

    if format == "csv":
        output = io.StringIO()
        if log_dicts:
            writer = csv.DictWriter(output, fieldnames=log_dicts[0].keys())
            writer.writeheader()
            writer.writerows(log_dicts)
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
        )

    return StreamingResponse(
        iter([json.dumps(log_dicts, indent=2, default=str)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_logs.json"},
    )


@router.get("/stats")
async def get_audit_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Dashboard statistics: query count, active users, etc. (admin+ only)."""
    from sqlalchemy import distinct

    # Total queries
    total_queries_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.action == "chat_query")
    )
    total_queries = total_queries_result.scalar() or 0

    # Total logins
    total_logins_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.action == "login")
    )
    total_logins = total_logins_result.scalar() or 0

    # Unique active users (from login events)
    active_users_result = await db.execute(
        select(func.count(distinct(AuditLog.user_id))).where(
            AuditLog.action == "login"
        )
    )
    active_users = active_users_result.scalar() or 0

    # Total document uploads
    total_uploads_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.action == "doc_upload")
    )
    total_uploads = total_uploads_result.scalar() or 0

    return {
        "total_queries": total_queries,
        "total_logins": total_logins,
        "active_users": active_users,
        "total_document_uploads": total_uploads,
    }
