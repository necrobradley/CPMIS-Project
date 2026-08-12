import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.telegram_webhook import (
    telegram_webhook_health,
    verify_telegram_webhook_secret,
)
from app.core.config import settings


def test_webhook_rejects_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")

    with pytest.raises(HTTPException) as exc:
        verify_telegram_webhook_secret("anything")

    assert exc.value.status_code == 503


def test_webhook_uses_constant_time_secret_check(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "valid-secret")

    with pytest.raises(HTTPException) as exc:
        verify_telegram_webhook_secret("wrong-secret")
    assert exc.value.status_code == 403

    verify_telegram_webhook_secret("valid-secret")


def test_webhook_health_reports_serverless_mode(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_ENABLED", True)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "valid-secret")
    monkeypatch.setattr(settings, "BACKGROUND_WORKERS_ENABLED", False)

    assert telegram_webhook_health() == {
        "configured": True,
        "mode": "webhook",
    }
