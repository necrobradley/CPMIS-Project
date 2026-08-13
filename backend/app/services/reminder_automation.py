from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.user import (
    Division,
    Notification,
    Project,
    ProjectMembership,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    UserRole,
)
from app.services.report_workflow import can_access_task
from app.services.project_role_catalog import (
    PROJECT_CROSS_DIVISION_ROLE_CODES,
    PROJECT_DIVISION_LEAD_ROLE_CODES,
)


ACTIONABLE_STATUSES = (
    TaskStatus.TODO,
    TaskStatus.IN_PROGRESS,
    TaskStatus.REVIEW,
    TaskStatus.BLOCKED,
)


def _unique_ids(values: Iterable[Optional[int]]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _day_start(now: datetime) -> datetime:
    return datetime(now.year, now.month, now.day)


def _deadline_label(days_remaining: int) -> str:
    if days_remaining < 0:
        return f"terlambat {abs(days_remaining)} hari"
    if days_remaining == 0:
        return "jatuh tempo hari ini"
    return f"jatuh tempo dalam {days_remaining} hari"


def _priority_label(priority: TaskPriority | str | None) -> str:
    value = priority.value if isinstance(priority, TaskPriority) else priority
    return {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
    }.get(str(value or "medium"), "Medium")


def _status_label(status: TaskStatus | str | None) -> str:
    value = status.value if isinstance(status, TaskStatus) else status
    return {
        "todo": "To do",
        "in_progress": "In progress",
        "review": "Review",
        "done": "Done",
        "blocked": "Blocked",
    }.get(str(value or "todo"), "To do")


def _classify_task(task: Task, now: datetime, horizon_days: int, include_stalled: bool) -> Optional[dict[str, Any]]:
    if task.status == TaskStatus.DONE:
        return None

    if task.deadline:
        days_remaining = (task.deadline.date() - now.date()).days
        if days_remaining < 0:
            return {
                "kind": "overdue",
                "title": "Task overdue",
                "type": "deadline",
                "severity": "critical",
                "days_remaining": days_remaining,
            }
        if days_remaining <= horizon_days:
            return {
                "kind": "due_today" if days_remaining == 0 else "due_soon",
                "title": "Pengingat deadline task",
                "type": "deadline",
                "severity": "high" if days_remaining <= 1 else "warning",
                "days_remaining": days_remaining,
            }

    if task.status == TaskStatus.BLOCKED:
        return {
            "kind": "blocked",
            "title": "Task blocked perlu tindak lanjut",
            "type": "warning",
            "severity": "high",
            "days_remaining": None,
        }

    if include_stalled and task.status == TaskStatus.IN_PROGRESS and task.updated_at:
        stale_cutoff = now - timedelta(days=3)
        if task.updated_at < stale_cutoff:
            return {
                "kind": "stalled",
                "title": "Task belum ada update",
                "type": "warning",
                "severity": "medium",
                "days_remaining": None,
            }

    return None


def _stakeholder_ids_for_task(db: Session, task: Task, kind: str) -> list[int]:
    ids: list[Optional[int]] = [task.assigned_to, task.created_by]

    project = task.project or db.query(Project).filter(Project.id == task.project_id).first()
    if project:
        ids.append(project.owner_id)

    if task.division_id:
        division = task.division or db.query(Division).filter(Division.id == task.division_id).first()
        if division:
            ids.append(division.manager_id)

    memberships = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == task.project_id,
        ProjectMembership.is_active == True,
        ProjectMembership.project_role.in_(
            list(PROJECT_CROSS_DIVISION_ROLE_CODES | PROJECT_DIVISION_LEAD_ROLE_CODES)
        ),
    ).all()
    ids.extend(item.user_id for item in memberships)

    if kind in {"overdue", "blocked"} or task.priority == TaskPriority.CRITICAL:
        managers = db.query(User).filter(
            User.is_active == True,
            User.role.in_([UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER]),
        ).all()
        ids.extend(user.id for user in managers if can_access_task(user, task))

    return _unique_ids(ids)


def _active_users_by_ids(db: Session, user_ids: Iterable[int]) -> list[User]:
    cleaned = _unique_ids(user_ids)
    if not cleaned:
        return []
    users = db.query(User).filter(
        User.id.in_(cleaned),
        User.is_active == True,
    ).all()
    order = {user_id: index for index, user_id in enumerate(cleaned)}
    return sorted(users, key=lambda user: order.get(user.id, len(order)))


def _existing_today_notification(
    db: Session,
    user_id: int,
    task_id: int,
    title: str,
    since: datetime,
) -> Optional[Notification]:
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.related_task_id == task_id,
        Notification.title == title,
        Notification.created_at >= since,
    ).order_by(Notification.created_at.desc()).first()


