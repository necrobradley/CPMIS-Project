from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import AuditLog, Project, User, UserRole
from app.schemas.schemas import AuditLogResponse
from app.services.report_workflow import can_access_project

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


def _accessible_project_ids(db: Session, user: User):
    if user.role in (UserRole.OWNER, UserRole.DIRECTOR):
        return None
    return [project.id for project in db.query(Project).all() if can_access_project(user, project)]


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    project_id: Optional[int] = Query(None),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    query = db.query(AuditLog)
    accessible_ids = _accessible_project_ids(db, current_user)
    if accessible_ids is not None:
        if project_id and project_id not in accessible_ids:
            raise HTTPException(status_code=403, detail="Audit proyek tidak tersedia untuk akun ini")
        query = query.filter(AuditLog.project_id.in_(accessible_ids or [-1]))
    if project_id:
        query = query.filter(AuditLog.project_id == project_id)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()


@router.get("/recent", response_model=List[AuditLogResponse])
def recent_audit_logs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AuditLog)
    if current_user.role in (UserRole.ADMIN, UserRole.MANAGER):
        query = query.filter(AuditLog.project_id.in_(_accessible_project_ids(db, current_user) or [-1]))
    elif current_user.role not in (UserRole.OWNER, UserRole.DIRECTOR):
        query = query.filter(AuditLog.actor_id == current_user.id)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
