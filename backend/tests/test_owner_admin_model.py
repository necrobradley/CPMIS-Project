import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints import system as system_endpoint
from app.api.v1.endpoints.system import OwnerBootstrapRequest, bootstrap_owner
from app.core.config import settings
from app.db.database import Base
from app.models.user import User, UserRole


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_owner_can_only_be_provisioned_once(monkeypatch):
    db = build_database()
    monkeypatch.setattr(settings, "BOOTSTRAP_SECRET", "owner-bootstrap-secret")
    monkeypatch.setattr(system_endpoint, "transactional_email_configured", lambda: True)
    monkeypatch.setattr(system_endpoint, "send_verification_email", lambda user, token: (True, None))
    payload = OwnerBootstrapRequest(
        name="Rencanix Platform Owner",
        email="owner@rencanix.example.com",
        password="OwnerPassword123",
    )

    created = bootstrap_owner(payload, "owner-bootstrap-secret", db)

    assert created["role"] == UserRole.OWNER
    assert db.query(User).filter(User.role == UserRole.OWNER).count() == 1
    with pytest.raises(HTTPException) as exc:
        bootstrap_owner(payload, "owner-bootstrap-secret", db)
    assert exc.value.status_code == 409
    assert "tidak dapat dibuat ulang" in exc.value.detail


def test_project_admin_role_remains_distinct_from_owner():
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.OWNER.value == "owner"


def test_owner_is_not_created_without_transactional_email(monkeypatch):
    db = build_database()
    monkeypatch.setattr(settings, "BOOTSTRAP_SECRET", "owner-bootstrap-secret")
    monkeypatch.setattr(system_endpoint, "transactional_email_configured", lambda: False)
    payload = OwnerBootstrapRequest(
        name="Rencanix Platform Owner",
        email="owner@rencanix.example.com",
        password="OwnerPassword123",
    )

    with pytest.raises(HTTPException) as exc:
        bootstrap_owner(payload, "owner-bootstrap-secret", db)

    assert exc.value.status_code == 503
    assert db.query(User).filter(User.role == UserRole.OWNER).count() == 0
