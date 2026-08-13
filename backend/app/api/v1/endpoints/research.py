import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.database import get_db
from app.models.user import (
    ApprovalRequest, AuditLog, DailyReport, Document, Notification,
    Project, Task, User, UserRole,
)
from app.services.audit_service import log_audit

router = APIRouter(prefix="/research", tags=["Research Export"])


def _value(value: Any):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _row(obj, fields: list[str], anonymize: bool = False):
    data = {}
    for field in fields:
        value = getattr(obj, field, None)
        if anonymize and field in {"name", "email", "phone", "telegram_id"} and value:
            value = f"anon_{obj.id}"
        data[field] = _value(value)
    return data


@router.get("/export")
def export_research_data(
    format: str = Query("json", pattern="^(json|csv)$"),
    anonymize: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.DIRECTOR)),
):
    dataset = {
        "generated_at": datetime.utcnow().isoformat(),
        "anonymized": anonymize,
        "projects": [
            _row(p, ["id", "project_name", "status", "location", "progress_percent", "created_at"], anonymize)
            for p in db.query(Project).all()
        ],
        "users": [
            _row(u, ["id", "name", "email", "role", "phone", "telegram_id", "is_active", "created_at"], anonymize)
            for u in db.query(User).all()
        ],
        "tasks": [
            _row(t, ["id", "project_id", "assigned_to", "created_by", "title", "priority", "status", "deadline", "progress_percent", "ai_generated", "created_at"], anonymize)
            for t in db.query(Task).all()
        ],
        "reports": [
            _row(r, ["id", "project_id", "user_id", "report_date", "weather", "manpower_count", "ai_summary", "ai_risks", "created_at"], anonymize)
            for r in db.query(DailyReport).all()
        ],
        "documents": [
            _row(d, ["id", "project_id", "uploaded_by", "file_name", "file_type", "file_size", "version", "created_at"], anonymize)
            for d in db.query(Document).all()
        ],
        "approvals": [
            _row(a, ["id", "project_id", "requested_by", "approver_id", "approval_type", "status", "created_at", "decided_at"], anonymize)
            for a in db.query(ApprovalRequest).all()
        ],
        "notifications": [
            _row(n, ["id", "user_id", "type", "is_read", "related_task_id", "related_project_id", "sent_to_telegram", "created_at"], anonymize)
            for n in db.query(Notification).all()
        ],
        "audit_logs": [
            _row(a, ["id", "actor_id", "project_id", "action", "entity_type", "entity_id", "summary", "channel", "created_at"], anonymize)
            for a in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000).all()
        ],
    }

    log_audit(
        db,
        actor_id=current_user.id,
        action="research.exported",
        entity_type="research_export",
        summary=f"Research export generated as {format}",
        after={"format": format, "anonymize": anonymize},
    )
    db.commit()

    if format == "json":
        return JSONResponse(dataset)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["table", "id", "field", "value"])
    for table, rows in dataset.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            row_id = row.get("id", "")
            for field, value in row.items():
                writer.writerow([table, row_id, field, value])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=digicom-pmis-research-export.csv"},
    )
