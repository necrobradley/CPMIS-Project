"""Transactional authentication email and single-use token management."""
from __future__ import annotations

import hashlib
import html
import logging
import secrets
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import EmailActionToken, User

logger = logging.getLogger(__name__)

VERIFY_EMAIL = "verify_email"
ACCEPT_INVITATION = "accept_invitation"
RESET_PASSWORD = "reset_password"


@dataclass(frozen=True)
class IssuedEmailToken:
    token: str
    expires_at: datetime


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_email_token(
    db: Session,
    user: User,
    purpose: str,
    *,
    ttl: timedelta,
    requested_by: int | None = None,
) -> IssuedEmailToken:
    now = datetime.utcnow()
    db.query(EmailActionToken).filter(
        EmailActionToken.user_id == user.id,
        EmailActionToken.purpose == purpose,
        EmailActionToken.used_at.is_(None),
    ).update({EmailActionToken.used_at: now}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(48)
    expires_at = now + ttl
    db.add(EmailActionToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        purpose=purpose,
        expires_at=expires_at,
        requested_by=requested_by,
    ))
    db.flush()
    return IssuedEmailToken(token=raw_token, expires_at=expires_at)


def get_valid_email_token(db: Session, raw_token: str, purpose: str) -> EmailActionToken | None:
    if not raw_token or len(raw_token) > 256:
        return None
    return db.query(EmailActionToken).filter(
        EmailActionToken.token_hash == _hash_token(raw_token),
        EmailActionToken.purpose == purpose,
        EmailActionToken.used_at.is_(None),
        EmailActionToken.expires_at > datetime.utcnow(),
    ).first()


def consume_email_token(token: EmailActionToken) -> None:
    token.used_at = datetime.utcnow()


def _auth_link(path: str, token: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}{path}?{urlencode({'token': token})}"


def _email_html(*, name: str, heading: str, message: str, button_label: str, url: str, expiry: str) -> str:
    safe_name = html.escape(name)
    safe_heading = html.escape(heading)
    safe_message = html.escape(message)
    safe_url = html.escape(url, quote=True)
    return f"""<!doctype html>
<html lang="id"><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a">
<div style="display:none;max-height:0;overflow:hidden">{safe_heading}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e2e8f0">
<tr><td style="padding:28px 32px;background:#082f49;color:#fff"><div style="font-size:24px;font-weight:700">Rencanix</div><div style="margin-top:5px;font-size:13px;color:#bae6fd">Intelligent Project Control</div></td></tr>
<tr><td style="padding:32px"><h1 style="margin:0 0 18px;font-size:24px">{safe_heading}</h1><p style="margin:0 0 12px;line-height:1.7;color:#475569">Halo {safe_name},</p><p style="margin:0 0 24px;line-height:1.7;color:#475569">{safe_message}</p>
<a href="{safe_url}" style="display:inline-block;padding:13px 22px;border-radius:10px;background:#0ea5e9;color:#fff;text-decoration:none;font-weight:700">{html.escape(button_label)}</a>
<p style="margin:24px 0 8px;font-size:12px;line-height:1.6;color:#64748b">Tautan ini berlaku {html.escape(expiry)} dan hanya dapat digunakan satu kali.</p>
<p style="margin:0;font-size:12px;line-height:1.6;color:#94a3b8">Jika Anda tidak meminta tindakan ini, abaikan email ini. Jangan membagikan tautan kepada siapa pun.</p>
</td></tr></table></td></tr></table></body></html>"""


def _send_with_resend(*, to: str, subject: str, body: str) -> None:
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": body},
        timeout=12,
    )
    response.raise_for_status()


def _send_with_smtp(*, to: str, subject: str, body: str) -> None:
    sender_address = settings.SMTP_FROM.strip() or settings.SMTP_USERNAME.strip()
    message = EmailMessage()
    message["From"] = formataddr(("Rencanix", sender_address))
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Email ini memerlukan tampilan HTML. Buka melalui aplikasi email modern untuk melanjutkan.")
    message.add_alternative(body, subtype="html")

    context = ssl.create_default_context()
    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12, context=context) as server:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


def _send_email(*, to: str, subject: str, body: str) -> tuple[bool, str | None]:
    provider = "resend" if settings.RESEND_API_KEY else "smtp"
    smtp_ready = bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)
    if provider == "smtp" and not smtp_ready:
        logger.warning("No transactional email provider is configured; email to %s was not sent", to)
        return False, "Penyedia email belum dikonfigurasi"
    try:
        if provider == "resend":
            _send_with_resend(to=to, subject=subject, body=body)
        else:
            _send_with_smtp(to=to, subject=subject, body=body)
        return True, None
    except Exception as exc:
        logger.error("Authentication email delivery through %s failed for %s: %s", provider, to, exc)
        return False, "Pengiriman email gagal"


def send_verification_email(user: User, token: str) -> tuple[bool, str | None]:
    url = _auth_link("/verify-email", token)
    return _send_email(
        to=user.email,
        subject="Verifikasi email akun Rencanix",
        body=_email_html(
            name=user.name,
            heading="Verifikasi alamat email Anda",
            message="Konfirmasikan alamat email ini untuk mengaktifkan akses akun Rencanix Anda.",
            button_label="Verifikasi email",
            url=url,
            expiry=f"selama {settings.EMAIL_VERIFICATION_TTL_HOURS} jam",
        ),
    )


def send_invitation_email(user: User, token: str) -> tuple[bool, str | None]:
    url = _auth_link("/accept-invitation", token)
    return _send_email(
        to=user.email,
        subject="Undangan bergabung ke Rencanix",
        body=_email_html(
            name=user.name,
            heading="Anda diundang ke Rencanix",
            message="Administrator organisasi telah membuat akun untuk Anda. Tetapkan password pribadi untuk mengaktifkan akun.",
            button_label="Aktifkan akun",
            url=url,
            expiry=f"selama {settings.EMAIL_INVITATION_TTL_HOURS} jam",
        ),
    )


def send_password_reset_email(user: User, token: str) -> tuple[bool, str | None]:
    url = _auth_link("/reset-password", token)
    return _send_email(
        to=user.email,
        subject="Atur ulang password Rencanix",
        body=_email_html(
            name=user.name,
            heading="Atur ulang password",
            message="Kami menerima permintaan untuk mengganti password akun Anda. Lanjutkan hanya jika permintaan ini berasal dari Anda.",
            button_label="Atur ulang password",
            url=url,
            expiry=f"selama {settings.PASSWORD_RESET_TTL_MINUTES} menit",
        ),
    )
