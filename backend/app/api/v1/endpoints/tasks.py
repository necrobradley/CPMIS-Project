from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models.user import (
    User, Task, UserRole, TaskStatus, ApprovalStatus, TaskComment, TaskAttachment, Document,
    DailyReportWorkflow, ReportStatus, TaskRequirement, TaskSpecification,
    ApprovalRequest, CommunicationItem, Division, Project, ProjectMembership, ProjectRolePolicy,
    Notification, TaskControl, TaskMaterialSpecification,
)
from app.schemas.schemas import (
    TaskCreate, TaskUpdate, TaskResponse,
    TaskCommentCreate, TaskCommentResponse, TaskAttachmentResponse,
    TaskMaterialCreate, TaskMaterialResponse, TaskMaterialUpdate,
)
from app.core.security import get_current_user, require_roles
from app.services.audit_service import log_audit
from app.services.project_controls import recalculate_project_controls, task_gate_snapshot
from app.services.project_role_catalog import (
    PROJECT_CROSS_DIVISION_ROLE_CODES,
    PROJECT_DIVISION_LEAD_ROLE_CODES,
    can_role_access_task_division,
    project_role_label,
    role_can_be_task_pic,
)
from app.services.report_workflow import can_access_task, ensure_project_access, ensure_task_access
from app.services.task_approval import request_task_approval, task_is_approved

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _validate_task_classification(
    db: Session,
    *,
    project_id: int,
    division_id: Optional[int],
    assigned_to: Optional[int] = None,
) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    if division_id is None:
        division = None
    else:
        division = db.query(Division).filter(Division.id == division_id).first()
        if not division:
            raise HTTPException(status_code=404, detail="Divisi tidak ditemukan")
        if division.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="Divisi yang dipilih tidak berasal dari proyek task",
            )
    if assigned_to is None:
        return
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == assigned_to,
        ProjectMembership.is_active == True,
    ).first()
    if not membership:
        raise HTTPException(status_code=400, detail="PIC belum menjadi anggota aktif proyek")
    if not role_can_be_task_pic(membership.project_role):
        raise HTTPException(
            status_code=400,
            detail=f"{project_role_label(membership.project_role)} tidak dapat menjadi PIC task",
        )
    policy = db.query(ProjectRolePolicy).filter(
        ProjectRolePolicy.project_id == project_id,
        ProjectRolePolicy.role_code == membership.project_role,
    ).first()
    if policy and not policy.enabled:
        raise HTTPException(
            status_code=409,
            detail=f"{project_role_label(membership.project_role)} sedang dinonaktifkan untuk assignment task",
        )
    if (
        division_id is not None
        and not can_role_access_task_division(membership.project_role, membership.division_id, division_id)
    ):
        raise HTTPException(status_code=400, detail="PIC tidak ditempatkan pada divisi task")


def _replace_task_definition(db: Session, task: Task, specification, requirements, materials) -> None:
    if specification is not None:
        values = specification.model_dump()
        if task.specification:
            for field, value in values.items():
                setattr(task.specification, field, value)
        else:
            task.specification = TaskSpecification(**values)

    if requirements is not None:
        task.requirements.clear()
        for index, item in enumerate(requirements):
            values = item.model_dump()
            values["sequence"] = values.get("sequence", index)
            task.requirements.append(TaskRequirement(**values))

    if materials is not None:
        task.materials.clear()
        for index, item in enumerate(materials):
            values = item.model_dump()
            values["sequence"] = values.get("sequence", index)
            task.materials.append(TaskMaterialSpecification(**values))


