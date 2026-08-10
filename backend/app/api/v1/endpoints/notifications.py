"""
Notifications Endpoint - AI CPMIS
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.user import User, Notification
from app.core.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    notifications = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id, "title": n.title, "message": n.message,
            "type": n.type, "is_read": n.is_read,
            "related_task_id": n.related_task_id,
            "related_project_id": n.related_project_id,
            "sent_to_telegram": n.sent_to_telegram,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).count()
    return {"count": count}


@router.patch("/{notif_id}/read")
def mark_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.id,
    ).first()
    if n:
        n.is_read = True
        db.commit()
    return {"success": True}


@router.patch("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"success": True}
