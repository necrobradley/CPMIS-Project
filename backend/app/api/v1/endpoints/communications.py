import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import (
    CommunicationAttachment,
    CommunicationItem,
    CommunicationMention,
    CommunicationMessage,
    CommunicationReadReceipt,
    CommunicationStatus,
    CommunicationType,
    Notification,
    Project,
    ProjectMembership,
    Task,
    TaskPriority,
    User,
    UserRole,
)
from app.schemas.schemas import (
    CommunicationAttachmentResponse,
    CommunicationCreate,
    CommunicationDetailResponse,
    CommunicationEscalateRequest,
    CommunicationMessageCreate,
    CommunicationMessageResponse,
    CommunicationReadReceiptResponse,
    CommunicationResponse,
    CommunicationUpdate,
)
from app.services.audit_service import log_audit
from app.services.communication_service import (
    add_communication_message,
    communication_participants,
    mark_communication_read,
    run_sla_escalations,
)
from app.services.report_workflow import (
    can_access_project,
    can_access_task,
    ensure_project_access,
    ensure_task_access,
)
from app.services.project_role_catalog import is_cross_division_project_role
from app.services.storage_service import storage_service

router = APIRouter(prefix="/communications", tags=["Communications"])

ALLOWED_ATTACHMENT_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024
MANAGEMENT_ROLES = {UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER}


def _get_item(db: Session, communication_id: int) -> CommunicationItem:
    item = db.query(CommunicationItem).filter(CommunicationItem.id == communication_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Communication item tidak ditemukan")
    return item


def _can_access(item: CommunicationItem, current_user: User, db: Session) -> bool:
    if current_user.role == UserRole.DIRECTOR:
        return True
    if current_user.role in (UserRole.ADMIN, UserRole.MANAGER):
        return can_access_project(current_user, item.project)
    if item.created_by == current_user.id or item.assigned_to == current_user.id:
        return True
    project_wide_membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == item.project_id,
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.is_active == True,
    ).first()
    if project_wide_membership and is_cross_division_project_role(project_wide_membership.project_role):
        return True
    if item.related_task and can_access_task(current_user, item.related_task):
        return True
    mentioned = db.query(CommunicationMention.id).filter(
        CommunicationMention.communication_id == item.id,
        CommunicationMention.mentioned_user_id == current_user.id,
    ).first()
    if mentioned:
        return True
    participant = db.query(CommunicationMessage.id).filter(
        CommunicationMessage.communication_id == item.id,
        CommunicationMessage.user_id == current_user.id,
    ).first()
    return bool(participant)


def _ensure_access(item: CommunicationItem, current_user: User, db: Session) -> None:
    if not _can_access(item, current_user, db):
        raise HTTPException(status_code=403, detail="Akses communication ditolak")


def _is_mine(item: CommunicationItem, current_user: User, db: Session) -> bool:
    if item.created_by == current_user.id or item.assigned_to == current_user.id:
        return True
    return current_user.id in communication_participants(db, item)


def _validate_related_task(db: Session, project_id: int, task_id: Optional[int], current_user: User) -> None:
    if not task_id:
        return
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task terkait tidak ditemukan")
    if task.project_id != project_id:
        raise HTTPException(status_code=400, detail="Task terkait tidak berasal dari proyek komunikasi")
    ensure_task_access(current_user, task)


def _validate_project_assignee(db: Session, project_id: int, assigned_to: Optional[int]) -> None:
    if not assigned_to:
        return
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == assigned_to,
        ProjectMembership.is_active == True,
    ).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Ball-in-court harus anggota aktif proyek")


def _attachment_payload(attachment: CommunicationAttachment, include_url: bool = False) -> dict:
    payload = {
        "id": attachment.id,
        "communication_id": attachment.communication_id,
        "message_id": attachment.message_id,
        "document_id": attachment.document_id,
        "uploaded_by": attachment.uploaded_by,
        "file_name": attachment.file_name,
        "file_size": attachment.file_size,
        "mime_type": attachment.mime_type,
        "caption": attachment.caption,
        "created_at": attachment.created_at,
        "download_url": None,
    }
    if include_url:
        try:
            payload["download_url"] = storage_service.get_signed_url(attachment.file_path)
        except Exception:
            payload["download_url"] = None
    return payload


