from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.user import (
    CommunicationItem,
    CommunicationLink,
    CommunicationMention,
    CommunicationMessage,
    CommunicationReadReceipt,
    CommunicationStatus,
    CommunicationType,
    Notification,
    Project,
    TaskPriority,
    User,
)


OPEN_COMMUNICATION_STATUSES = (
    CommunicationStatus.OPEN,
    CommunicationStatus.IN_REVIEW,
)


def _clean_user_ids(user_ids: Iterable[int] | None) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for user_id in user_ids or []:
        if user_id and user_id not in seen:
            result.append(user_id)
            seen.add(user_id)
    return result


def _notify(
    db: Session,
    user_id: Optional[int],
    title: str,
    message: str,
    communication: CommunicationItem,
    actor_id: Optional[int] = None,
    notification_type: str = "communication",
) -> None:
    if not user_id or user_id == actor_id:
        return
    db.add(Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        related_task_id=communication.related_task_id,
        related_project_id=communication.project_id,
        sent_to_telegram=False,
    ))


def communication_participants(db: Session, communication: CommunicationItem) -> set[int]:
    user_ids = {communication.created_by}
    if communication.assigned_to:
        user_ids.add(communication.assigned_to)
    message_user_ids = db.query(CommunicationMessage.user_id).filter(
        CommunicationMessage.communication_id == communication.id,
        CommunicationMessage.user_id.isnot(None),
    ).all()
    user_ids.update(row[0] for row in message_user_ids if row[0])
    mention_user_ids = db.query(CommunicationMention.mentioned_user_id).filter(
        CommunicationMention.communication_id == communication.id,
    ).all()
    user_ids.update(row[0] for row in mention_user_ids if row[0])
    return user_ids


def mark_communication_read(db: Session, communication: CommunicationItem, user_id: int) -> CommunicationReadReceipt:
    now = datetime.utcnow()
    receipt = db.query(CommunicationReadReceipt).filter(
        CommunicationReadReceipt.communication_id == communication.id,
        CommunicationReadReceipt.user_id == user_id,
    ).first()
    if not receipt:
        receipt = CommunicationReadReceipt(
            communication_id=communication.id,
            user_id=user_id,
            last_read_at=now,
        )
        db.add(receipt)
    else:
        receipt.last_read_at = now
        receipt.updated_at = now

    db.query(CommunicationMention).filter(
        CommunicationMention.communication_id == communication.id,
        CommunicationMention.mentioned_user_id == user_id,
        CommunicationMention.is_read == False,
    ).update({"is_read": True, "read_at": now}, synchronize_session=False)
    return receipt


def add_communication_message(
    db: Session,
    communication: CommunicationItem,
    message: str,
    actor_id: Optional[int],
    message_type: str = "comment",
    mention_user_ids: Iterable[int] | None = None,
    telegram_message_id: Optional[str] = None,
    notify_participants: bool = True,
) -> CommunicationMessage:
    now = datetime.utcnow()
    thread_message = CommunicationMessage(
        communication_id=communication.id,
        user_id=actor_id,
        message_type=message_type,
        message=message.strip(),
        telegram_message_id=telegram_message_id,
        created_at=now,
    )
    db.add(thread_message)
    db.flush()

    mentions = _clean_user_ids(mention_user_ids)
    valid_mentions = db.query(User).filter(
        User.id.in_(mentions),
        User.is_active == True,
    ).all() if mentions else []
    for user in valid_mentions:
        db.add(CommunicationMention(
            communication_id=communication.id,
            message_id=thread_message.id,
            mentioned_user_id=user.id,
            created_by=actor_id or communication.created_by,
        ))
        _notify(
            db,
            user.id,
            "Anda di-mention",
            f"Anda di-mention pada '{communication.subject}'.",
            communication,
            actor_id,
            "mention",
        )

    if message_type == "response":
        communication.response = message.strip()
        communication.status = CommunicationStatus.ANSWERED
        communication.answered_at = communication.answered_at or now
    elif communication.status == CommunicationStatus.DRAFT:
        communication.status = CommunicationStatus.OPEN

    communication.updated_at = now

    if actor_id:
        mark_communication_read(db, communication, actor_id)

    if notify_participants:
        participant_ids = communication_participants(db, communication)
        participant_ids.update([communication.created_by, communication.assigned_to])
        participant_ids.difference_update({None, actor_id})
        participant_ids.difference_update({user.id for user in valid_mentions})
        for user_id in participant_ids:
            _notify(
                db,
                user_id,
                "Update komunikasi",
                f"Ada update pada '{communication.subject}'.",
                communication,
                actor_id,
            )

    return thread_message


