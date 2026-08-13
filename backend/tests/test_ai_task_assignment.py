from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.user import (
    Division,
    Project,
    ProjectMembership,
    Task,
    User,
    UserRole,
)
from app.services.project_staffing import resolve_task_project_role, select_task_pic


def build_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ai_role_is_resolved_and_least_loaded_member_is_selected():
    db = build_database()
    owner = User(name="Admin", email="admin@example.com", password_hash="x", role=UserRole.ADMIN)
    first = User(name="HSE Satu", email="hse1@example.com", password_hash="x", role=UserRole.STAFF)
    second = User(name="HSE Dua", email="hse2@example.com", password_hash="x", role=UserRole.STAFF)
    db.add_all([owner, first, second])
    db.flush()
    project = Project(project_name="Demo", owner_id=owner.id)
    db.add(project)
    db.flush()
    division = Division(project_id=project.id, division_name="HSE", manager_id=owner.id)
    db.add(division)
    db.flush()
    db.add_all([
        ProjectMembership(project_id=project.id, user_id=first.id, division_id=division.id, project_role="hse_officer"),
        ProjectMembership(project_id=project.id, user_id=second.id, division_id=division.id, project_role="hse_officer"),
    ])
    db.add(Task(title="Patrol sebelumnya", project_id=project.id, division_id=division.id, assigned_to=first.id, created_by=owner.id))
    db.commit()

    role = resolve_task_project_role(
        {"title": "Patrol keselamatan dan toolbox meeting", "division": "HSE"},
        {"hse_officer", "site_engineer"},
    )
    assignment = select_task_pic(db, project_id=project.id, requested_project_role=role)

    assert role == "hse_officer"
    assert assignment.user_id == second.id


def test_non_pic_role_cannot_receive_ai_task():
    db = build_database()
    assert select_task_pic(db, project_id=1, requested_project_role="viewer") is None
