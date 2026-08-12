"""
System readiness endpoint for dashboards and external monitors.
"""
import secrets

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_roles
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.ai_service import AIService
from app.services.audit_service import log_audit

router = APIRouter(prefix="/system", tags=["System"])


async def _read_mnbc_archive(dataset: UploadFile) -> bytes:
    filename = (dataset.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Dataset MNBC harus berupa file ZIP")

    content = await dataset.read()
    if not content:
        raise HTTPException(status_code=400, detail="File dataset MNBC kosong")
    max_bytes = max(1, settings.BOOTSTRAP_MAX_UPLOAD_MB) * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Dataset melebihi batas {settings.BOOTSTRAP_MAX_UPLOAD_MB} MB",
        )
    return content


def _import_mnbc_archive(
    db: Session,
    content: bytes,
    *,
    admin_email: str,
    admin_password: str,
    telegram_id: str | None,
) -> dict:
    try:
        from app.services.mnbc_dataset import import_mnbc_demo

        return import_mnbc_demo(
            db,
            content,
            admin_email=admin_email,
            admin_password=admin_password,
            telegram_id=telegram_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/mnbc", summary="Impor dataset MNBC dari Admin Console")
async def import_mnbc_project_from_website(
    dataset: UploadFile = File(...),
    telegram_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Impor idempotent satu proyek MNBC menggunakan akun admin yang sedang login."""
    content = await _read_mnbc_archive(dataset)
    result = _import_mnbc_archive(
        db,
        content,
        admin_email=current_user.email,
        # Akun sudah dipastikan ada oleh autentikasi; password tidak dibuat ulang.
        admin_password="",
        telegram_id=(telegram_id or "").strip() or None,
    )
    log_audit(
        db,
        actor_id=current_user.id,
        action="system.mnbc_dataset_imported",
        entity_type="project",
        entity_id=result["project_id"],
        project_id=result["project_id"],
        summary=f"Dataset MNBC diimpor dari Admin Console oleh {current_user.email}",
        after=result,
    )
    db.commit()
    return result


@router.post("/bootstrap/mnbc", summary="Impor satu proyek demo MNBC dari files.zip")
async def bootstrap_mnbc_project(
    dataset: UploadFile = File(...),
    admin_email: str = Form("admin.mnbc@demo.local"),
    admin_password: str = Form(...),
    telegram_id: str | None = Form(None),
    x_bootstrap_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if not settings.BOOTSTRAP_SECRET:
        raise HTTPException(status_code=503, detail="BOOTSTRAP_SECRET belum dikonfigurasi")
    if not x_bootstrap_secret or not secrets.compare_digest(
        x_bootstrap_secret,
        settings.BOOTSTRAP_SECRET,
    ):
        raise HTTPException(status_code=403, detail="Bootstrap secret tidak valid")
    if len(admin_password) < 12:
        raise HTTPException(status_code=400, detail="Password admin minimal 12 karakter")

    content = await _read_mnbc_archive(dataset)
    return _import_mnbc_archive(
        db,
        content,
        admin_email=admin_email,
        admin_password=admin_password,
        telegram_id=telegram_id,
    )


@router.get("/status")
def system_status():
    """Public operational status used by the realtime frontend panels."""
    try:
        n8n_online = httpx.get("http://n8n:5678/healthz", timeout=1.5).status_code == 200
    except Exception:
        n8n_online = False
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "services": {
            "api": True,
            "database": True,
            "scheduler": settings.BACKGROUND_WORKERS_ENABLED,
            "telegram": settings.TELEGRAM_BOT_ENABLED and bool(settings.TELEGRAM_BOT_TOKEN),
            "n8n": n8n_online,
            "ai": AIService.is_configured(),
            "rag": settings.RAG_ENABLED,
            "ai_safety": settings.AI_SAFETY_ENABLED,
            "ai_gateway": settings.AI_GATEWAY_ENABLED,
            "ai_gateway_policy": settings.AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY,
            "ai_local": AIService.local_status(),
        },
        "workflows": [
            {
                "id": "daily-report",
                "name": "Daily report validation and notification",
                "schedule": "Realtime webhook",
                "status": "ready" if n8n_online else "offline",
            },
            {
                "id": "tender-analysis",
                "name": "Tender analysis and task generation",
                "schedule": "On document upload",
                "status": "ready" if n8n_online else "offline",
            },
            {
                "id": "deadline-alert",
                "name": "Deadline reminder",
                "schedule": "Daily 08:00 WIB",
                "status": "ready" if n8n_online else "offline",
            },
            {
                "id": "approval-routing",
                "name": "Approval routing and escalation",
                "schedule": "On approval request",
                "status": "backend-only",
            },
            {
                "id": "weekly-summary",
                "name": "Weekly executive summary",
                "schedule": "Friday 17:00 WIB",
                "status": "ready" if n8n_online else "offline",
            },
        ],
    }