def ensure_communication_from_source(
    db: Session,
    source_type: str,
    source_id: int,
    project_id: int,
    created_by: int,
    subject: str,
    description: Optional[str] = None,
    communication_type: CommunicationType = CommunicationType.ISSUE,
    priority: TaskPriority = TaskPriority.HIGH,
    assigned_to: Optional[int] = None,
    related_task_id: Optional[int] = None,
    related_document_id: Optional[int] = None,
    discipline: Optional[str] = None,
    location: Optional[str] = None,
    due_date: Optional[datetime] = None,
    system_message: Optional[str] = None,
) -> CommunicationItem:
    existing_link = db.query(CommunicationLink).filter(
        CommunicationLink.source_type == source_type,
        CommunicationLink.source_id == source_id,
    ).first()
    if existing_link:
        return existing_link.communication

    communication = CommunicationItem(
        project_id=project_id,
        created_by=created_by,
        assigned_to=assigned_to,
        communication_type=communication_type,
        status=CommunicationStatus.OPEN,
        priority=priority,
        subject=subject,
        description=description,
        discipline=discipline,
        location=location,
        related_task_id=related_task_id,
        related_document_id=related_document_id,
        due_date=due_date,
    )
    db.add(communication)
    db.flush()
    db.add(CommunicationLink(
        communication_id=communication.id,
        source_type=source_type,
        source_id=source_id,
        label=subject,
    ))
    add_communication_message(
        db,
        communication,
        system_message or description or subject,
        actor_id=created_by,
        message_type="system",
        notify_participants=True,
    )
    _notify(
        db,
        assigned_to,
        "Item komunikasi otomatis",
        f"Sistem membuat item '{subject}' dan menugaskannya kepada Anda.",
        communication,
        created_by,
    )
    return communication


def run_sla_escalations(db: Session) -> int:
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)
    overdue_items = db.query(CommunicationItem).filter(
        CommunicationItem.status.in_(OPEN_COMMUNICATION_STATUSES),
        CommunicationItem.due_date.isnot(None),
        CommunicationItem.due_date < now,
    ).all()
    escalated = 0
    for item in overdue_items:
        recent_escalation = db.query(CommunicationMessage).filter(
            CommunicationMessage.communication_id == item.id,
            CommunicationMessage.message_type == "auto_escalation",
            CommunicationMessage.created_at >= cutoff,
        ).first()
        if recent_escalation:
            continue
        item.priority = TaskPriority.CRITICAL
        project = db.query(Project).filter(Project.id == item.project_id).first()
        owner_id = project.owner_id if project else None
        add_communication_message(
            db,
            item,
            "SLA komunikasi terlewati. Item otomatis dinaikkan menjadi critical dan perlu keputusan/tindak lanjut.",
            actor_id=None,
            message_type="auto_escalation",
            notify_participants=True,
        )
        _notify(
            db,
            item.assigned_to,
            "SLA komunikasi overdue",
            f"'{item.subject}' sudah melewati due date.",
            item,
            None,
            "escalation",
        )
        _notify(
            db,
            owner_id,
            "SLA komunikasi overdue",
            f"'{item.subject}' sudah melewati due date dan dinaikkan menjadi critical.",
            item,
            None,
            "escalation",
        )
        escalated += 1
    return escalated
