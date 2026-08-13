"""Safe owner-initiated reset of operational project data."""
from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.user import (
    CommunicationAttachment,
    DailyReport,
    Document,
    ReportEvidence,
    TaskAttachment,
    User,
)


PROTECTED_TABLES = {
    "users",
    "feature_flags",
    "tenants",
    "tenant_feature_entitlements",
    "tenant_usage_records",
}


def _operational_tables_in_delete_order():
    """Topologically order operational tables without the retained user cycle."""
    deferred = {"projects", "divisions"}
    tables = {
        table.name: table
        for table in Base.metadata.tables.values()
        if table.name not in PROTECTED_TABLES | deferred
    }
    dependencies = {
        name: {
            foreign_key.column.table.name
            for foreign_key in table.foreign_keys
            if foreign_key.column.table.name in tables and foreign_key.column.table.name != name
        }
        for name, table in tables.items()
    }
    insertion_order: list[str] = []
    remaining = set(tables)
    while remaining:
        ready = sorted(name for name in remaining if not (dependencies[name] & remaining))
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise RuntimeError(f"Siklus tabel operasional tidak dapat direset dengan aman: {cycle}")
        insertion_order.extend(ready)
        remaining.difference_update(ready)

    deletion_order = [tables[name] for name in reversed(insertion_order)]
    deletion_order.extend([Base.metadata.tables["divisions"], Base.metadata.tables["projects"]])
    return deletion_order


def _append_paths(target: set[str], values: Iterable[str | None]) -> None:
    for value in values:
        if value and value.strip():
            target.add(value.strip())


def collect_operational_storage_paths(db: Session) -> set[str]:
    """Collect private object paths before database rows are removed."""
    paths: set[str] = set()
    for model in (Document, ReportEvidence, CommunicationAttachment, TaskAttachment):
        _append_paths(paths, db.scalars(select(model.file_path)).all())

    for raw_value in db.scalars(select(DailyReport.photo_paths)).all():
        if not raw_value:
            continue
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            parsed = [raw_value]
        if isinstance(parsed, list):
            _append_paths(paths, (item for item in parsed if isinstance(item, str)))
    return paths


def reset_operational_data(db: Session) -> dict[str, int]:
    """Delete project activity while preserving accounts and platform settings.

    User accounts are deliberately retained so the owner can sign in again after
    the reset. Their division link is cleared before project divisions are removed.
    """
    db.execute(update(User).values(division_id=None))

    deleted: dict[str, int] = {}
    for table in _operational_tables_in_delete_order():
        result = db.execute(delete(table))
        deleted[table.name] = max(result.rowcount or 0, 0)
    db.flush()
    return deleted
