import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.tasks import _validate_task_classification, list_tasks
from app.db.database import Base
from app.models.user import (
    Division, Project, ProjectMembership, ProjectStatus, Task, TaskPriority,
    TaskStatus, User, UserRole,
)


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    owner = User(
        name="Manager Test",
        email="manager-classification@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db.add(owner)
    db.flush()
    first_project = Project(
        project_name="Proyek A",
        status=ProjectStatus.ACTIVE,
        owner_id=owner.id,
    )
    second_project = Project(
        project_name="Proyek B",
        status=ProjectStatus.ACTIVE,
        owner_id=owner.id,
    )
    db.add_all([first_project, second_project])
    db.flush()
    division = Division(
        project_id=first_project.id,
        division_name="Struktur",
    )
    db.add(division)
    db.commit()
    return db, first_project, second_project, division


def test_accepts_division_from_same_project():
    db, project, _, division = build_database()

    _validate_task_classification(
        db, project_id=project.id, division_id=division.id
    )


def test_rejects_division_from_another_project():
    db, _, project, division = build_database()

    with pytest.raises(HTTPException) as error:
        _validate_task_classification(
            db, project_id=project.id, division_id=division.id
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Divisi yang dipilih tidak berasal dari proyek task"


def test_accepts_pic_from_task_division_membership():
    db, project, _, division = build_database()
    staff = User(
        name="Staff Struktur",
        email="staff-structure@test.local",
        password_hash="x",
        role=UserRole.STAFF,
    )
    db.add(staff)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=staff.id,
        division_id=division.id,
        project_role="staff",
    ))
    db.commit()

    _validate_task_classification(
        db,
        project_id=project.id,
        division_id=division.id,
        assigned_to=staff.id,
    )


def test_accepts_cross_division_pic_role():
    db, project, _, division = build_database()
    finance = User(
        name="Finance Manager",
        email="finance-manager@test.local",
        password_hash="x",
        role=UserRole.STAFF,
    )
    db.add(finance)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=finance.id,
        division_id=None,
        project_role="finance_manager",
    ))
    db.commit()

    _validate_task_classification(
        db,
        project_id=project.id,
        division_id=division.id,
        assigned_to=finance.id,
    )


def test_rejects_non_pic_project_role():
    db, project, _, division = build_database()
    vendor = User(
        name="Vendor Viewer",
        email="vendor-viewer@test.local",
        password_hash="x",
        role=UserRole.SUBCONTRACTOR,
    )
    db.add(vendor)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=vendor.id,
        division_id=None,
        project_role="vendor",
    ))
    db.commit()

    with pytest.raises(HTTPException) as error:
        _validate_task_classification(
            db,
            project_id=project.id,
            division_id=division.id,
            assigned_to=vendor.id,
        )

    assert error.value.status_code == 400
    assert "tidak dapat menjadi PIC task" in error.value.detail


def test_rejects_pic_without_project_membership():
    db, project, _, division = build_database()
    staff = User(
        name="Staff Belum Ditempatkan",
        email="staff-unassigned@test.local",
        password_hash="x",
        role=UserRole.STAFF,
    )
    db.add(staff)
    db.commit()

    with pytest.raises(HTTPException) as error:
        _validate_task_classification(
            db,
            project_id=project.id,
            division_id=division.id,
            assigned_to=staff.id,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "PIC belum menjadi anggota aktif proyek"


def test_division_scope_returns_only_staff_division_tasks():
    db, project, _, division = build_database()
    other_division = Division(project_id=project.id, division_name="MEP")
    staff = User(
        name="Staff Struktur",
        email="staff-division-scope@test.local",
        password_hash="x",
        role=UserRole.STAFF,
        division_id=division.id,
    )
    db.add_all([other_division, staff])
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=staff.id,
        division_id=division.id,
        project_role="staff",
    ))
    visible_task = Task(
        title="Pekerjaan divisi struktur",
        project_id=project.id,
        division_id=division.id,
        assigned_to=None,
        created_by=project.owner_id,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
    )
    hidden_task = Task(
        title="Pekerjaan divisi MEP",
        project_id=project.id,
        division_id=other_division.id,
        assigned_to=None,
        created_by=project.owner_id,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
    )
    db.add_all([visible_task, hidden_task])
    db.commit()

    result = list_tasks(
        project_id=None,
        division_id=None,
        assigned_to=None,
        status=None,
        scope="division",
        db=db,
        current_user=staff,
    )

    assert [task.title for task in result] == ["Pekerjaan divisi struktur"]