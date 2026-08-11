from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import (
    Notification,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    UserRole,
)
from app.services.reminder_automation import (
    mark_reminder_telegram_delivered,
    prepare_task_reminders,
)


def build_database(now: datetime):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    manager = User(
        name="Reminder Manager",
        email="manager-reminder@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
        telegram_id="1001",
    )
    staff = User(
        name="Reminder Staff",
        email="staff-reminder@test.local",
        password_hash="x",
        role=UserRole.STAFF,
        telegram_id="1002",
    )
    db.add_all([manager, staff])
    db.flush()

    project = Project(
        project_name="Reminder Project",
        status=ProjectStatus.ACTIVE,
        owner_id=manager.id,
    )
    db.add(project)
    db.flush()

    task = Task(
        title="Install formwork zone A",
        project_id=project.id,
        assigned_to=staff.id,
        created_by=manager.id,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
        deadline=now + timedelta(days=2),
        updated_at=now,
    )
    db.add(task)
    db.commit()
    return db, manager, staff, task


def test_prepare_reminders_creates_in_app_notifications_and_telegram_payloads_once_per_day():
    now = datetime(2026, 6, 24, 1, 0, 0)
    db, manager, staff, task = build_database(now)

    first = prepare_task_reminders(db, now=now)
    db.commit()

    notifications = db.query(Notification).filter(Notification.related_task_id == task.id).all()
    assert first["summary"]["notifications_created"] == 2
    assert len(notifications) == 2
    assert {item.user_id for item in notifications} == {manager.id, staff.id}
    assert first["summary"]["telegram_messages"] == 2

    second = prepare_task_reminders(db, now=now + timedelta(hours=1))
    db.commit()

    assert second["summary"]["notifications_created"] == 0
    assert db.query(Notification).filter(Notification.related_task_id == task.id).count() == 2
    assert second["summary"]["telegram_messages"] == 2

    delivered_ids = [message["notification_id"] for message in second["telegram_messages"]]
    updated = mark_reminder_telegram_delivered(db, delivered_ids)
    db.commit()

    assert updated == 2
    assert db.query(Notification).filter(
        Notification.related_task_id == task.id,
        Notification.sent_to_telegram == True,
    ).count() == 2

    third = prepare_task_reminders(db, now=now + timedelta(hours=2))
    assert third["summary"]["notifications_created"] == 0
    assert third["summary"]["telegram_messages"] == 0
