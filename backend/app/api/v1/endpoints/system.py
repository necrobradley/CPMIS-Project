"""
System readiness endpoint for dashboards and external monitors.
"""
import logging
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
import httpx
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings, transactional_email_configured
from app.core.security import get_password_hash, require_roles, verify_password
from app.db.database import get_db
from app.models.user import Project, ProjectMembership, ProjectStatus, User, UserRole
from app.services.ai_service import AIService
from app.services.audit_service import log_audit
from app.services.storage_service import storage_service
from app.services.system_reset import collect_operational_storage_paths, reset_operational_data
from app.services.email_auth import VERIFY_EMAIL, issue_email_token, send_verification_email
from app.services.feature_flags import bootstrap_project_feature_entitlements

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["System"])


class OperationalResetRequest(BaseModel):
    owner_email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    confirmation: str = Field(min_length=1, max_length=40)


class OwnerBootstrapRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class ProjectAdminBootstrapRequest(BaseModel):
    admin_name: str = Field(min_length=2, max_length=100)
    admin_email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    project_name: str = Field(min_length=2, max_length=200)
    telegram_id: str | None = Field(default=None, max_length=50)


def _require_bootstrap_secret(value: str | None) -> None:
    if not settings.BOOTSTRAP_SECRET:
        raise HTTPException(status_code=503, detail="BOOTSTRAP_SECRET belum dikonfigurasi")
    if not value or not secrets.compare_digest(value, settings.BOOTSTRAP_SECRET):
        raise HTTPException(status_code=403, detail="Bootstrap secret tidak valid")


def _validate_admin_password(value: str) -> None:
    if len(value) < 12:
        raise HTTPException(status_code=400, detail="Password admin minimal 12 karakter")
    if not any(char.isupper() for char in value) or not any(char.islower() for char in value) or not any(char.isdigit() for char in value):
        raise HTTPException(status_code=400, detail="Password admin wajib memiliki huruf besar, huruf kecil, dan angka")


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
    _require_bootstrap_secret(x_bootstrap_secret)
    _validate_admin_password(admin_password)

    content = await _read_project_archive(dataset)
    result = _import_project_archive(
        db,
        content,
        admin_email=admin_email,
        admin_password=admin_password,
        telegram_id=telegram_id,
    )
    verification_sent = False
    verification_message = "Akun admin existing tetap aktif"
    if result.get("admin_created"):
        owner = db.query(User).filter(User.email == result["admin_email"]).first()
        if owner:
            issued = issue_email_token(
                db, owner, VERIFY_EMAIL,
                ttl=timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
            )
            db.commit()
            verification_sent, delivery_error = send_verification_email(owner, issued.token)
            verification_message = delivery_error or "Email verifikasi admin berhasil dikirim"
    return {
        **result,
        "verification_email_sent": verification_sent,
        "verification_message": verification_message,
    }


@router.post("/bootstrap/project-admin", status_code=201, summary="Buat satu Admin Proyek dan satu proyek kosong")
def bootstrap_project_admin(
    payload: ProjectAdminBootstrapRequest,
    x_bootstrap_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Setup akun dipisahkan dari import dataset dan dokumen proyek."""
    _require_bootstrap_secret(x_bootstrap_secret)
    _validate_admin_password(payload.password)
    if not transactional_email_configured():
        raise HTTPException(
            status_code=503,
            detail="Email transaksional belum dikonfigurasi. Admin Proyek tidak dibuat agar akun tidak terkunci.",
        )

    normalized_email = str(payload.admin_email).strip().lower()
    project_name = payload.project_name.strip()
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="Email sudah digunakan oleh akun lain")
    if db.query(Project).filter(Project.project_name == project_name).first():
        raise HTTPException(status_code=409, detail="Nama proyek sudah terdaftar")

    admin = User(
        name=payload.admin_name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.ADMIN,
        telegram_id=(payload.telegram_id or "").strip() or None,
        is_active=True,
        email_verification_required=True,
        email_verified_at=None,
        must_set_password=False,
    )
    db.add(admin)
    db.flush()
    project = Project(
        project_name=project_name,
        owner_id=admin.id,
        status=ProjectStatus.PLANNING,
        progress_percent=0,
        plan_key=None,
    )
    db.add(project)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=admin.id,
        project_role="project_admin",
        is_active=True,
    ))
    bootstrap_project_feature_entitlements(db, project, admin.id)
    issued = issue_email_token(
        db,
        admin,
        VERIFY_EMAIL,
        ttl=timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
    )
    sent, delivery_error = send_verification_email(admin, issued.token)
    if not sent:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=delivery_error or "Email verifikasi gagal dikirim; Admin Proyek belum dibuat",
        )
    db.commit()
    return {
        "admin_id": admin.id,
        "admin_email": admin.email,
        "project_id": project.id,
        "project_name": project.project_name,
        "project_status": project.status,
        "plan_key": project.plan_key,
        "verification_email_sent": True,
        "verification_message": "Email verifikasi Admin Proyek berhasil dikirim",
    }


@router.post("/bootstrap/owner", status_code=201, summary="Provision satu-satunya Admin Owner")
def bootstrap_owner(
    payload: OwnerBootstrapRequest,
    x_bootstrap_secret: str | None = Header(None),
    db: Session = Depends(get_db),
):
    _require_bootstrap_secret(x_bootstrap_secret)
    _validate_admin_password(payload.password)
    if db.query(User).filter(User.role == UserRole.OWNER).first():
        raise HTTPException(status_code=409, detail="Admin Owner sudah tersedia dan tidak dapat dibuat ulang")
    if not transactional_email_configured():
        raise HTTPException(
            status_code=503,
            detail="Email transaksional belum dikonfigurasi. Admin Owner tidak dibuat agar akun tidak terkunci sebelum verifikasi.",
        )

    normalized_email = str(payload.email).strip().lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="Email sudah digunakan oleh akun lain")

    owner = User(
        name=payload.name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.OWNER,
        is_active=True,
        email_verification_required=True,
        email_verified_at=None,
    )
    db.add(owner)
    db.flush()
    issued = issue_email_token(
        db,
        owner,
        VERIFY_EMAIL,
        ttl=timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
    )
    verification_sent, delivery_error = send_verification_email(owner, issued.token)
    if not verification_sent:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=delivery_error or "Email verifikasi gagal dikirim; Admin Owner belum dibuat",
        )
    db.commit()
    return {
        "id": owner.id,
        "email": owner.email,
        "role": owner.role,
        "verification_email_sent": verification_sent,
        "verification_message": delivery_error or "Email verifikasi Admin Owner berhasil dikirim",
    }


@router.post("/reset/operational-data", summary="Kosongkan data operasional proyek")
def reset_project_operational_data(
    payload: OperationalResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OWNER)),
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
            "transactional_email": transactional_email_configured(),
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
