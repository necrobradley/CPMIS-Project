import csv
import io
import secrets
import string
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models.user import Division, Project, ProjectMembership, ProjectRolePolicy, User, UserRole
from app.schemas.schemas import (
    PasswordChangeRequest,
    UserProjectSetupCreate,
    UserProjectSetupResponse,
    UserProjectSetupUpdate,
    UserResponse,
    UserUpdate,
)
from app.core.security import get_current_user, require_roles
from app.core.security import get_password_hash, verify_password
from app.services.audit_service import log_audit
from app.services.project_role_catalog import (
    is_valid_project_role,
    project_role_label,
    role_requires_division,
)
from app.services.report_workflow import can_access_project
from app.services.storage_service import storage_service
from app.services.email_auth import ACCEPT_INVITATION, issue_email_token, send_invitation_email
from app.core.config import settings

router = APIRouter(prefix="/users", tags=["Users"])
AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _clean_csv_value(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


def _optional_int(value: str) -> Optional[int]:
    return int(value) if value else None


def _ensure_generated_role(role: UserRole) -> None:
    if role in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=400,
            detail="Admin Proyek tidak dapat membuat akun Admin Owner atau Admin Proyek lain.",
        )


def _admin_project_membership(db: Session, admin: User) -> ProjectMembership:
    memberships = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == admin.id,
        ProjectMembership.project_role == "project_admin",
        ProjectMembership.is_active == True,
    ).all()
    if len(memberships) != 1:
        raise HTTPException(
            status_code=409,
            detail="Akun Admin Proyek harus terhubung tepat ke satu proyek.",
        )
    return memberships[0]


def _ensure_admin_project_scope(db: Session, admin: User, project_id: int) -> ProjectMembership:
    membership = _admin_project_membership(db, admin)
    if membership.project_id != project_id:
        raise HTTPException(status_code=403, detail="Admin Proyek hanya dapat mengelola proyeknya sendiri.")
    return membership


def _ensure_user_in_admin_project(db: Session, admin: User, user_id: int) -> None:
    admin_membership = _admin_project_membership(db, admin)
    if user_id == admin.id:
        return
    exists = db.query(ProjectMembership.id).filter(
        ProjectMembership.project_id == admin_membership.project_id,
        ProjectMembership.user_id == user_id,
        ProjectMembership.is_active == True,
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="User tidak ditemukan pada proyek Admin Proyek ini")


def _safe_user(user: User, viewer: User) -> dict:
    expose_contact = viewer.role in (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER) or user.id == viewer.id
    return {
        "id": user.id, "name": user.name,
        "email": user.email if expose_contact else None,
        "role": user.role,
        "phone": user.phone if expose_contact else None,
        "division_id": user.division_id,
        "telegram_id": user.telegram_id if expose_contact else None,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
        "email_verified_at": user.email_verified_at,
        "email_verification_required": user.email_verification_required,
        "must_set_password": user.must_set_password,
        "created_at": user.created_at,
    }


def _membership_payload(membership: ProjectMembership, viewer: User) -> dict:
    member = membership.user
    return {
        "id": membership.id,
        "project_id": membership.project_id,
        "user_id": membership.user_id,
        "division_id": membership.division_id,
        "project_role": membership.project_role,
        "is_active": membership.is_active,
        "joined_at": membership.joined_at,
        "user": _safe_user(member, viewer),
        "division": membership.division,
    }


def _validate_project_assignment(
    db: Session,
    project_id: int,
    project_division_id: Optional[int],
    project_role: str,
) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    if not is_valid_project_role(project_role):
        raise HTTPException(status_code=400, detail="Peran proyek tidak valid")
    if role_requires_division(project_role) and project_division_id is None:
        raise HTTPException(status_code=400, detail=f"{project_role_label(project_role)} wajib ditempatkan pada divisi")
    policy = db.query(ProjectRolePolicy).filter(
        ProjectRolePolicy.project_id == project_id,
        ProjectRolePolicy.role_code == project_role,
    ).first()
    if policy and not policy.enabled:
        raise HTTPException(status_code=409, detail=f"{project_role_label(project_role)} sedang dinonaktifkan untuk proyek ini")
    if project_division_id is not None:
        division = db.query(Division).filter(
            Division.id == project_division_id,
            Division.project_id == project_id,
        ).first()
        if not division:
            raise HTTPException(status_code=400, detail="Divisi tidak berasal dari proyek ini")
    return project


