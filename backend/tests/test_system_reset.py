import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.system import OperationalResetRequest, reset_project_operational_data
from app.core.security import get_password_hash
from app.db.database import Base
from app.models.user import Division, FeatureFlag, Project, Task, Tenant, User, UserRole
from app.services.system_reset import reset_operational_data


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed_operational_database(db):
    owner = User(
        name="System Owner",
        email="owner@rencanix.test",
        password_hash=get_password_hash("owner-password-123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(owner)
    db.flush()
    project = Project(project_name="Demo Project", owner_id=owner.id)
    db.add(project)
    db.flush()
    division = Division(division_name="Engineering", project_id=project.id, manager_id=owner.id)
    db.add(division)
    db.flush()
    owner.division_id = division.id
    db.add(Task(title="Review drawing", project_id=project.id, division_id=division.id, created_by=owner.id))
    db.add(FeatureFlag(feature_key="dashboard", label="Dashboard", category="core", is_core=True))
    db.add(Tenant(name="Rencanix Demo", slug="rencanix-demo", created_by=owner.id))
    db.commit()
    return owner


def test_reset_clears_operational_data_and_preserves_accounts_and_settings():
    db = build_database()
    owner = seed_operational_database(db)

    deleted = reset_operational_data(db)
    db.commit()

    assert deleted["tasks"] == 1
    assert deleted["projects"] == 1
    assert db.query(Project).count() == 0
    assert db.query(Division).count() == 0
    assert db.query(Task).count() == 0
    assert db.query(User).count() == 1
    assert db.get(User, owner.id).division_id is None
    assert db.query(FeatureFlag).count() == 1
    assert db.query(Tenant).count() == 1


def test_reset_endpoint_rejects_confirmation_that_is_not_exact():
    db = build_database()
    owner = seed_operational_database(db)

    with pytest.raises(HTTPException) as exc:
        reset_project_operational_data(
            payload=OperationalResetRequest(
                owner_email=owner.email,
                password="owner-password-123",
                confirmation="reset",
            ),
            db=db,
            current_user=owner,
        )

    assert exc.value.status_code == 400
    assert db.query(Project).count() == 1


def test_reset_endpoint_rejects_invalid_owner_password():
    db = build_database()
    owner = seed_operational_database(db)

    with pytest.raises(HTTPException) as exc:
        reset_project_operational_data(
            payload=OperationalResetRequest(
                owner_email=owner.email,
                password="wrong-password",
                confirmation="RESET DATA",
            ),
            db=db,
            current_user=owner,
        )

    assert exc.value.status_code == 403
    assert db.query(Project).count() == 1
