"""Impor files.zip MNBC ke DATABASE_URL yang aktif."""
import argparse
import json
import sys
from pathlib import Path

from app.core.config import settings
from app.db.database import SessionLocal, create_tables
from app.services.mnbc_dataset import import_mnbc_demo


def main() -> int:
    parser = argparse.ArgumentParser(description="Import dataset demo MNBC-2025")
    parser.add_argument("zip_path", type=Path, help="Lokasi files.zip")
    args = parser.parse_args()

    if not args.zip_path.is_file():
        print(f"Dataset tidak ditemukan: {args.zip_path}")
        return 1
    if len(settings.DEMO_ADMIN_PASSWORD) < 12:
        print("Isi DEMO_ADMIN_PASSWORD minimal 12 karakter melalui environment/.env.")
        return 1

    create_tables()
    db = SessionLocal()
    try:
        result = import_mnbc_demo(
            db,
            args.zip_path.read_bytes(),
            admin_email=settings.DEMO_ADMIN_EMAIL,
            admin_password=settings.DEMO_ADMIN_PASSWORD,
            telegram_id=settings.DEMO_TELEGRAM_ID or None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Import gagal: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