def _upsert_project_membership(
    db: Session,
    user_id: int,
    project_id: int,
    project_division_id: Optional[int],
    project_role: str,
) -> ProjectMembership:
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == user_id,
    ).first()
    if membership:
        membership.division_id = project_division_id
        membership.project_role = project_role
        membership.is_active = True
    else:
        membership = ProjectMembership(
            project_id=project_id,
            user_id=user_id,
            division_id=project_division_id,
            project_role=project_role,
            is_active=True,
        )
        db.add(membership)
    db.flush()
    return membership


@router.get("", response_model=List[UserResponse])
def list_users(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil user aktif sesuai kebutuhan koordinasi role."""
    if current_user.role == UserRole.OWNER:
        return [_safe_user(current_user, current_user)]
    query = db.query(User).filter(User.is_active == True, User.role != UserRole.OWNER)
    if current_user.role == UserRole.ADMIN and project_id is None:
        project_id = _admin_project_membership(db, current_user).project_id
    if project_id is not None:
        if current_user.role == UserRole.ADMIN:
            _ensure_admin_project_scope(db, current_user, project_id)
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
        if not can_access_project(current_user, project):
            raise HTTPException(status_code=403, detail="Proyek tidak tersedia untuk akun ini")
        user_ids = [
            row[0] for row in db.query(ProjectMembership.user_id).filter(
                ProjectMembership.project_id == project_id,
                ProjectMembership.is_active == True,
            ).all()
        ]
        if current_user.id not in user_ids:
            user_ids.append(current_user.id)
        users = query.filter(User.id.in_(user_ids or [-1])).order_by(User.name).all()
        return [_safe_user(user, current_user) for user in users]

    if current_user.role in (UserRole.DIRECTOR, UserRole.MANAGER):
        return query.order_by(User.name).all()

    users = query.filter(or_(
        User.id == current_user.id,
        User.division_id == current_user.division_id,
    )).order_by(User.name).all()
    return [_safe_user(user, current_user) for user in users]


@router.post("/setup", response_model=UserProjectSetupResponse, status_code=201)
def create_user_with_project_setup(
    data: UserProjectSetupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    _ensure_generated_role(data.role)
    if data.project_id is None:
        raise HTTPException(status_code=400, detail="Admin Proyek wajib menempatkan akun pada proyeknya")
    _ensure_admin_project_scope(db, current_user, data.project_id)
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    membership = None
    project = None
    if data.project_id is not None:
        project = _validate_project_assignment(db, data.project_id, data.project_division_id, data.project_role)

    user = User(
        name=data.name,
        email=data.email,
        password_hash=get_password_hash(secrets.token_urlsafe(32)),
        role=data.role,
        phone=data.phone,
        telegram_id=data.telegram_id,
        division_id=data.division_id,
        email_verified_at=None,
        email_verification_required=True,
        must_set_password=True,
    )
    db.add(user)
    db.flush()

    if project:
        membership = _upsert_project_membership(
            db,
            user.id,
            project.id,
            data.project_division_id,
            data.project_role,
        )

    log_audit(
        db,
        actor_id=current_user.id,
        action="users.setup_created",
        entity_type="user",
        entity_id=user.id,
        project_id=project.id if project else None,
        summary=f"Akun dibuat lewat setup wizard: {user.email}",
        after={
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
            "project_id": project.id if project else None,
            "project_role": data.project_role if project else None,
            "division_id": data.project_division_id if project else None,
        },
    )
    issued = issue_email_token(
        db, user, ACCEPT_INVITATION,
        ttl=timedelta(hours=settings.EMAIL_INVITATION_TTL_HOURS),
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(user)
    invitation_sent, invitation_error = send_invitation_email(user, issued.token)
    if membership:
        db.refresh(membership)
    return {
        "user": _safe_user(user, current_user),
        "membership": _membership_payload(membership, current_user) if membership else None,
        "invitation_sent": invitation_sent,
        "invitation_message": invitation_error or "Undangan aktivasi dikirim melalui email",
    }


@router.patch("/{user_id}/setup", response_model=UserProjectSetupResponse)
def update_user_project_setup(
    user_id: int,
    data: UserProjectSetupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    _ensure_user_in_admin_project(db, current_user, user.id)

    updates = data.model_dump(exclude_unset=True)
    next_global_role = updates.get("role", user.role)
    if next_global_role in (UserRole.OWNER, UserRole.ADMIN) and user.id != current_user.id:
        raise HTTPException(status_code=400, detail="Role Admin Owner/Admin Proyek tidak dapat diberikan melalui Pengguna")
    if user.id == current_user.id and next_global_role != UserRole.ADMIN:
        raise HTTPException(status_code=409, detail="Admin Proyek tidak dapat mengubah role akunnya sendiri")
    if data.project_id is None:
        raise HTTPException(status_code=400, detail="Assignment proyek wajib diisi")
    _ensure_admin_project_scope(db, current_user, data.project_id)
    for field in ("role", "phone", "telegram_id", "is_active"):
        if field in updates:
            setattr(user, field, updates[field])

    membership = None
    project = None
    if data.project_id is not None:
        existing_membership = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == data.project_id,
            ProjectMembership.user_id == user.id,
        ).first()
        project_role = data.project_role or (existing_membership.project_role if existing_membership else "staff")
        project_division_id = (
            data.project_division_id
            if "project_division_id" in updates
            else (existing_membership.division_id if existing_membership else None)
        )
        project = _validate_project_assignment(db, data.project_id, project_division_id, project_role)
        membership = _upsert_project_membership(
            db,
            user.id,
            project.id,
            project_division_id,
            project_role,
        )

    log_audit(
        db,
        actor_id=current_user.id,
        action="users.setup_updated",
        entity_type="user",
        entity_id=user.id,
        project_id=project.id if project else None,
        summary=f"Setup akun diperbarui: {user.email}",
        after={
            "role": user.role.value if hasattr(user.role, "value") else user.role,
            "telegram_id": user.telegram_id,
            "project_id": project.id if project else None,
            "project_role": membership.project_role if membership else None,
            "division_id": membership.division_id if membership else None,
        },
    )
    db.commit()
    db.refresh(user)
    if membership:
        db.refresh(membership)
    return {
        "user": _safe_user(user, current_user),
        "membership": _membership_payload(membership, current_user) if membership else None,
    }


@router.post("/import")
async def import_users_from_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Import daftar pegawai dari CSV dan buat akun internal secara otomatis."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Gunakan file CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV harus UTF-8")

    reader = csv.DictReader(io.StringIO(text))
    required_columns = {"name", "email"}
    if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=400, detail="CSV wajib memiliki kolom name dan email")

    results = []
    pending_invitations: list[tuple[User, str]] = []
    created_count = 0
    skipped_count = 0
    for index, row in enumerate(reader, start=2):
        name = _clean_csv_value(row, "name")
        email = _clean_csv_value(row, "email").lower()
        if not name or not email:
            results.append({"row": index, "email": email, "status": "error", "message": "name dan email wajib diisi"})
            skipped_count += 1
            continue
        if db.query(User).filter(User.email == email).first():
            results.append({"row": index, "email": email, "status": "skipped", "message": "Email sudah terdaftar"})
            skipped_count += 1
            continue

        role_value = _clean_csv_value(row, "role") or UserRole.STAFF.value
        try:
            role = UserRole(role_value)
            _ensure_generated_role(role)
        except (ValueError, HTTPException) as exc:
            message = exc.detail if isinstance(exc, HTTPException) else f"Role tidak valid: {role_value}"
            results.append({"row": index, "email": email, "status": "error", "message": message})
            skipped_count += 1
            continue

        project_id = _optional_int(_clean_csv_value(row, "project_id"))
        project_division_id = _optional_int(_clean_csv_value(row, "project_division_id"))
        project_role = _clean_csv_value(row, "project_role") or "staff"
        project = None
        try:
            if project_id is None:
                project_id = _admin_project_membership(db, current_user).project_id
            _ensure_admin_project_scope(db, current_user, project_id)
            project = _validate_project_assignment(db, project_id, project_division_id, project_role)
        except HTTPException as exc:
            results.append({"row": index, "email": email, "status": "error", "message": exc.detail})
            skipped_count += 1
            continue

        user = User(
            name=name,
            email=email,
            password_hash=get_password_hash(secrets.token_urlsafe(32)),
            role=role,
            phone=_clean_csv_value(row, "phone") or None,
            telegram_id=_clean_csv_value(row, "telegram_id") or None,
            division_id=_optional_int(_clean_csv_value(row, "division_id")),
            email_verified_at=None,
            email_verification_required=True,
            must_set_password=True,
        )
        db.add(user)
        db.flush()
        membership = None
        if project:
            membership = _upsert_project_membership(db, user.id, project.id, project_division_id, project_role)
        issued = issue_email_token(
            db, user, ACCEPT_INVITATION,
            ttl=timedelta(hours=settings.EMAIL_INVITATION_TTL_HOURS),
            requested_by=current_user.id,
        )
        pending_invitations.append((user, issued.token))

        log_audit(
            db,
            actor_id=current_user.id,
            action="users.import_created",
            entity_type="user",
            entity_id=user.id,
            project_id=project.id if project else None,
            summary=f"Akun dibuat dari import pegawai: {user.email}",
            after={
                "email": user.email,
                "role": role.value,
                "project_id": project.id if project else None,
                "project_role": membership.project_role if membership else None,
            },
        )
        results.append({
            "row": index,
            "email": email,
            "status": "created",
            "message": "Akun dibuat; undangan aktivasi dijadwalkan melalui email",
            "role": role.value,
        })
        created_count += 1

    db.commit()
    delivery_by_email = {
        user.email: send_invitation_email(user, token)[0]
        for user, token in pending_invitations
    }
    for result in results:
        if result.get("status") == "created":
            delivered = delivery_by_email.get(result["email"], False)
            result["status"] = "invited" if delivered else "created"
            result["message"] = (
                "Akun dibuat dan undangan email terkirim"
                if delivered else "Akun dibuat, tetapi email belum terkirim. Gunakan kirim ulang undangan."
            )
    return {"created": created_count, "skipped": skipped_count, "results": results}


@router.post("/{user_id}/resend-invitation")
def resend_user_invitation(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    _ensure_user_in_admin_project(db, current_user, user.id)
    if not user.must_set_password:
        raise HTTPException(status_code=409, detail="Akun sudah pernah diaktifkan")
    issued = issue_email_token(
        db, user, ACCEPT_INVITATION,
        ttl=timedelta(hours=settings.EMAIL_INVITATION_TTL_HOURS),
        requested_by=current_user.id,
    )
    db.commit()
    sent, error = send_invitation_email(user, issued.token)
    if not sent:
        raise HTTPException(status_code=503, detail=error or "Undangan belum dapat dikirim")
    return {"success": True, "message": "Undangan aktivasi berhasil dikirim ulang"}


@router.patch("/me/password")
def change_my_password(
    data: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="Password lama tidak sesuai")
    current_user.password_hash = get_password_hash(data.new_password)
    current_user.auth_version += 1
    log_audit(
        db,
        actor_id=current_user.id,
        action="users.password_changed",
        entity_type="user",
        entity_id=current_user.id,
        summary=f"Password diganti oleh user: {current_user.email}",
    )
    db.commit()
    return {"success": True}


@router.post("/me/avatar")
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload foto profil untuk akun sendiri."""
    extension = AVATAR_CONTENT_TYPES.get(file.content_type or "")
    if not extension:
        raise HTTPException(status_code=400, detail="Foto harus JPG, PNG, atau WebP")

    content = await file.read()
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran foto maksimal 2MB")

    filename = f"user-{current_user.id}-{uuid4().hex}{extension}"
    object_name = f"avatars/{filename}"
    storage_service.upload_file(content, object_name, file.content_type or "application/octet-stream")

    current_user.avatar_url = f"/api/v1/users/{current_user.id}/avatar/{filename}"
    log_audit(
        db,
        actor_id=current_user.id,
        action="users.avatar_uploaded",
        entity_type="user",
        entity_id=current_user.id,
        summary=f"Foto profil diperbarui: {current_user.email}",
        after={"avatar_url": current_user.avatar_url},
    )
    db.commit()
    return {"avatar_url": current_user.avatar_url}


@router.get("/{user_id}/avatar/{filename}", include_in_schema=False)
def get_user_avatar(user_id: int, filename: str):
    if not filename.startswith(f"user-{user_id}-") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    try:
        content = storage_service.get_file_bytes(f"avatars/{filename}")
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan") from exc
    extension = filename.rsplit(".", 1)[-1].lower()
    media_type = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(extension, "application/octet-stream")
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil detail satu user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if user.role == UserRole.OWNER and current_user.id != user.id:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if current_user.role == UserRole.ADMIN:
        _ensure_user_in_admin_project(db, current_user, user.id)
    if current_user.role not in (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER) and current_user.id != user.id:
        raise HTTPException(status_code=403, detail="Data kontak pengguna tidak tersedia untuk akun ini")
    return _safe_user(user, current_user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update data user (hanya diri sendiri atau Admin)."""
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Akses ditolak")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if user.role == UserRole.OWNER and current_user.id != user.id:
        raise HTTPException(status_code=403, detail="Admin Owner tidak dapat diubah oleh Admin Proyek")
    if current_user.role == UserRole.ADMIN:
        _ensure_user_in_admin_project(db, current_user, user.id)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    """Nonaktifkan user (Admin saja)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if user.role in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Akun Admin Owner/Admin Proyek tidak dapat dinonaktifkan dari menu Pengguna")
    _ensure_user_in_admin_project(db, current_user, user.id)

    user.is_active = False  # soft delete
    db.commit()


@router.get("/by-telegram/{telegram_id}", response_model=UserResponse)
def get_user_by_telegram(
    telegram_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Cari user berdasarkan Telegram ID (digunakan oleh bot)."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    _ensure_user_in_admin_project(db, current_user, user.id)
    return user
