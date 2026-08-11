from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from app.api.v1.endpoints import users as users_endpoint
from app.api.v1.endpoints.users import change_my_password, import_users_from_csv, upload_my_avatar
from app.core.security import get_password_hash, verify_password
from app.db.database import Base
from app.models.user import User, UserRole
from app.schemas.schemas import PasswordChangeRequest


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = User(
        name="System Admin",
        email="admin-import@example.com",
        password_hash=get_password_hash("admin1234"),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return db, admin


@pytest.mark.asyncio
async def test_admin_imports_employee_csv_and_gets_temporary_password():
    db, admin = build_database()
    csv_text = "name,email,role,phone\nImported Staff,imported.staff@example.com,staff,08123\n"
    upload = UploadFile(filename="employees.csv", file=BytesIO(csv_text.encode("utf-8")))

    result = await import_users_from_csv(upload, db, admin)
    user = db.query(User).filter(User.email == "imported.staff@example.com").first()

    assert result["created"] == 1
    assert result["results"][0]["status"] == "created"
    assert len(result["results"][0]["temporary_password"]) >= 8
    assert user is not None
    assert user.role == UserRole.STAFF


def test_user_can_change_own_password():
    db, admin = build_database()

    result = change_my_password(
        PasswordChangeRequest(current_password="admin1234", new_password="newpass123"),
        db,
        admin,
    )

    db.refresh(admin)
    assert result == {"success": True}
    assert verify_password("newpass123", admin.password_hash)


def test_user_change_password_rejects_wrong_current_password():
    db, admin = build_database()

    with pytest.raises(HTTPException) as exc:
        change_my_password(
            PasswordChangeRequest(current_password="wrongpass", new_password="newpass123"),
            db,
            admin,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_user_can_upload_profile_avatar(tmp_path, monkeypatch):
    db, admin = build_database()
    monkeypatch.setattr(users_endpoint, "AVATAR_DIR", tmp_path)
    upload = UploadFile(
        filename="avatar.png",
        file=BytesIO(b"fake-png"),
        headers=Headers({"content-type": "image/png"}),
    )

    result = await upload_my_avatar(upload, db, admin)

    db.refresh(admin)
    assert result["avatar_url"].startswith("/uploads/avatars/user-")
    assert admin.avatar_url == result["avatar_url"]
    assert (tmp_path / result["avatar_url"].split("/")[-1]).exists()
