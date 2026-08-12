import pytest
from fastapi import HTTPException
from telegram.ext import Application

from app.api.v1.endpoints.telegram_webhook import (
    telegram_webhook_health,
    verify_telegram_webhook_secret,
)
from app.core.config import settings
from app.services.telegram_service import create_bot_app


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


def test_bot_application_can_be_built_on_supported_python(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")

    bot_app = create_bot_app()

    assert isinstance(bot_app, Application)