def _message_payload(message: CommunicationMessage) -> dict:
    return {
        "id": message.id,
        "communication_id": message.communication_id,
        "user_id": message.user_id,
        "message_type": message.message_type,
        "message": message.message,
        "telegram_message_id": message.telegram_message_id,
        "created_at": message.created_at,
        "mentions": message.mentions,
        "attachments": [_attachment_payload(item, include_url=True) for item in message.attachments],
    }


def _item_payload(
    db: Session,
    item: CommunicationItem,
    current_user: User,
    include_detail: bool = False,
) -> dict:
    receipt = db.query(CommunicationReadReceipt).filter(
        CommunicationReadReceipt.communication_id == item.id,
        CommunicationReadReceipt.user_id == current_user.id,
    ).first()
    last_read_at = receipt.last_read_at if receipt else None
    unread_query = db.query(CommunicationMessage).filter(
        CommunicationMessage.communication_id == item.id,
        CommunicationMessage.user_id != current_user.id,
    )
    if last_read_at:
        unread_query = unread_query.filter(CommunicationMessage.created_at > last_read_at)
    unread_count = unread_query.count()
    mention_count = db.query(CommunicationMention).filter(
        CommunicationMention.communication_id == item.id,
        CommunicationMention.mentioned_user_id == current_user.id,
        CommunicationMention.is_read == False,
    ).count()
    last_activity_at = item.updated_at
    if item.messages:
        last_activity_at = max(last_activity_at, max(message.created_at for message in item.messages))
    if item.attachments:
        last_activity_at = max(last_activity_at, max(attachment.created_at for attachment in item.attachments))

    payload = {
        "id": item.id,
        "project_id": item.project_id,
        "created_by": item.created_by,
        "assigned_to": item.assigned_to,
        "communication_type": item.communication_type,
        "status": item.status,
        "priority": item.priority,
        "subject": item.subject,
        "description": item.description,
        "question": item.question,
        "response": item.response,
        "discipline": item.discipline,
        "location": item.location,
        "related_task_id": item.related_task_id,
        "related_document_id": item.related_document_id,
        "due_date": item.due_date,
        "answered_at": item.answered_at,
        "closed_at": item.closed_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "thread_count": len(item.messages),
        "attachment_count": len(item.attachments),
        "unread_count": unread_count,
        "mention_count": mention_count,
        "last_activity_at": last_activity_at,
        "last_read_at": last_read_at,
    }
    if include_detail:
        payload.update({
            "messages": [_message_payload(message) for message in item.messages],
            "attachments": [_attachment_payload(attachment, include_url=True) for attachment in item.attachments],
            "mentions": item.mentions,
            "read_receipts": item.read_receipts,
            "links": item.links,
        })
    return payload


@router.get("", response_model=List[CommunicationResponse])
def list_communications(
    project_id: Optional[int] = Query(None),
    communication_type: Optional[CommunicationType] = Query(None),
    status: Optional[CommunicationStatus] = Query(None),
    assigned_to: Optional[int] = Query(None),
    mine: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CommunicationItem)

    if project_id:
        query = query.filter(CommunicationItem.project_id == project_id)
    if communication_type:
        query = query.filter(CommunicationItem.communication_type == communication_type)
    if status:
        query = query.filter(CommunicationItem.status == status)
    if assigned_to:
        query = query.filter(CommunicationItem.assigned_to == assigned_to)

    items = query.order_by(
        CommunicationItem.due_date.asc().nullslast(),
        CommunicationItem.updated_at.desc(),
        CommunicationItem.created_at.desc(),
    ).all()
    visible = [item for item in items if _can_access(item, current_user, db)]
    if mine:
        visible = [item for item in visible if _is_mine(item, current_user, db)]
    return [_item_payload(db, item, current_user) for item in visible]


@router.post("/sla/escalate-overdue")
def escalate_overdue_communications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project_ids = None
    if current_user.role != UserRole.DIRECTOR:
        project_ids = {
            project.id for project in db.query(Project).all()
            if can_access_project(current_user, project)
        }
    escalated = run_sla_escalations(db, project_ids=project_ids)
    log_audit(
        db,
        actor_id=current_user.id,
        action="communication.sla_escalated",
        entity_type="communication",
        entity_id=None,
        project_id=next(iter(project_ids)) if project_ids and len(project_ids) == 1 else None,
        summary=f"SLA escalation dijalankan untuk {escalated} item",
        after={"escalated": escalated},
    )
    db.commit()
    return {"escalated": escalated}


