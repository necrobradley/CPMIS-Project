"""Telegram webhook untuk deployment serverless (misalnya Vercel)."""
from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, Header, HTTPException, Request
from telegram import Update

from app.core.config import settings
from app.services.telegram_service import create_bot_app


router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])
_bot_application = None
_initialization_lock = asyncio.Lock()


async def _get_bot_application():
    global _bot_application
    if _bot_application is not None:
        return _bot_application
    async with _initialization_lock:
        if _bot_application is None:
            application = create_bot_app()
            await application.initialize()
            _bot_application = application
    return _bot_application


def verify_telegram_webhook_secret(value: str | None) -> None:
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if not settings.TELEGRAM_BOT_TOKEN or not expected:
        raise HTTPException(status_code=503, detail="Telegram webhook belum dikonfigurasi")
    if not value or not secrets.compare_digest(value, expected):
        raise HTTPException(status_code=403, detail="Telegram webhook secret tidak valid")


@router.post("/webhook")
async def receive_telegram_update(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
):
    verify_telegram_webhook_secret(x_telegram_bot_api_secret_token)
    payload = await request.json()
    application = await _get_bot_application()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return {"status": "ok"}


@router.get("/webhook/health")
def telegram_webhook_health():
    return {
        "configured": bool(
            settings.TELEGRAM_BOT_ENABLED
            and settings.TELEGRAM_BOT_TOKEN
            and settings.TELEGRAM_WEBHOOK_SECRET
        ),
        "mode": "webhook" if not settings.BACKGROUND_WORKERS_ENABLED else "polling",
    }
