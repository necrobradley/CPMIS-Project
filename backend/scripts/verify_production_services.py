"""Periksa database cloud dan Telegram tanpa mencetak credential."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from urllib.parse import urlparse

import httpx
from sqlalchemy import create_engine, inspect, text


def check_database() -> dict:
    database_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL", "")
    result = {"configured": bool(database_url)}
    if not database_url:
        return result

    parsed = urlparse(database_url)
    result.update(
        {
            "engine": parsed.scheme.split("+")[0],
            "host_is_cloud": bool(parsed.hostname and "localhost" not in parsed.hostname),
        }
    )
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            counts = {}
            for table in ("projects", "users", "tasks", "daily_reports", "documents"):
                if table in tables:
                    counts[table] = connection.execute(
                        text(f'SELECT COUNT(*) FROM "{table}"')
                    ).scalar()
            result.update({"reachable": True, "counts": counts})
    except Exception as exc:
        result.update({"reachable": False, "error": type(exc).__name__})
    return result


async def check_telegram() -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    result = {"configured": bool(token)}
    if not token:
        return result

    async with httpx.AsyncClient(timeout=30) as client:
        me = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        webhook = await client.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo"
        )
    me_data = me.json().get("result", {}) if me.status_code == 200 else {}
    webhook_data = (
        webhook.json().get("result", {}) if webhook.status_code == 200 else {}
    )
    result.update(
        {
            "bot_username": me_data.get("username"),
            "webhook_url": webhook_data.get("url"),
            "pending_updates": webhook_data.get("pending_update_count"),
            "last_error": webhook_data.get("last_error_message"),
        }
    )
    return result


def check_blob() -> dict:
    token = os.getenv("BLOB_READ_WRITE_TOKEN", "")
    result = {"configured": bool(token)}
    if not token:
        return result

    from vercel.blob import BlobClient

    client = BlobClient(token=token)
    pathname = f"healthchecks/{uuid.uuid4().hex}.txt"
    uploaded_path = ""
    try:
        uploaded = client.put(
            pathname,
            b"CPMIS_STORAGE_OK",
            access="private",
            content_type="text/plain",
            overwrite=False,
        )
        uploaded_path = uploaded.pathname
        downloaded = client.get(uploaded_path, access="private", use_cache=False)
        content = downloaded.content if downloaded else b""
        result.update({"reachable": content == b"CPMIS_STORAGE_OK", "private": True})
    except Exception as exc:
        result.update(
            {
                "reachable": False,
                "error": type(exc).__name__,
                "detail": str(exc)[:200],
            }
        )
    finally:
        if uploaded_path:
            client.delete(uploaded_path)
    return result


async def main() -> None:
    print(
        json.dumps(
            {
                "database": check_database(),
                "blob": check_blob(),
                "telegram": await check_telegram(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