@router.get("/attachments/{attachment_id}/download-url")
def get_attachment_download_url(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = db.query(CommunicationAttachment).filter(
        CommunicationAttachment.id == attachment_id,
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment tidak ditemukan")
    _ensure_access(attachment.communication, current_user, db)
    return {"url": storage_service.get_signed_url(attachment.file_path)}


@router.get("/{communication_id}", response_model=CommunicationDetailResponse)
def get_communication(
    communication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item(db, communication_id)
    _ensure_access(item, current_user, db)
    mark_communication_read(db, item, current_user.id)
    db.commit()
    db.refresh(item)
    return _item_payload(db, item, current_user, include_detail=True)


@router.post("", response_model=CommunicationResponse, status_code=201)
def create_communication(
    data: CommunicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR) and not data.related_task_id:
        raise HTTPException(status_code=400, detail="Komunikasi staff wajib terkait task yang dapat diakses")
    _validate_related_task(db, data.project_id, data.related_task_id, current_user)
    _validate_project_assignee(db, data.project_id, data.assigned_to)

    item = CommunicationItem(
        **data.model_dump(),
        created_by=current_user.id,
        status=CommunicationStatus.ANSWERED if data.response else CommunicationStatus.OPEN,
        answered_at=datetime.utcnow() if data.response else None,
    )
    db.add(item)
    db.flush()

    initial_text = data.question or data.description or f"Item komunikasi dibuat: {data.subject}"
    add_communication_message(
        db,
        item,
        initial_text,
        actor_id=current_user.id,
        message_type="system",
        notify_participants=False,
    )
    if data.response:
        add_communication_message(
            db,
            item,
            data.response,
            actor_id=current_user.id,
            message_type="response",
            notify_participants=True,
        )

    if item.assigned_to:
        db.add(Notification(
            user_id=item.assigned_to,
            title="Communication item baru",
            message=f"{current_user.name} membuat {item.communication_type.value}: {item.subject}",
            type="communication",
            related_task_id=item.related_task_id,
            related_project_id=item.project_id,
            sent_to_telegram=False,
        ))

    log_audit(
        db,
        actor_id=current_user.id,
        action="communication.created",
        entity_type="communication",
        entity_id=item.id,
        project_id=item.project_id,
        summary=f"Communication dibuat: {item.subject}",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(item)
    return _item_payload(db, item, current_user)


@router.patch("/{communication_id}", response_model=CommunicationResponse)
def update_communication(
    communication_id: int,
    data: CommunicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item(db, communication_id)
    _ensure_access(item, current_user, db)
    if data.related_task_id is not None:
        _validate_related_task(db, item.project_id, data.related_task_id, current_user)
    if data.assigned_to is not None:
        _validate_project_assignee(db, item.project_id, data.assigned_to)

    before = {
        "status": item.status.value if item.status else None,
        "assigned_to": item.assigned_to,
        "response": item.response,
        "due_date": item.due_date,
    }
    changes = data.model_dump(exclude_unset=True)
    if current_user.role not in MANAGEMENT_ROLES:
        allowed_staff_fields = {"response"}
        blocked_fields = set(changes) - allowed_staff_fields
        if blocked_fields:
            raise HTTPException(
                status_code=403,
                detail="Staff hanya dapat membalas, upload evidence, atau eskalasi item komunikasi",
            )
    response_text = changes.pop("response", None)

    for field, value in changes.items():
        setattr(item, field, value)

    if response_text:
        add_communication_message(
            db,
            item,
            response_text,
            actor_id=current_user.id,
            message_type="response",
            notify_participants=True,
        )

    if "status" in changes and changes["status"] == CommunicationStatus.CLOSED:
        item.closed_at = item.closed_at or datetime.utcnow()
        add_communication_message(
            db,
            item,
            "Item komunikasi ditutup.",
            actor_id=current_user.id,
            message_type="status_update",
            notify_participants=True,
        )
    elif "status" in changes:
        add_communication_message(
            db,
            item,
            f"Status komunikasi diubah menjadi {item.status.value}.",
            actor_id=current_user.id,
            message_type="status_update",
            notify_participants=True,
        )

    if item.assigned_to and "assigned_to" in changes:
        db.add(Notification(
            user_id=item.assigned_to,
            title="Ball-in-court dipindahkan",
            message=f"PIC communication '{item.subject}' dipindahkan ke Anda.",
            type="communication",
            related_task_id=item.related_task_id,
            related_project_id=item.project_id,
            sent_to_telegram=False,
        ))

    item.updated_at = datetime.utcnow()
    mark_communication_read(db, item, current_user.id)
    log_audit(
        db,
        actor_id=current_user.id,
        action="communication.updated",
        entity_type="communication",
        entity_id=item.id,
        project_id=item.project_id,
        summary=f"Communication diupdate: {item.subject}",
        before=before,
        after=data.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(item)
    return _item_payload(db, item, current_user)


@router.post("/{communication_id}/messages", response_model=CommunicationMessageResponse, status_code=201)
def create_message(
    communication_id: int,
    data: CommunicationMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item(db, communication_id)
    _ensure_access(item, current_user, db)
    message = add_communication_message(
        db,
        item,
        data.message,
        actor_id=current_user.id,
        message_type=data.message_type,
        mention_user_ids=data.mention_user_ids,
        notify_participants=True,
    )
    log_audit(
        db,
        actor_id=current_user.id,
        action="communication.message_added",
        entity_type="communication_message",
        entity_id=message.id,
        project_id=item.project_id,
        summary=f"Pesan ditambahkan pada: {item.subject}",
        after={"message_type": data.message_type, "mention_user_ids": data.mention_user_ids},
    )
    db.commit()
    db.refresh(message)
    return _message_payload(message)


@router.post("/{communication_id}/attachments", response_model=CommunicationAttachmentResponse, status_code=201)
async def upload_attachment(
    communication_id: int,
    caption: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item(db, communication_id)
    _ensure_access(item, current_user, db)
    if file.content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipe file tidak didukung: {file.content_type}")
    content = await file.read()
    if len(content) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=400, detail="File terlalu besar (maks 25MB)")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    object_name = f"projects/{item.project_id}/communications/{item.id}/{uuid.uuid4()}.{ext}"
    try:
        storage_service.upload_file(content, object_name, file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload attachment gagal: {exc}")

    message = add_communication_message(
        db,
        item,
        caption or f"Attachment diunggah: {file.filename}",
        actor_id=current_user.id,
        message_type="attachment",
        notify_participants=True,
    )
    attachment = CommunicationAttachment(
        communication_id=item.id,
        message_id=message.id,
        uploaded_by=current_user.id,
        file_name=file.filename or object_name,
        file_path=object_name,
        file_size=len(content),
        mime_type=file.content_type,
        caption=caption,
    )
    db.add(attachment)
    log_audit(
        db,
        actor_id=current_user.id,
        action="communication.attachment_uploaded",
        entity_type="communication_attachment",
        entity_id=None,
        project_id=item.project_id,
        summary=f"Attachment komunikasi diupload: {file.filename}",
        after={"communication_id": item.id, "file_name": file.filename, "size": len(content)},
    )
    db.commit()
    db.refresh(attachment)
    return _attachment_payload(attachment, include_url=True)


@router.post("/{communication_id}/read", response_model=CommunicationReadReceiptResponse)
def mark_read(
    communication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item(db, communication_id)
    _ensure_access(item, current_user, db)
    receipt = mark_communication_read(db, item, current_user.id)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/{communication_id}/escalate", response_model=CommunicationDetailResponse)
def escalate_communication(
    communication_id: int,
    data: CommunicationEscalateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item(db, communication_id)
    _ensure_access(item, current_user, db)
    if data.assigned_to:
        if current_user.role not in MANAGEMENT_ROLES and data.assigned_to != item.assigned_to:
            raise HTTPException(status_code=403, detail="Staff tidak dapat memindahkan PIC eskalasi")
        _validate_project_assignee(db, item.project_id, data.assigned_to)
        assignee = db.query(User).filter(User.id == data.assigned_to, User.is_active == True).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="User tujuan eskalasi tidak ditemukan")
        item.assigned_to = assignee.id
    if data.due_date:
        item.due_date = data.due_date
    item.priority = TaskPriority.CRITICAL
    if item.status == CommunicationStatus.CLOSED:
        item.status = CommunicationStatus.OPEN
        item.closed_at = None
    add_communication_message(
        db,
        item,
        data.reason,
        actor_id=current_user.id,
        message_type="manual_escalation",
        mention_user_ids=[data.assigned_to] if data.assigned_to else [],
        notify_participants=True,
    )
    log_audit(
        db,
        actor_id=current_user.id,
        action="communication.escalated",
        entity_type="communication",
        entity_id=item.id,
        project_id=item.project_id,
        summary=f"Communication dieskalasikan: {item.subject}",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(item)
    return _item_payload(db, item, current_user, include_detail=True)