def _task_message(task: Task, project: Optional[Project], classification: dict[str, Any]) -> str:
    project_name = project.project_name if project else f"Proyek #{task.project_id}"
    deadline = task.deadline.strftime("%Y-%m-%d") if task.deadline else "belum ditetapkan"
    if classification["days_remaining"] is None:
        timing = "perlu update/tindak lanjut"
    else:
        timing = _deadline_label(classification["days_remaining"])
    assignee = task.assignee.name if task.assignee else "Belum ditetapkan"
    return (
        f"{task.title} pada {project_name} {timing}. "
        f"PIC: {assignee}. Deadline: {deadline}. "
        "Mohon update status, kirim laporan/evidence, atau koordinasikan blocker di CPMIS."
    )


def _telegram_text(
    notification: Notification,
    task: Task,
    project: Optional[Project],
    recipient: User,
    classification: dict[str, Any],
) -> str:
    project_name = project.project_name if project else f"Proyek #{task.project_id}"
    deadline = task.deadline.strftime("%Y-%m-%d") if task.deadline else "Belum ditetapkan"
    timing = "Perlu update" if classification["days_remaining"] is None else _deadline_label(classification["days_remaining"])
    assignee = task.assignee.name if task.assignee else "Belum ditetapkan"
    return (
        f"*{notification.title}*\n\n"
        f"Proyek: {project_name}\n"
        f"Task: {task.title}\n"
        f"PIC: {assignee}\n"
        f"Penerima: {recipient.name}\n"
        f"Status: {_status_label(task.status)}\n"
        f"Prioritas: {_priority_label(task.priority)}\n"
        f"Deadline: {deadline} ({timing})\n\n"
        "Tindak lanjut: update progress, submit laporan/evidence, atau respon blocker melalui CPMIS."
    )


def prepare_task_reminders(
    db: Session,
    horizon_days: int = 3,
    include_stalled: bool = True,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    now = now or datetime.utcnow()
    since = _day_start(now)
    tasks = db.query(Task).filter(
        Task.status.in_(ACTIONABLE_STATUSES),
    ).order_by(Task.deadline.asc().nullslast(), Task.priority.desc(), Task.id.asc()).all()

    reminders: list[dict[str, Any]] = []
    telegram_messages: list[dict[str, Any]] = []
    notifications_created = 0

    for task in tasks:
        classification = _classify_task(task, now, horizon_days, include_stalled)
        if not classification:
            continue
        project = task.project or db.query(Project).filter(Project.id == task.project_id).first()
        message = _task_message(task, project, classification)
        recipients = _active_users_by_ids(db, _stakeholder_ids_for_task(db, task, classification["kind"]))

        for recipient in recipients:
            notification = _existing_today_notification(
                db,
                recipient.id,
                task.id,
                classification["title"],
                since,
            )
            created = False
            if not notification:
                notification = Notification(
                    user_id=recipient.id,
                    title=classification["title"],
                    message=message,
                    type=classification["type"],
                    related_task_id=task.id,
                    related_project_id=task.project_id,
                    sent_to_telegram=False,
                    created_at=now,
                )
                db.add(notification)
                db.flush()
                notifications_created += 1
                created = True

            reminder = {
                "notification_id": notification.id,
                "created": created,
                "kind": classification["kind"],
                "severity": classification["severity"],
                "task_id": task.id,
                "task_title": task.title,
                "project_id": task.project_id,
                "project_name": project.project_name if project else f"Proyek #{task.project_id}",
                "user_id": recipient.id,
                "user_name": recipient.name,
                "telegram_id": recipient.telegram_id,
                "days_remaining": classification["days_remaining"],
                "sent_to_telegram": notification.sent_to_telegram,
            }
            reminders.append(reminder)

            if recipient.telegram_id and not notification.sent_to_telegram:
                telegram_messages.append({
                    **reminder,
                    "notification_ids": [notification.id],
                    "text": _telegram_text(notification, task, project, recipient, classification),
                })

    return {
        "generated_at": now.isoformat(),
        "horizon_days": horizon_days,
        "summary": {
            "tasks_scanned": len(tasks),
            "reminders": len(reminders),
            "notifications_created": notifications_created,
            "telegram_messages": len(telegram_messages),
        },
        "reminders": reminders,
        "telegram_messages": telegram_messages,
    }


def mark_reminder_telegram_delivered(db: Session, notification_ids: Iterable[int]) -> int:
    ids = _unique_ids(notification_ids)
    if not ids:
        return 0
    updated = db.query(Notification).filter(
        Notification.id.in_(ids),
    ).update({"sent_to_telegram": True}, synchronize_session=False)
    return int(updated or 0)
