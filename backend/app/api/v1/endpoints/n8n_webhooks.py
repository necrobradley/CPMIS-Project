"""
N8N Webhook Receiver Endpoints - AI CPMIS
N8N memanggil endpoint ini setelah memproses workflow.
Backend menerima hasil dari N8N dan menyimpan ke DB.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging

from app.db.database import get_db
from app.models.user import User, Task, DailyReport, Notification, Project
from app.core.config import settings
from app.services.reminder_automation import (
    mark_reminder_telegram_delivered,
    prepare_task_reminders,
)
from app.services.telegram_service import create_bot_app

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/n8n", tags=["N8N Webhooks"])

# Secret key untuk validasi request dari N8N
N8N_SECRET = settings.N8N_WEBHOOK_SECRET


def verify_n8n_secret(x_n8n_secret: Optional[str] = Header(None)):
    """Validasi bahwa request berasal dari N8N yang sah."""
    if N8N_SECRET and x_n8n_secret != N8N_SECRET:
        raise HTTPException(status_code=403, detail="Invalid N8N secret")


def _payload_ids(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
            raw_values = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            raw_values = [item.strip() for item in value.split(",")]
    else:
        raw_values = [value]

    ids: list[int] = []
    for item in raw_values:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _payload_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _payload_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ─── Workflow 1 Result: Daily Report Processed ───────────────────
@router.post("/daily-report/processed", dependencies=[Depends(verify_n8n_secret)])
async def receive_daily_report_processed(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    N8N memanggil endpoint ini setelah:
    1. AI analysis selesai
    2. Notifikasi sudah dikirim ke manager via Telegram
    Endpoint ini menyimpan status dan membuat notifikasi di DB.
    """
    report_id   = payload.get("report_id")
    ai_summary  = payload.get("ai_summary")
    ai_risks    = payload.get("ai_risks")
    severity    = payload.get("severity", "low")
    sent_to     = payload.get("sent_to", [])  # list telegram_id yang sudah dikirimi

    if not report_id:
        raise HTTPException(status_code=400, detail="report_id wajib diisi")

    # Update AI summary di laporan
    report = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if report:
        if ai_summary:  report.ai_summary = ai_summary
        if ai_risks:    report.ai_risks   = ai_risks

    # Buat notifikasi untuk manager/director
    if severity in ("high", "critical"):
        managers = db.query(User).filter(
            User.role.in_(["manager", "director", "admin"]),
            User.is_active == True
        ).all()
        for mgr in managers:
            notif = Notification(
                user_id=mgr.id,
                title=f"🚨 Laporan Risiko {severity.upper()}",
                message=f"Laporan #{report_id} mendeteksi risiko: {ai_risks or 'Lihat laporan'}",
                type="alert" if severity == "critical" else "warning",
                related_project_id=report.project_id if report else None,
                sent_to_telegram=len(sent_to) > 0,
            )
            db.add(notif)

    db.commit()
    logger.info(f"N8N daily report processed: report_id={report_id}, severity={severity}")
    return {"status": "ok", "report_id": report_id}


# ─── Workflow 2 Result: Tender Analyzed ──────────────────────────
@router.post("/tender/analyzed", dependencies=[Depends(verify_n8n_secret)])
async def receive_tender_analyzed(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    N8N memanggil ini setelah tender berhasil dianalisis dan
    notifikasi sudah dikirim ke manager.
    """
    document_id        = payload.get("document_id")
    project_id         = payload.get("project_id")
    generated_tasks    = payload.get("generated_tasks", 0)
    notification_sent  = payload.get("notification_sent", False)

    # Buat notifikasi di DB
    if project_id and generated_tasks > 0:
        managers = db.query(User).filter(
            User.role.in_(["manager", "director"]),
            User.is_active == True
        ).all()
        for mgr in managers:
            notif = Notification(
                user_id=mgr.id,
                title="📄 Tender Berhasil Dianalisis",
                message=f"{generated_tasks} task berhasil digenerate dari dokumen tender (dokumen #{document_id}).",
                type="info",
                related_project_id=project_id,
                sent_to_telegram=notification_sent,
            )
            db.add(notif)
        db.commit()

    logger.info(f"N8N tender analyzed: doc_id={document_id}, tasks={generated_tasks}")
    return {"status": "ok", "document_id": document_id}


# ─── Workflow 3 Result: Deadline Alert Sent ──────────────────────
@router.post("/deadline/alerted", dependencies=[Depends(verify_n8n_secret)])
async def receive_deadline_alerted(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    N8N memanggil ini setelah mengirim deadline reminder ke user.
    Simpan record notifikasi ke DB.
    """
    task_id    = payload.get("task_id")
    user_id    = payload.get("user_id")
    sent_at    = payload.get("sent_at")

    if task_id and user_id:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            notif = Notification(
                user_id=user_id,
                title="⏰ Pengingat Deadline",
                message=f"Task '{task.title}' mendekati deadline. Segera selesaikan.",
                type="deadline",
                related_task_id=task_id,
                related_project_id=task.project_id,
                sent_to_telegram=True,
            )
            db.add(notif)
            db.commit()

    return {"status": "ok"}


@router.post("/reminders/prepare", dependencies=[Depends(verify_n8n_secret)])
async def prepare_stakeholder_reminders(
    payload: dict | None = None,
    db: Session = Depends(get_db),
):
    """
    N8N schedule memanggil endpoint ini untuk menyusun reminder resmi.
    Backend menentukan task, stakeholder, website notification, dan payload Telegram.
    """
    payload = payload or {}
    horizon_days = _payload_int(payload.get("horizon_days"), 3)
    include_stalled = _payload_bool(payload.get("include_stalled"), True)

    result = prepare_task_reminders(
        db,
        horizon_days=max(0, min(horizon_days, 14)),
        include_stalled=include_stalled,
    )
    db.commit()
    return result


@router.post("/reminders/delivered", dependencies=[Depends(verify_n8n_secret)])
async def receive_reminder_delivered(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    N8N memanggil endpoint ini setelah Telegram reminder dikirim.
    Website notification sudah dibuat saat prepare; callback ini menandai channel Telegram.
    """
    notification_ids = _payload_ids(payload.get("notification_ids"))
    updated = mark_reminder_telegram_delivered(db, notification_ids)
    db.commit()
    return {
        "status": "ok",
        "updated": updated,
        "notification_ids": notification_ids,
    }


# ─── Workflow 5 Result: Weekly Summary Sent ──────────────────────
@router.post("/weekly-summary/sent", dependencies=[Depends(verify_n8n_secret)])
async def receive_weekly_summary_sent(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    N8N memanggil ini setelah weekly summary berhasil dikirim.
    """
    project_id = payload.get("project_id")
    sent_to    = payload.get("sent_to", [])

    logger.info(f"N8N weekly summary sent: project_id={project_id}, sent_to={len(sent_to)} orang")
    return {"status": "ok", "project_id": project_id}


# ─── Health check untuk N8N ──────────────────────────────────────
@router.get("/health")
def n8n_health():
    """N8N bisa ping endpoint ini untuk cek koneksi backend."""
    return {"status": "ok", "service": "AI CPMIS Backend", "n8n_ready": True}
