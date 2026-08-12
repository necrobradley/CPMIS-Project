"""Uji satu model AI yang sudah dikonfigurasi tanpa membuka frontend."""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.services.ai_service import AIService


async def run(provider: str | None, model: str | None, message: str) -> int:
    try:
        response = await AIService().chat(
            message=message,
            context="Uji koneksi model untuk aplikasi CPMIS.",
            provider=provider,
            model=model,
        )
    except Exception as exc:
        print(f"Uji model gagal: {exc}")
        return 1

    print("Model merespons:\n")
    print(response)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Uji koneksi model AI CPMIS")
    parser.add_argument("--provider", default="mlapi", help="Provider, misalnya mlapi")
    parser.add_argument("--model", default=None, help="ID model dalam katalog")
    parser.add_argument(
        "--message",
        default="Jawab singkat: koneksi AI CPMIS berhasil.",
        help="Prompt uji yang dikirim ke model",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.provider, args.model, args.message))


if __name__ == "__main__":
    sys.exit(main())
