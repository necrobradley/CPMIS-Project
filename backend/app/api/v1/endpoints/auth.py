from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.schemas.schemas import (
    EmailRequest, EmailTokenRequest, LoginRequest, PasswordTokenRequest,
    RefreshTokenRequest, TokenResponse, UserResponse,
)
from app.core.security import (
    verify_password, create_access_token, create_refresh_token, decode_token,
    get_current_user, get_password_hash,
)
from app.services.audit_service import log_audit
from app.services.email_auth import (
    ACCEPT_INVITATION, RESET_PASSWORD, VERIFY_EMAIL, consume_email_token,
    get_valid_email_token, issue_email_token, send_password_reset_email,
    send_verification_email,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register():
    """Registrasi publik ditutup untuk mode aplikasi internal."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Aplikasi tertutup. Akun anggota proyek dibuat oleh Admin Proyek melalui menu Pengguna.",
    )


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Login dan dapatkan JWT token."""
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun tidak aktif. Hubungi administrator."
        )

    if user.email_verification_required and user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email belum diverifikasi. Periksa inbox atau kirim ulang email verifikasi.",
        )

    if user.must_set_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun belum diaktifkan. Gunakan tautan undangan yang dikirim melalui email.",
        )

    token_data = {"sub": str(user.id), "role": user.role, "av": user.auth_version}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": str(user.id), "av": user.auth_version})

    log_audit(
        db,
        actor_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        summary=f"Login berhasil: {user.email}",
    )
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Perbarui access token menggunakan refresh token."""
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token bukan refresh token"
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first() if user_id else None
    if (
        not user or not user.is_active
        or (user.email_verification_required and user.email_verified_at is None) or user.must_set_password
        or payload.get("av") != user.auth_version
    ):
        raise HTTPException(status_code=401, detail="Sesi tidak berlaku. Silakan masuk kembali.")
    access_token = create_access_token(data={"sub": user_id, "role": user.role, "av": user.auth_version})
    new_refresh_token = create_refresh_token(data={"sub": user_id, "av": user.auth_version})

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Dapatkan data user yang sedang login."""
    return current_user


@router.post("/email/verify")
def verify_email(body: EmailTokenRequest, db: Session = Depends(get_db)):
    token = get_valid_email_token(db, body.token, VERIFY_EMAIL)
    if not token:
        raise HTTPException(status_code=400, detail="Tautan verifikasi tidak valid atau sudah kedaluwarsa")
    user = db.query(User).filter(User.id == token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Akun tidak ditemukan")
    user.email_verified_at = datetime.utcnow()
    consume_email_token(token)
    db.commit()
    return {"success": True, "message": "Email berhasil diverifikasi. Anda sekarang dapat masuk."}


@router.post("/email/resend-verification")
def resend_verification(body: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(body.email).lower()).first()
    if user and user.is_active and user.email_verification_required and user.email_verified_at is None and not user.must_set_password:
        issued = issue_email_token(
            db, user, VERIFY_EMAIL,
            ttl=timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
        )
        db.commit()
        send_verification_email(user, issued.token)
    return {"success": True, "message": "Jika akun tersebut tersedia, email verifikasi telah dikirim."}


@router.post("/invitation/accept")
def accept_invitation(body: PasswordTokenRequest, db: Session = Depends(get_db)):
    token = get_valid_email_token(db, body.token, ACCEPT_INVITATION)
    if not token:
        raise HTTPException(status_code=400, detail="Tautan undangan tidak valid atau sudah kedaluwarsa")
    user = db.query(User).filter(User.id == token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Akun tidak tersedia")
    user.password_hash = get_password_hash(body.password)
    user.email_verified_at = datetime.utcnow()
    user.email_verification_required = True
    user.must_set_password = False
    user.auth_version += 1
    consume_email_token(token)
    db.commit()
    return {"success": True, "message": "Akun berhasil diaktifkan. Silakan masuk dengan password baru."}


@router.post("/password/forgot")
def forgot_password(body: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(body.email).lower()).first()
    if user and user.is_active and (user.email_verified_at is not None or not user.email_verification_required) and not user.must_set_password:
        issued = issue_email_token(
            db, user, RESET_PASSWORD,
            ttl=timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        )
        db.commit()
        send_password_reset_email(user, issued.token)
    return {"success": True, "message": "Jika email terdaftar, tautan reset password telah dikirim."}


@router.post("/password/reset")
def reset_password(body: PasswordTokenRequest, db: Session = Depends(get_db)):
    token = get_valid_email_token(db, body.token, RESET_PASSWORD)
    if not token:
        raise HTTPException(status_code=400, detail="Tautan reset password tidak valid atau sudah kedaluwarsa")
    user = db.query(User).filter(User.id == token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Akun tidak tersedia")
    user.password_hash = get_password_hash(body.password)
    user.must_set_password = False
    user.auth_version += 1
    consume_email_token(token)
    db.commit()
    return {"success": True, "message": "Password berhasil diperbarui. Seluruh sesi lama telah dihentikan."}
