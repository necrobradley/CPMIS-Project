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
from app.models.user import Division, Project, ProjectMembership, User, UserRole
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
    db.flush()
    project = Project(project_name="Admin Project", owner_id=admin.id)
    db.add(project)
    db.flush()
    division = Division(division_name="Project Team", project_id=project.id)
    db.add(division)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=admin.id,
        project_role="project_admin",
        is_active=True,
    ))
    db.commit()
    db.refresh(admin)
    return db, admin, project, division


@pytest.mark.asyncio
async def test_admin_imports_employee_csv_and_creates_email_invitation():
    db, admin, project, division = build_database()
    csv_text = (
        "name,email,role,phone,project_id,project_division_id,project_role\n"
        f"Imported Staff,imported.staff@example.com,staff,08123,{project.id},{division.id},site_engineer\n"
    )
    upload = UploadFile(filename="employees.csv", file=BytesIO(csv_text.encode("utf-8")))

    result = await import_users_from_csv(upload, db, admin)
    user = db.query(User).filter(User.email == "imported.staff@example.com").first()

    assert result["created"] == 1
    assert result["results"][0]["status"] == "created"
    assert "temporary_password" not in result["results"][0]
    assert user is not None
    assert user.role == UserRole.STAFF
    assert user.must_set_password is True
    assert user.email_verification_required is True
    assert user.email_verified_at is None


def test_user_can_change_own_password():
    db, admin, _, _ = build_database()

    result = change_my_password(
        PasswordChangeRequest(current_password="admin1234", new_password="NewPassword123"),
        db,
        admin,
    )

    db.refresh(admin)
    assert result == {"success": True}
    assert verify_password("NewPassword123", admin.password_hash)


def test_user_change_password_rejects_wrong_current_password():
    db, admin, _, _ = build_database()

    with pytest.raises(HTTPException) as exc:
        change_my_password(
            PasswordChangeRequest(current_password="wrongpass", new_password="NewPassword123"),
            db,
            admin,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_user_can_upload_profile_avatar(monkeypatch):
    db, admin, _, _ = build_database()
    uploaded = {}
    monkeypatch.setattr(
        users_endpoint.storage_service,
        "upload_file",
        lambda content, object_name, content_type: uploaded.update({
            "content": content,
            "object_name": object_name,
            "content_type": content_type,
        }) or object_name,
    )
    upload = UploadFile(
        filename="avatar.png",
        file=BytesIO(b"fake-png"),
        headers=Headers({"content-type": "image/png"}),
    )

    result = await upload_my_avatar(upload, db, admin)

    db.refresh(admin)
    assert result["avatar_url"].startswith(f"/api/v1/users/{admin.id}/avatar/user-")
    assert admin.avatar_url == result["avatar_url"]
    assert uploaded["object_name"].startswith(f"avatars/user-{admin.id}-")
    assert uploaded["content"] == b"fake-png"
