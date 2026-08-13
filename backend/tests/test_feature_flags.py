import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.settings import update_feature_flag
from app.db.database import Base
from app.models.user import AuditLog, FeatureFlag, User, UserRole
from app.schemas.schemas import FeatureFlagUpdate
from app.services.feature_flags import bootstrap_feature_flags


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = User(
        name="Platform Owner",
        email="owner-feature@test.local",
        password_hash="x",
        role=UserRole.OWNER,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return db, admin


def test_bootstrap_feature_flags_creates_core_and_menu_flags():
    db, _ = build_database()

    bootstrap_feature_flags(db)

    flags = db.query(FeatureFlag).all()
    dashboard = db.query(FeatureFlag).filter(FeatureFlag.feature_key == "dashboard").first()
    admin_console = db.query(FeatureFlag).filter(FeatureFlag.feature_key == "admin_console").first()
    communications = db.query(FeatureFlag).filter(FeatureFlag.feature_key == "communications").first()

    assert len(flags) >= 20
    assert dashboard is not None and dashboard.is_core is True and dashboard.enabled is True
    assert admin_console is not None and admin_console.is_core is True and admin_console.enabled is True
    assert communications is not None and communications.category == "communication"


def test_owner_can_toggle_non_core_feature_and_audit_is_written():
    db, admin = build_database()
    bootstrap_feature_flags(db)

    updated = update_feature_flag("telegram", FeatureFlagUpdate(enabled=False), db, admin)

    audit = db.query(AuditLog).filter(AuditLog.action == "settings.feature_updated").first()
    assert updated.enabled is False
    assert updated.updated_by == admin.id
    assert audit is not None
    assert audit.entity_type == "feature_flag"
    assert audit.entity_id == "telegram"


def test_core_feature_cannot_be_disabled():
    db, admin = build_database()
    bootstrap_feature_flags(db)

    with pytest.raises(HTTPException) as exc:
        update_feature_flag("admin_console", FeatureFlagUpdate(enabled=False), db, admin)

    assert exc.value.status_code == 409
