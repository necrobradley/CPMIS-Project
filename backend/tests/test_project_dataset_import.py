from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.system import router
from app.core.config import settings
from app.core.security import get_current_user, get_password_hash, verify_password
from app.db.database import Base, get_db
from app.models.user import AuditLog, User, UserRole
from app.services import project_dataset


def build_app(role: UserRole):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(
        name="Admin Import Project",
        email=f"{role.value}@project.test",
        password_hash=get_password_hash("password123"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    return app, db, user


def test_admin_imports_project_from_website(monkeypatch):
    app, db, admin = build_app(UserRole.ADMIN)
    captured = {}

    def fake_import(db_session, content, **kwargs):
        captured.update(kwargs)
        assert db_session is db
        assert content == b"repacked-zip"
        return {
            "project_id": 7,
            "project_name": "Pembangunan Gedung Percontohan",
            "project_code": "PGP-2026",
            "admin_email": admin.email,
            "admin_created": False,
            "field_user_email": "staff.project@demo.local",
            "telegram_linked": True,
            "tasks_upserted": 400,
            "nodes_upserted": 1468,
            "relationships_upserted": 2689,
            "rules_upserted": 345,
            "reasoning_examples_upserted": 960,
        }

    monkeypatch.setattr(project_dataset, "import_project_dataset", fake_import)
    with TestClient(app) as client:
        response = client.post(
            "/system/import/project-dataset",
            files={"dataset": ("project-import.zip", b"repacked-zip", "application/zip")},
            data={"telegram_id": "770910605"},
        )

    assert response.status_code == 200
    assert response.json()["tasks_upserted"] == 400
    assert captured == {
        "admin_email": admin.email,
        "admin_password": "",
        "telegram_id": "770910605",
    }
    audit = db.query(AuditLog).filter(AuditLog.action == "system.project_dataset_imported").one()
    assert audit.actor_id == admin.id
    assert audit.project_id == 7


def test_non_admin_cannot_import_project_from_website():
    app, _, _ = build_app(UserRole.MANAGER)
    with TestClient(app) as client:
        response = client.post(
            "/system/import/project-dataset",
            files={"dataset": ("project-import.zip", b"zip", "application/zip")},
        )

    assert response.status_code == 403


def test_admin_import_rejects_non_zip_file():
    app, _, _ = build_app(UserRole.ADMIN)
    with TestClient(app) as client:
        response = client.post(
            "/system/import/project-dataset",
            files={"dataset": ("dataset.json", b"{}", "application/json")},
        )

    assert response.status_code == 400
    assert "ZIP" in response.json()["detail"]


def test_setup_page_bootstraps_project_with_secret(monkeypatch):
    app, _, _ = build_app(UserRole.ADMIN)
    monkeypatch.setattr(settings, "BOOTSTRAP_SECRET", "setup-secret")
    captured = {}

    def fake_import(_, content, **kwargs):
        captured.update(kwargs)
        assert content == b"compact-zip"
        return {"project_id": 1, "project_name": "Gedung Percontohan", "tasks_upserted": 400}

    monkeypatch.setattr(project_dataset, "import_project_dataset", fake_import)
    with TestClient(app) as client:
        response = client.post(
            "/system/bootstrap/project-dataset",
            headers={"X-Bootstrap-Secret": "setup-secret"},
            files={"dataset": ("project-import.zip", b"compact-zip", "application/zip")},
            data={
                "admin_email": "admin@example.com",
                "admin_password": "Strong-password-123",
                "telegram_id": "770910605",
            },
        )

    assert response.status_code == 200
    assert captured == {
        "admin_email": "admin@example.com",
        "admin_password": "Strong-password-123",
        "telegram_id": "770910605",
    }


def test_setup_page_rejects_wrong_bootstrap_secret(monkeypatch):
    app, _, _ = build_app(UserRole.ADMIN)
    monkeypatch.setattr(settings, "BOOTSTRAP_SECRET", "setup-secret")
    with TestClient(app) as client:
        response = client.post(
            "/system/bootstrap/project-dataset",
            headers={"X-Bootstrap-Secret": "wrong-secret"},
            files={"dataset": ("project-import.zip", b"compact-zip", "application/zip")},
            data={"admin_password": "strong-password-123"},
        )

    assert response.status_code == 403


def test_setup_replaces_password_for_an_existing_admin_account():
    app, db, admin = build_app(UserRole.ADMIN)
    del app

    project_dataset._upsert_core_project(
        db,
        {"project_summary": {"project_name": "Project Password Repair"}},
        admin_email=admin.email,
        admin_password="new-strong-password-123",
        telegram_id=None,
    )
    db.refresh(admin)

    assert verify_password("new-strong-password-123", admin.password_hash)
