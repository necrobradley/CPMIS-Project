from app.core.config import settings, transactional_email_configured
from app.services import email_auth


class FakeSMTP:
    messages = []

    def __init__(self, host, port, timeout, context=None):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def login(self, username, password):
        assert username == "sender@example.com"
        assert password == "app-password"

    def send_message(self, message):
        self.messages.append(message)


def test_personal_smtp_is_supported_as_transactional_email_provider(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "SMTP_USE_SSL", True)
    monkeypatch.setattr(settings, "SMTP_FROM", "sender@example.com")
    monkeypatch.setattr(email_auth.smtplib, "SMTP_SSL", FakeSMTP)
    FakeSMTP.messages.clear()

    delivered, error = email_auth._send_email(
        to="recipient@example.com",
        subject="Verifikasi",
        body="<p>Aktifkan akun</p>",
    )

    assert transactional_email_configured() is True
    assert delivered is True
    assert error is None
    assert len(FakeSMTP.messages) == 1
    assert FakeSMTP.messages[0]["To"] == "recipient@example.com"


def test_transactional_email_is_not_ready_without_complete_provider(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    assert transactional_email_configured() is False
