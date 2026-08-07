from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import (
    ApprovalRequest, ApprovalStatus, ApprovalType, Notification, Project,
    ProjectMembership, Task, User,
)


PROJECT_MANAGER_ROLE_CODES = {"project_manager"}


def task_is_approved(task: Task) -> bool:
    return (task.approval_status or ApprovalStatus.APPROVED.value) == ApprovalStatus.APPROVED.value


def select_task_approver(
    db: Session,
    project: Project,
    requester_id: Optional[int] = None,
    explicit_approver_id: Optional[int] = None,
) -> Optional[int]:
    if explicit_approver_id:
        return explicit_approver_id

    project_managers = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.project_role.in_(PROJECT_MANAGER_ROLE_CODES),
        ProjectMembership.is_active == True,
    ).order_by(ProjectMembership.id.asc()).all()
    for membership in project_managers:
        if membership.user_id != requester_id:
            return membership.user_id
    if project_managers:
        return project_managers[0].user_id
    return project.owner_id


def request_task_approval(
    db: Session,
    task: Task,
    requester: User,
    approver_id: Optional[int] = None,
    description: Optional[str] = None,
) -> ApprovalRequest:
    task.approval_status = ApprovalStatus.PENDING.value
    task.approved_by = None
    task.approved_at = None
    task.approval_note = None
    selected_approver_id = select_task_approver(
        db,
        task.project,
        requester_id=requester.id,
        explicit_approver_id=approver_id,
    )
    approval = ApprovalRequest(
        project_id=task.project_id,
        requested_by=requester.id,
        approver_id=selected_approver_id,
        title=f"Approval task: {task.title}",
        description=description or (
            "Task menunggu review Project Manager sebelum aktif, muncul di work queue, "
            "dan dapat dilaporkan oleh PIC."
        ),
        approval_type=ApprovalType.TASK,
        status=ApprovalStatus.PENDING,
        related_entity_type="task",
        related_entity_id=task.id,
        due_date=task.deadline or datetime.utcnow() + timedelta(days=2),
    )
    db.add(approval)
    db.flush()
    task.approval_id = approval.id

    if selected_approver_id:
        db.add(Notification(
            user_id=selected_approver_id,
            title="Task menunggu approval PM",
            message=f"Task '{task.title}' perlu disetujui sebelum aktif.",
            type="approval",
            related_task_id=task.id,
            related_project_id=task.project_id,
            sent_to_telegram=False,
        ))
    return approval


def apply_task_approval_decision(
    task: Task,
    status: ApprovalStatus,
    actor_id: int,
    note: Optional[str] = None,
) -> None:
    task.approval_status = status.value
    task.approval_note = note
    if status == ApprovalStatus.APPROVED:
        task.approved_by = actor_id
        task.approved_at = datetime.utcnow()
    else:
        task.approved_by = None
        task.approved_at = None