@router.get("", response_model=List[TaskResponse])
def list_tasks(
    project_id: Optional[int] = Query(None),
    division_id: Optional[int] = Query(None),
    assigned_to: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil daftar task dengan filter opsional."""
    if scope not in (None, "division", "mine"):
        raise HTTPException(status_code=400, detail="Scope task tidak valid")

    query = db.query(Task)

    if project_id:
        query = query.filter(Task.project_id == project_id)
    if division_id:
        query = query.filter(Task.division_id == division_id)
    if assigned_to:
        query = query.filter(Task.assigned_to == assigned_to)
    if status:
        query = query.filter(Task.status == status)
    if scope == "mine":
        query = query.filter(Task.assigned_to == current_user.id)
    elif scope == "division":
        membership_division_access = exists().where(and_(
            ProjectMembership.project_id == Task.project_id,
            ProjectMembership.user_id == current_user.id,
            ProjectMembership.is_active == True,
            ProjectMembership.division_id.isnot(None),
            ProjectMembership.division_id == Task.division_id,
        ))
        division_filters = [membership_division_access]
        if current_user.division_id is not None:
            division_filters.append(Task.division_id == current_user.division_id)
        query = query.filter(Task.division_id.isnot(None), or_(*division_filters))

    # Staff hanya lihat task milik divisinya sendiri
    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        query = query.filter(Task.approval_status == ApprovalStatus.APPROVED.value)
        member_access = exists().where(and_(
            ProjectMembership.project_id == Task.project_id,
            ProjectMembership.user_id == current_user.id,
            ProjectMembership.is_active == True,
            or_(
                ProjectMembership.division_id == Task.division_id,
                ProjectMembership.project_role.in_(
                    list(PROJECT_CROSS_DIVISION_ROLE_CODES | PROJECT_DIVISION_LEAD_ROLE_CODES)
                ),
            ),
        ))
        query = query.filter(or_(Task.assigned_to == current_user.id, member_access))

    tasks = query.order_by(Task.deadline.asc()).all()
    if current_user.role == UserRole.DIRECTOR:
        return tasks
    return [task for task in tasks if can_access_task(current_user, task)]


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER))
):
    """Buat task baru."""
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    _validate_task_classification(
        db, project_id=data.project_id, division_id=data.division_id,
        assigned_to=data.assigned_to,
    )
    values = data.model_dump(exclude={"approval_approver_id", "specification", "requirements", "materials"})
    task = Task(**values, created_by=current_user.id)
    db.add(task)
    db.flush()
    if task.deadline:
        db.add(TaskControl(
            task_id=task.id,
            planned_start=task.created_at,
            planned_finish=task.deadline,
        ))
    _replace_task_definition(db, task, data.specification, data.requirements, data.materials)
    approval = request_task_approval(
        db,
        task,
        current_user,
        approver_id=data.approval_approver_id,
    )
    log_audit(
        db,
        actor_id=current_user.id,
        action="task.approval_requested",
        entity_type="task",
        entity_id=task.id,
        project_id=task.project_id,
        summary=f"Task diajukan untuk approval PM: {task.title}",
        after={**data.model_dump(mode="json"), "approval_id": approval.id},
    )
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil detail satu task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER))
):
    """Update task (status, progress, dll)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)

    if "division_id" in data.model_fields_set or "assigned_to" in data.model_fields_set:
        next_division_id = data.division_id if "division_id" in data.model_fields_set else task.division_id
        next_assigned_to = data.assigned_to if "assigned_to" in data.model_fields_set else task.assigned_to
        _validate_task_classification(
            db, project_id=task.project_id, division_id=next_division_id,
            assigned_to=next_assigned_to,
        )

    before = {
        "title": task.title,
        "description": task.description,
        "assigned_to": task.assigned_to,
        "division_id": task.division_id,
        "priority": task.priority.value if task.priority else None,
        "status": task.status.value if task.status else None,
        "deadline": task.deadline,
        "progress_percent": task.progress_percent,
    }
    changes = data.model_dump(exclude_unset=True, mode="json")
    if data.status is not None and data.status != task.status:
        raise HTTPException(
            status_code=400,
            detail="Perubahan status wajib melalui endpoint status agar workflow gate diperiksa",
        )
    task_changes = data.model_dump(
        exclude_unset=True, exclude={"specification", "requirements", "materials"}
    )
    for field, value in task_changes.items():
        setattr(task, field, value)
    _replace_task_definition(db, task, data.specification, data.requirements, data.materials)

    log_audit(
        db,
        actor_id=current_user.id,
        action="task.updated",
        entity_type="task",
        entity_id=task.id,
        project_id=task.project_id,
        summary=f"Task diupdate: {task.title}",
        before=before,
        after=changes,
    )
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: int,
    status: TaskStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update status task saja (endpoint cepat untuk Kanban board)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    if not task_is_approved(task):
        raise HTTPException(
            status_code=409,
            detail="Task belum approved oleh Project Manager sehingga status belum dapat diubah",
        )

    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        if task.assigned_to != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Staff hanya dapat update status task yang ditugaskan langsung kepadanya",
            )
        allowed = {
            TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
            TaskStatus.IN_PROGRESS: {TaskStatus.REVIEW, TaskStatus.BLOCKED},
            TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS},
            TaskStatus.REVIEW: set(),
            TaskStatus.DONE: set(),
        }
        if status not in allowed.get(task.status, set()):
            raise HTTPException(
                status_code=409,
                detail="Staff hanya dapat memulai, mengirim ke review, atau menandai task terhambat",
            )

    gate = task_gate_snapshot(db, task)
    if status == TaskStatus.IN_PROGRESS and not gate["can_start"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Task belum dapat dimulai karena construction start gate belum terpenuhi",
                "blockers": gate["start_blockers"],
            },
        )
    if status == TaskStatus.DONE and not gate["can_complete"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Task belum dapat selesai karena completion gate belum terpenuhi",
                "blockers": gate["completion_blockers"],
            },
        )

    before_status = task.status.value if task.status else None
    task.status = status
    if status == TaskStatus.DONE:
        task.progress_percent = 100
    recalculate_project_controls(db, task.project_id)
    log_audit(
        db,
        actor_id=current_user.id,
        action="task.status_changed",
        entity_type="task",
        entity_id=task.id,
        project_id=task.project_id,
        summary=f"Status task berubah: {task.title}",
        before={"status": before_status},
        after={"status": status.value},
    )
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}/comments", response_model=List[TaskCommentResponse])
def list_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    return db.query(TaskComment).filter(TaskComment.task_id == task_id).order_by(TaskComment.created_at.asc()).all()


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
def create_task_comment(
    task_id: int,
    data: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    comment = TaskComment(task_id=task_id, user_id=current_user.id, comment=data.comment)
    db.add(comment)
    db.flush()
    log_audit(
        db,
        actor_id=current_user.id,
        action="task.comment_added",
        entity_type="task",
        entity_id=task.id,
        project_id=task.project_id,
        summary=f"Komentar ditambahkan pada task: {task.title}",
        after={"comment": data.comment},
    )
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{task_id}/attachments", response_model=List[TaskAttachmentResponse])
def list_task_attachments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    return db.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).order_by(TaskAttachment.created_at.desc()).all()


