from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import (
    CommunicationItem,
    CommunicationMention,
    CommunicationMessage,
    CommunicationStatus,
    CommunicationType,
    Notification,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    User,
    UserRole,
)
from app.services.communication_service import (
    add_communication_message,
    ensure_communication_from_source,
    mark_communication_read,
    run_sla_escalations,
)


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        name="Manager Communication", email="manager-communication@test.local",
        password_hash="x", role=UserRole.MANAGER,
    )
    staff = User(
        name="Staff Communication", email="staff-communication@test.local",
        password_hash="x", role=UserRole.STAFF,
    )
    db.add_all([manager, staff])
    db.flush()
    project = Project(
        project_name="Communication Test", status=ProjectStatus.ACTIVE,
        owner_id=manager.id,
    )
    db.add(project)
    db.flush()
    task = Task(
        title="QA task", project_id=project.id, created_by=manager.id,
        assigned_to=staff.id,
    )
    db.add(task)
    db.flush()
    item = CommunicationItem(
        project_id=project.id,
        created_by=staff.id,
        assigned_to=manager.id,
        communication_type=CommunicationType.ISSUE,
        status=CommunicationStatus.OPEN,
        priority=TaskPriority.HIGH,
        subject="Communication QA",
        related_task_id=task.id,
        due_date=datetime.utcnow() + timedelta(days=1),
    )
    db.add(item)
    db.commit()
    return db, manager, staff, project, task, item


def test_thread_mentions_notifications_and_read_receipt():
    db, manager, staff, _, _, item = build_database()

    message = add_communication_message(
        db,
        item,
        "Manager response with mention.",
        actor_id=manager.id,
        message_type="response",
        mention_user_ids=[staff.id],
    )
    db.commit()

    mention = db.query(CommunicationMention).filter(
        CommunicationMention.message_id == message.id,
        CommunicationMention.mentioned_user_id == staff.id,
    ).first()
    notification = db.query(Notification).filter(
        Notification.user_id == staff.id,
        Notification.type == "mention",
    ).first()

    assert message.message_type == "response"
    assert item.status == CommunicationStatus.ANSWERED
    assert mention is not None
    assert mention.is_read is False
    assert notification is not None

    receipt = mark_communication_read(db, item, staff.id)
    db.commit()
    db.refresh(mention)

    assert receipt.user_id == staff.id
    assert mention.is_read is True
    assert mention.read_at is not None


def test_auto_source_is_idempotent_and_sla_escalates_overdue():
    db, manager, staff, project, task, _ = build_database()

    item = ensure_communication_from_source(
        db,
        source_type="ncr",
        source_id=501,
        project_id=project.id,
        created_by=manager.id,
        subject="NCR auto communication",
        description="NCR needs corrective action.",
        communication_type=CommunicationType.ISSUE,
        priority=TaskPriority.HIGH,
        assigned_to=staff.id,
        related_task_id=task.id,
        due_date=datetime.utcnow() - timedelta(days=1),
    )
    duplicate = ensure_communication_from_source(
        db,
        source_type="ncr",
        source_id=501,
        project_id=project.id,
        created_by=manager.id,
        subject="NCR auto communication duplicate",
    )
    db.commit()

    escalated = run_sla_escalations(db)
    db.commit()
    auto_message = db.query(CommunicationMessage).filter(
        CommunicationMessage.communication_id == item.id,
        CommunicationMessage.message_type == "auto_escalation",
    ).first()

    assert duplicate.id == item.id
    assert escalated == 1
    assert item.priority == TaskPriority.CRITICAL
    assert auto_message is not None
