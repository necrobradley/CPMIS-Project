"""Daftarkan endpoint webhook backend ke Telegram setelah deployment."""
import sys

import httpx

from app.core.config import settings


def main() -> int:
    if not settings.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN belum diisi.")
        return 1
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        print("TELEGRAM_WEBHOOK_SECRET belum diisi.")
        return 1
    if not settings.PUBLIC_BASE_URL.startswith("https://"):
        print("PUBLIC_BASE_URL harus URL HTTPS backend yang sudah dideploy.")
        return 1

    webhook_url = (
        settings.PUBLIC_BASE_URL.rstrip("/")
        + "/api/v1/telegram/webhook"
    )
    telegram_url = (
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    )
    response = httpx.post(
        telegram_url,
        json={
            "url": webhook_url,
            "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        print(f"Telegram menolak webhook: {result.get('description', 'unknown error')}")
        return 1
    print(f"Webhook Telegram aktif: {webhook_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
