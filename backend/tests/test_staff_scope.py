from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.communications import (
    create_communication,
    escalate_communication,
    update_communication,
)
from app.api.v1.endpoints.projects import list_divisions, list_project_members
from app.db.database import Base
from app.models.user import (
    CommunicationItem,
    CommunicationStatus,
    CommunicationType,
    Division,
    Project,
    ProjectMembership,
    ProjectStatus,
    Task,
    TaskPriority,
    User,
    UserRole,
)
from app.schemas.schemas import (
    CommunicationCreate,
    CommunicationEscalateRequest,
    CommunicationUpdate,
)


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        name="Manager Scope", email="manager-scope@test.local",
        password_hash="x", role=UserRole.MANAGER,
    )
    staff = User(
        name="Staff Scope", email="staff-scope@test.local",
        password_hash="x", role=UserRole.STAFF,
    )
    peer = User(
        name="Peer Scope", email="peer-scope@test.local",
        password_hash="x", role=UserRole.STAFF,
    )
    other_peer = User(
        name="Other Scope", email="other-scope@test.local",
        password_hash="x", role=UserRole.STAFF,
    )
    db.add_all([manager, staff, peer, other_peer])
    db.flush()
    project = Project(
        project_name="Staff Scope Project",
        status=ProjectStatus.ACTIVE,
        owner_id=manager.id,
    )
    db.add(project)
    db.flush()
    division_a = Division(project_id=project.id, division_name="Struktur")
    division_b = Division(project_id=project.id, division_name="MEP")
    db.add_all([division_a, division_b])
    db.flush()
    db.add_all([
        ProjectMembership(
            project_id=project.id,
            user_id=staff.id,
            division_id=division_a.id,
            project_role="staff",
        ),
        ProjectMembership(
            project_id=project.id,
            user_id=peer.id,
            division_id=division_a.id,
            project_role="staff",
        ),
        ProjectMembership(
            project_id=project.id,
            user_id=other_peer.id,
            division_id=division_b.id,
            project_role="staff",
        ),
        ProjectMembership(
            project_id=project.id,
            user_id=manager.id,
            division_id=None,
            project_role="project_manager",
        ),
    ])
    task = Task(
        title="Task divisi struktur",
        project_id=project.id,
        division_id=division_a.id,
        assigned_to=staff.id,
        created_by=manager.id,
        priority=TaskPriority.HIGH,
    )
    db.add(task)
    db.flush()
    item = CommunicationItem(
        project_id=project.id,
        created_by=staff.id,
        assigned_to=manager.id,
        communication_type=CommunicationType.ISSUE,
        status=CommunicationStatus.OPEN,
        priority=TaskPriority.HIGH,
        subject="Issue divisi struktur",
        related_task_id=task.id,
        due_date=datetime.utcnow() + timedelta(days=1),
    )
    db.add(item)
    db.commit()
    return db, manager, staff, peer, other_peer, project, division_a, division_b, task, item


def test_staff_divisions_and_members_are_limited_to_membership_division():
    db, _, staff, peer, other_peer, project, division_a, _, _, _ = build_database()

    divisions = list_divisions(project.id, db, staff)
    members = list_project_members(project.id, None, db, staff)

    assert [division.id for division in divisions] == [division_a.id]
    visible_user_ids = {member["user_id"] for member in members}
    assert visible_user_ids == {staff.id, peer.id}
    assert other_peer.id not in visible_user_ids


def test_staff_communication_must_be_related_to_accessible_task():
    db, _, staff, _, _, project, _, _, task, _ = build_database()

    with pytest.raises(HTTPException) as missing_task_error:
        create_communication(
            CommunicationCreate(
                project_id=project.id,
                communication_type=CommunicationType.ISSUE,
                priority=TaskPriority.HIGH,
                subject="Issue tanpa task",
            ),
            db,
            staff,
        )

    created = create_communication(
        CommunicationCreate(
            project_id=project.id,
            communication_type=CommunicationType.ISSUE,
            priority=TaskPriority.HIGH,
            subject="Issue dengan task",
            related_task_id=task.id,
        ),
        db,
        staff,
    )

    assert missing_task_error.value.status_code == 400
    assert created["related_task_id"] == task.id


def test_staff_cannot_close_or_reassign_communication():
    db, _, staff, peer, _, _, _, _, _, item = build_database()

    with pytest.raises(HTTPException) as close_error:
        update_communication(
            item.id,
            CommunicationUpdate(status=CommunicationStatus.CLOSED),
            db,
            staff,
        )
    with pytest.raises(HTTPException) as reassign_error:
        escalate_communication(
            item.id,
            CommunicationEscalateRequest(
                reason="Butuh eskalasi ke peer",
                assigned_to=peer.id,
            ),
            db,
            staff,
        )

    assert close_error.value.status_code == 403
    assert reassign_error.value.status_code == 403