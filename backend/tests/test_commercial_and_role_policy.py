import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.projects import (
    add_project_member,
    create_project,
    list_project_role_policy,
    update_project_role_policy,
)
from app.api.v1.endpoints.settings import create_commercial_tenant, list_tenant_entitlements
from app.api.v1.endpoints.users import create_user_with_project_setup, update_user_project_setup
from app.db.database import Base
from app.models.user import Division, FeatureFlag, Project, ProjectMembership, ProjectRolePolicy, User, UserRole
from app.schemas.schemas import (
    CommercialTenantCreate,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectRolePolicyUpdate,
    UserProjectSetupCreate,
    UserProjectSetupUpdate,
)
from app.services.feature_flags import bootstrap_feature_flags


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = User(
        name="System Admin",
        email="admin-commercial@test.local",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    staff = User(
        name="Field Staff",
        email="field-staff@test.local",
        password_hash="x",
        role=UserRole.STAFF,
    )
    project = Project(project_name="Policy Project", owner_id=admin.id)
    db.add_all([admin, staff])
    db.flush()
    project.owner_id = admin.id
    db.add(project)
    db.commit()
    db.refresh(admin)
    db.refresh(staff)
    db.refresh(project)
    return db, admin, staff, project


def test_commercial_tenant_bootstraps_entitlements_and_limits():
    db, admin, _, _ = build_database()
    bootstrap_feature_flags(db)

    tenant = create_commercial_tenant(
        CommercialTenantCreate(name="PT Pilot CPMIS", plan_key="starter"),
        db,
        admin,
    )
    entitlements = list_tenant_entitlements(tenant.id, db, admin)
    dashboard = next(item for item in entitlements if item["feature_key"] == "dashboard")
    telegram = next(item for item in entitlements if item["feature_key"] == "telegram")

    assert tenant.slug == "pt-pilot-cpmis"
    assert tenant.max_users == 25
    assert dashboard["enabled"] is True
    assert telegram["enabled"] is False


def test_project_role_policy_blocks_disabled_role_for_new_member():
    db, admin, staff, project = build_database()
    policies = list_project_role_policy(project.id, db, admin)
    site_engineer = next(item for item in policies if item["code"] == "site_engineer")

    updated = update_project_role_policy(
        project.id,
        "site_engineer",
        ProjectRolePolicyUpdate(enabled=False),
        db,
        admin,
    )

    assert site_engineer["enabled"] is True
    assert updated["enabled"] is False
    assert db.query(ProjectRolePolicy).filter_by(project_id=project.id, role_code="site_engineer").first() is not None
    with pytest.raises(HTTPException) as exc:
        add_project_member(
            project.id,
            ProjectMemberCreate(user_id=staff.id, division_id=None, project_role="site_engineer"),
            db,
            admin,
        )
    assert exc.value.status_code == 409


def test_only_app_admin_can_update_project_role_policy():
    db, _, _, project = build_database()
    manager = User(
        name="Project Manager",
        email="project-manager@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)

    with pytest.raises(HTTPException) as exc:
        update_project_role_policy(
            project.id,
            "site_engineer",
            ProjectRolePolicyUpdate(enabled=False),
            db,
            manager,
        )

    assert exc.value.status_code == 403
    assert "admin aplikasi" in exc.value.detail


def test_non_app_admin_cannot_assign_project_admin_role():
    db, _, staff, project = build_database()
    manager = User(
        name="Project Manager",
        email="project-manager@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db.add(manager)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=manager.id,
        project_role="division_lead",
        is_active=True,
    ))
    db.commit()
    db.refresh(manager)

    with pytest.raises(HTTPException) as exc:
        add_project_member(
            project.id,
            ProjectMemberCreate(user_id=staff.id, division_id=None, project_role="project_admin"),
            db,
            manager,
        )

    assert exc.value.status_code == 403
    assert "admin proyek" in exc.value.detail


def test_app_admin_creating_project_does_not_become_project_admin():
    db, admin, _, _ = build_database()

    project = create_project(
        ProjectCreate(project_name="Separated Admin Project"),
        db,
        admin,
    )
    membership = db.query(ProjectMembership).filter_by(
        project_id=project["id"],
        user_id=admin.id,
    ).first()

    assert project["project_name"] == "Separated Admin Project"
    assert membership is None


def test_app_admin_account_cannot_be_project_admin_membership():
    db, admin, _, project = build_database()

    with pytest.raises(HTTPException) as exc:
        create_user_with_project_setup(
            UserProjectSetupCreate(
                name="Second App Admin",
                email="second-admin@example.com",
                password="dummy1234",
                role=UserRole.ADMIN,
                project_id=project.id,
                project_role="project_admin",
            ),
            db,
            admin,
        )

    assert exc.value.status_code == 400
    assert "tidak boleh dirangkap" in exc.value.detail


def test_admin_setup_creates_user_and_project_membership():
    db, admin, _, project = build_database()
    division = Division(division_name="QA/QC", project_id=project.id)
    db.add(division)
    db.commit()
    db.refresh(division)

    result = create_user_with_project_setup(
        UserProjectSetupCreate(
            name="QA Dummy",
            email="qa-dummy@example.com",
            password="dummy1234",
            role=UserRole.STAFF,
            telegram_id="770910605",
            project_id=project.id,
            project_division_id=division.id,
            project_role="qa_qc_engineer",
        ),
        db,
        admin,
    )
    membership = db.query(ProjectMembership).filter_by(user_id=result["user"]["id"], project_id=project.id).first()

    assert result["user"]["email"] == "qa-dummy@example.com"
    assert result["membership"]["project_role"] == "qa_qc_engineer"
    assert membership is not None
    assert membership.division_id == division.id


def test_admin_setup_updates_existing_user_project_assignment():
    db, admin, staff, project = build_database()
    division = Division(division_name="Engineering", project_id=project.id)
    db.add(division)
    db.commit()
    db.refresh(division)

    result = update_user_project_setup(
        staff.id,
        UserProjectSetupUpdate(
            role=UserRole.MANAGER,
            telegram_id="770910605",
            project_id=project.id,
            project_division_id=division.id,
            project_role="site_engineer",
        ),
        db,
        admin,
    )
    membership = db.query(ProjectMembership).filter_by(user_id=staff.id, project_id=project.id).first()

    assert result["user"]["role"] == UserRole.MANAGER
    assert result["user"]["telegram_id"] == "770910605"
    assert result["membership"]["project_role"] == "site_engineer"
    assert membership is not None
    assert membership.division_id == division.id
