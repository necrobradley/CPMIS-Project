import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.auth import register, router
from app.core.security import get_password_hash
from app.db.database import Base, get_db
from app.models.user import User, UserRole


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_public_register_is_closed_for_staff():
    db = build_database()

    with pytest.raises(HTTPException) as exc:
        await register()

    assert exc.value.status_code == 403
    assert "Aplikasi tertutup" in exc.value.detail


@pytest.mark.asyncio
async def test_public_register_rejects_director_role():
    db = build_database()

    with pytest.raises(HTTPException) as exc:
        await register()

    assert exc.value.status_code == 403
    assert "admin aplikasi" in exc.value.detail
    assert db.query(User).filter(User.email == "director-candidate@example.com").first() is None


def test_login_accepts_internal_demo_email_created_by_project_setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(
        User(
            name="Administrator Project",
            email="admin.project@demo.local",
            password_hash=get_password_hash("strong-password-123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    db.commit()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={
                "email": "admin.project@demo.local",
                "password": "strong-password-123",
            },
        )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