@router.post("/{task_id}/attachments", response_model=TaskAttachmentResponse, status_code=201)
def link_document_to_task(
    task_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    doc = db.query(Document).filter(Document.id == document_id, Document.project_id == task.project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan pada proyek task")
    attachment = TaskAttachment(
        task_id=task.id,
        document_id=doc.id,
        uploaded_by=current_user.id,
        file_name=doc.file_name,
        file_path=doc.file_path,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
    )
    db.add(attachment)
    db.flush()
    log_audit(
        db,
        actor_id=current_user.id,
        action="task.attachment_added",
        entity_type="task",
        entity_id=task.id,
        project_id=task.project_id,
        summary=f"Dokumen dilampirkan ke task: {task.title}",
        after={"document_id": doc.id, "file_name": doc.file_name},
    )
    db.commit()
    db.refresh(attachment)
    return attachment


def _validate_material_source(db: Session, task: Task, source_document_id: Optional[int]) -> None:
    if source_document_id is None:
        return
    document = db.query(Document).filter(
        Document.id == source_document_id,
        Document.project_id == task.project_id,
    ).first()
    if not document:
        raise HTTPException(status_code=400, detail="Dokumen sumber material tidak berasal dari proyek task")


@router.get("/{task_id}/materials", response_model=List[TaskMaterialResponse])
def list_task_materials(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    return db.query(TaskMaterialSpecification).filter(
        TaskMaterialSpecification.task_id == task_id
    ).order_by(TaskMaterialSpecification.sequence, TaskMaterialSpecification.id).all()


@router.post("/{task_id}/materials", response_model=TaskMaterialResponse, status_code=201)
def create_task_material(
    task_id: int,
    data: TaskMaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    _validate_material_source(db, task, data.source_document_id)
    material = TaskMaterialSpecification(task_id=task.id, **data.model_dump())
    db.add(material)
    db.flush()
    log_audit(
        db, actor_id=current_user.id, action="task.material_created",
        entity_type="task_material", entity_id=material.id, project_id=task.project_id,
        summary=f"Material task ditambahkan: {material.material_name}",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(material)
    return material


@router.put("/{task_id}/materials/{material_id}", response_model=TaskMaterialResponse)
def update_task_material(
    task_id: int,
    material_id: int,
    data: TaskMaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    material = db.query(TaskMaterialSpecification).filter(
        TaskMaterialSpecification.id == material_id,
        TaskMaterialSpecification.task_id == task_id,
    ).first()
    if not task or not material:
        raise HTTPException(status_code=404, detail="Spesifikasi material tidak ditemukan")
    ensure_task_access(current_user, task)
    changes = data.model_dump(exclude_unset=True)
    source_document_id = changes.get("source_document_id", material.source_document_id)
    _validate_material_source(db, task, source_document_id)
    before = {
        "material_name": material.material_name,
        "technical_specification": material.technical_specification,
        "revision": material.revision,
    }
    for field, value in changes.items():
        setattr(material, field, value)
    log_audit(
        db, actor_id=current_user.id, action="task.material_updated",
        entity_type="task_material", entity_id=material.id, project_id=task.project_id,
        summary=f"Spesifikasi material diperbarui: {material.material_name}",
        before=before, after=data.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{task_id}/materials/{material_id}", status_code=204)
def delete_task_material(
    task_id: int,
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    material = db.query(TaskMaterialSpecification).filter(
        TaskMaterialSpecification.id == material_id,
        TaskMaterialSpecification.task_id == task_id,
    ).first()
    if not task or not material:
        raise HTTPException(status_code=404, detail="Spesifikasi material tidak ditemukan")
    ensure_task_access(current_user, task)
    log_audit(
        db, actor_id=current_user.id, action="task.material_deleted",
        entity_type="task_material", entity_id=material.id, project_id=task.project_id,
        summary=f"Material task dihapus: {material.material_name}",
        before={"material_name": material.material_name, "material_code": material.material_code},
    )
    db.delete(material)
    db.commit()


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER))
):
    """Hapus task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)

    log_audit(
        db,
        actor_id=current_user.id,
        action="task.deleted",
        entity_type="task",
        entity_id=task.id,
        project_id=task.project_id,
        summary=f"Task dihapus: {task.title}",
        before={"title": task.title, "status": task.status.value if task.status else None},
    )
    db.query(Notification).filter(Notification.related_task_id == task.id).update(
        {Notification.related_task_id: None},
        synchronize_session=False,
    )
    db.query(CommunicationItem).filter(CommunicationItem.related_task_id == task.id).update(
        {CommunicationItem.related_task_id: None},
        synchronize_session=False,
    )
    db.query(ApprovalRequest).filter(
        ApprovalRequest.related_entity_type == "task",
        ApprovalRequest.related_entity_id == task.id,
    ).update(
        {ApprovalRequest.related_entity_id: None},
        synchronize_session=False,
    )
    db.delete(task)
    db.commit()


@router.get("/{task_id}/subtasks", response_model=List[TaskResponse])
def get_subtasks(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil semua subtask dari satu task (untuk tree view)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    ensure_task_access(current_user, task)
    return [
        item for item in db.query(Task).filter(Task.parent_task_id == task_id).all()
        if can_access_task(current_user, item)
    ]
