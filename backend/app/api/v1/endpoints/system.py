"""
System readiness endpoint for dashboards and external monitors.
"""
import logging
import secrets

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_roles, verify_password
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.ai_service import AIService
from app.services.audit_service import log_audit
from app.services.storage_service import storage_service
from app.services.system_reset import collect_operational_storage_paths, reset_operational_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System"])


class OperationalResetRequest(BaseModel):
    owner_email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    confirmation: str = Field(min_length=1, max_length=40)


async def _read_project_archive(dataset: UploadFile) -> bytes:
    filename = (dataset.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Paket data proyek harus berupa file ZIP")

    content = await dataset.read()
    if not content:
        raise HTTPException(status_code=400, detail="File paket data proyek kosong")
    max_bytes = max(1, settings.BOOTSTRAP_MAX_UPLOAD_MB) * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Dataset melebihi batas {settings.BOOTSTRAP_MAX_UPLOAD_MB} MB",
        )
    return content


def _import_project_archive(
    db: Session,
    content: bytes,
    *,
    admin_email: str,
    admin_password: str,
    telegram_id: str | None,
) -> dict:
    try:
        from app.services.project_dataset import import_project_dataset

        return import_project_dataset(
            db,
            content,
            admin_email=admin_email,
            admin_password=admin_password,
            telegram_id=telegram_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/project-dataset", summary="Impor paket data proyek dari Admin Console")
async def import_project_from_website(
    dataset: UploadFile = File(...),
    telegram_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Impor idempotent satu proyek menggunakan akun admin yang sedang login."""
    content = await _read_project_archive(dataset)
    result = _import_project_archive(
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
        action="system.project_dataset_imported",
        entity_type="project",
        entity_id=result["project_id"],
        project_id=result["project_id"],
        summary=f"Paket data proyek diimpor dari Admin Console oleh {current_user.email}",
        after={
            **{key: value for key, value in result.items() if key != "generated_accounts"},
            "generated_accounts": [
                {key: value for key, value in account.items() if key != "temporary_password"}
                for account in result.get("generated_accounts", [])
            ],
        },
    )
    db.commit()
    return result


@router.post("/bootstrap/project-dataset", summary="Setup awal dan impor paket data proyek")
async def bootstrap_project(
    dataset: UploadFile = File(...),
    admin_email: str = Form("admin@cpmis.example.com"),
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

    content = await _read_project_archive(dataset)
    return _import_project_archive(
        db,
        content,
        admin_email=admin_email,
        admin_password=admin_password,
        telegram_id=telegram_id,
    )


@router.post("/reset/operational-data", summary="Kosongkan data operasional proyek")
def reset_project_operational_data(
    payload: OperationalResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Reset berisiko tinggi yang hanya dapat dijalankan owner/admin aktif.

    Akun pengguna dan konfigurasi platform dipertahankan. Proyek, divisi,
    tugas, laporan, dokumen, komunikasi, approval, notifikasi, dan audit
    operasional dikosongkan.
    """
    if payload.owner_email.strip().casefold() != current_user.email.strip().casefold():
        raise HTTPException(status_code=400, detail="Email owner tidak sesuai dengan akun yang sedang aktif")
    if payload.confirmation.strip() != "RESET DATA":
        raise HTTPException(status_code=400, detail='Ketik "RESET DATA" untuk mengonfirmasi')
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password owner tidak valid")

    storage_paths = collect_operational_storage_paths(db)
    try:
        deleted = reset_operational_data(db)
        db.commit()
    except Exception:
        db.rollback()
        raise

    removed_files = 0
    failed_files = 0
    for object_path in storage_paths:
        try:
            if storage_service.delete_file(object_path):
                removed_files += 1
            else:
                failed_files += 1
        except Exception as exc:  # Database reset must remain successful if object cleanup fails.
            failed_files += 1
            logger.warning("Operational reset could not delete object %s: %s", object_path, exc)

    return {
        "status": "reset_complete",
        "message": "Data operasional telah dikosongkan. Akun dan konfigurasi platform tetap tersedia.",
        "deleted_rows": deleted,
        "deleted_row_total": sum(deleted.values()),
        "storage": {
            "queued": len(storage_paths),
            "deleted": removed_files,
            "failed": failed_files,
        },
    }


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
