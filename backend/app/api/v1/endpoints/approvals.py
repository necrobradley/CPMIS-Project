from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import (
    ApprovalRequest, ApprovalStatus, DocumentSyncSession, DocumentSyncStatus,
    Notification, Project, Task, User, UserRole,
)
from app.schemas.schemas import ApprovalCreate, ApprovalDecision, ApprovalResponse
from app.services.audit_service import log_audit
from app.services.n8n_service import n8n_service
from app.services.project_controls import recalculate_project_controls
from app.services.report_workflow import can_access_project, ensure_project_access
from app.services.task_approval import apply_task_approval_decision

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", response_model=List[ApprovalResponse])
def list_approvals(
    project_id: Optional[int] = Query(None),
    status: Optional[ApprovalStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ApprovalRequest)
    if project_id:
        query = query.filter(ApprovalRequest.project_id == project_id)
    if status:
        query = query.filter(ApprovalRequest.status == status)

    if current_user.role not in (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER):
        query = query.filter(
            (ApprovalRequest.requested_by == current_user.id) |
            (ApprovalRequest.approver_id == current_user.id)
        )

    approvals = query.order_by(ApprovalRequest.created_at.desc()).all()
    if current_user.role == UserRole.MANAGER:
        project_map = {project.id: project for project in db.query(Project).all()}
        return [item for item in approvals if item.project_id in project_map and can_access_project(current_user, project_map[item.project_id])]
    return approvals


@router.post("", response_model=ApprovalResponse, status_code=201)
def create_approval(
    data: ApprovalCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    approval = ApprovalRequest(
        **data.model_dump(),
        requested_by=current_user.id,
        status=ApprovalStatus.PENDING,
    )
    db.add(approval)
    db.flush()

    if data.approver_id:
        approver = db.query(User).filter(User.id == data.approver_id).first()
        db.add(Notification(
            user_id=data.approver_id,
            title="Approval baru",
            message=f"{current_user.name} meminta approval: {data.title}",
            type="approval",
            related_project_id=data.project_id,
            sent_to_telegram=False,
        ))
        background_tasks.add_task(
            n8n_service.trigger_approval_request,
            approval_id=approval.id,
            project_id=approval.project_id,
            title=approval.title,
            approval_type=approval.approval_type.value,
            requester_name=current_user.name,
            approver_telegram_id=approver.telegram_id if approver else None,
            due_date=approval.due_date.isoformat() if approval.due_date else None,
        )

    log_audit(
        db,
        actor_id=current_user.id,
        action="approval.created",
        entity_type="approval",
        entity_id=approval.id,
        project_id=approval.project_id,
        summary=f"Approval dibuat: {approval.title}",
        after=data.model_dump(),
    )
    db.commit()
    db.refresh(approval)
    return approval


@router.patch("/{approval_id}/decision", response_model=ApprovalResponse)
def decide_approval(
    approval_id: int,
    decision: ApprovalDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval tidak ditemukan")
    ensure_project_access(current_user, approval.project)

    allowed = current_user.role in (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)
    allowed = allowed or approval.approver_id == current_user.id
    if not allowed:
        raise HTTPException(status_code=403, detail="Akses approval ditolak")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval sudah memiliki keputusan")

    before = {
        "status": approval.status.value,
        "decision_note": approval.decision_note,
        "decided_by": approval.decided_by,
    }

    approval.status = decision.status
    approval.decision_note = decision.decision_note
    approval.decided_by = current_user.id
    approval.decided_at = datetime.utcnow()

    if approval.related_entity_type == "document_sync" and approval.related_entity_id:
        sync_session = db.query(DocumentSyncSession).filter(
            DocumentSyncSession.id == approval.related_entity_id
        ).first()
        if sync_session:
            sync_session.reviewed_by = current_user.id
            sync_session.reviewed_at = approval.decided_at
            if decision.status == ApprovalStatus.APPROVED:
                sync_session.status = DocumentSyncStatus.APPROVED
            elif decision.status == ApprovalStatus.REJECTED:
                sync_session.status = DocumentSyncStatus.REJECTED
            else:
                sync_session.status = DocumentSyncStatus.CANCELLED
            log_audit(
                db,
                actor_id=current_user.id,
                action=f"document.sync.{decision.status.value}",
                entity_type="document_sync",
                entity_id=sync_session.id,
                project_id=approval.project_id,
                summary=f"Sinkronisasi dokumen {decision.status.value}",
                before={"status": DocumentSyncStatus.PENDING_APPROVAL.value},
                after={"status": sync_session.status.value, "approval_id": approval.id},
            )
    elif approval.related_entity_type == "task" and approval.related_entity_id:
        task = db.query(Task).filter(Task.id == approval.related_entity_id).first()
        if task:
            before_task = {
                "approval_status": task.approval_status,
                "approval_id": task.approval_id,
            }
            apply_task_approval_decision(
                task,
                decision.status,
                current_user.id,
                decision.decision_note,
            )
            task.approval_id = approval.id
            if decision.status == ApprovalStatus.APPROVED and task.assigned_to:
                db.add(Notification(
                    user_id=task.assigned_to,
                    title="Task aktif",
                    message=f"Task '{task.title}' sudah approved dan dapat dikerjakan.",
                    type="task",
                    related_task_id=task.id,
                    related_project_id=task.project_id,
                    sent_to_telegram=False,
                ))
            recalculate_project_controls(db, task.project_id)
            log_audit(
                db,
                actor_id=current_user.id,
                action=f"task.approval_{decision.status.value}",
                entity_type="task",
                entity_id=task.id,
                project_id=approval.project_id,
                summary=f"Approval task {decision.status.value}: {task.title}",
                before=before_task,
                after={
                    "approval_status": task.approval_status,
                    "approved_by": task.approved_by,
                    "approved_at": task.approved_at,
                },
            )

    db.add(Notification(
        user_id=approval.requested_by,
        title=f"Approval {decision.status.value}",
        message=f"Approval '{approval.title}' diputuskan oleh {current_user.name}.",
        type="approval",
        related_project_id=approval.project_id,
        sent_to_telegram=False,
    ))

    log_audit(
        db,
        actor_id=current_user.id,
        action=f"approval.{decision.status.value}",
        entity_type="approval",
        entity_id=approval.id,
        project_id=approval.project_id,
        summary=f"Approval {decision.status.value}: {approval.title}",
        before=before,
        after={
            "status": decision.status.value,
            "decision_note": decision.decision_note,
            "decided_by": current_user.id,
        },
    )
    db.commit()
    db.refresh(approval)
    return approval
