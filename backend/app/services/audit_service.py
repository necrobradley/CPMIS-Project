import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.user import AuditLog


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _dump(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def log_audit(
    db: Session,
    *,
    actor_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[Any] = None,
    project_id: Optional[int] = None,
    summary: Optional[str] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    channel: str = "web",
) -> AuditLog:
    audit = AuditLog(
        actor_id=actor_id,
        project_id=project_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        summary=summary,
        before_data=_dump(before),
        after_data=_dump(after),
        channel=channel,
    )
    db.add(audit)
    return audit
