from copy import deepcopy
from types import SimpleNamespace

from app.api.v1.endpoints.controls import _scope_summary_for_user
from app.models.user import TaskStatus, UserRole
from app.services.report_workflow import can_access_project, can_access_task


def build_access_fixture():
    staff = SimpleNamespace(id=7, role=UserRole.STAFF)
    manager = SimpleNamespace(id=8, role=UserRole.MANAGER)
    project_manager = SimpleNamespace(id=9, role=UserRole.MANAGER)
    admin = SimpleNamespace(id=10, role=UserRole.ADMIN)

    project = SimpleNamespace(
        id=1,
        owner_id=99,
        memberships=[],
        divisions=[],
        tasks=[],
        daily_reports=[],
    )
    division_a = SimpleNamespace(id=11, manager_id=None)
    division_b = SimpleNamespace(id=12, manager_id=None)
    project.divisions = [division_a, division_b]
    project.memberships = [
        SimpleNamespace(
            user_id=staff.id,
            division_id=division_a.id,
            project_role="staff",
            is_active=True,
        ),
        SimpleNamespace(
            user_id=project_manager.id,
            division_id=None,
            project_role="project_manager",
            is_active=True,
        ),
    ]

    task_a = SimpleNamespace(
        id=101,
        project=project,
        division=division_a,
        division_id=division_a.id,
        assigned_to=None,
        created_by=99,
    )
    task_b = SimpleNamespace(
        id=102,
        project=project,
        division=division_b,
        division_id=division_b.id,
        assigned_to=None,
        created_by=99,
    )
    project.tasks = [task_a, task_b]
    return staff, manager, project_manager, admin, project, task_a, task_b


def test_project_access_is_not_global_for_manager():
    staff, manager, project_manager, admin, project, _, _ = build_access_fixture()

    assert can_access_project(staff, project) is True
    assert can_access_project(project_manager, project) is True
    assert can_access_project(manager, project) is False
    assert can_access_project(admin, project) is True


def test_staff_task_access_is_limited_to_division_or_assignment():
    staff, _, project_manager, _, _, task_a, task_b = build_access_fixture()

    assert can_access_task(staff, task_a) is True
    assert can_access_task(staff, task_b) is False
    assert can_access_task(project_manager, task_b) is True

    task_b.assigned_to = staff.id
    assert can_access_task(staff, task_b) is True


def test_staff_controls_summary_filters_tasks_and_masks_financials():
    staff, _, _, _, project, _, _ = build_access_fixture()
    summary = {
        "project": {"contract_value": 8_000_000_000},
        "metrics": {
            "budget_cost": 3_000_000_000,
            "actual_cost": 1_500_000_000,
        },
        "tasks": [
            {
                "id": 101,
                "status": TaskStatus.IN_PROGRESS.value,
                "budget_cost": 2_000_000_000,
                "actual_cost": 1_000_000_000,
                "gate": {"start_blockers": [], "completion_blockers": []},
            },
            {
                "id": 102,
                "status": TaskStatus.BLOCKED.value,
                "budget_cost": 1_000_000_000,
                "actual_cost": 500_000_000,
                "gate": {"start_blockers": [], "completion_blockers": []},
            },
        ],
        "lookahead": [
            {"id": 101, "budget_cost": 2_000_000_000, "actual_cost": 1_000_000_000},
            {"id": 102, "budget_cost": 1_000_000_000, "actual_cost": 500_000_000},
        ],
        "materials": [
            {"task_id": 101, "status": "approved"},
            {"task_id": 102, "status": "pending"},
        ],
        "inspections": [
            {"task_id": 101, "status": "pending"},
            {"task_id": 102, "status": "passed"},
        ],
        "ncrs": [
            {"task_id": 101, "status": "open"},
            {"task_id": 102, "status": "closed"},
        ],
        "overdue_rfis": [],
        "handover": [
            {"task_id": 101},
            {"task_id": 102},
        ],
    }

    scoped = _scope_summary_for_user(deepcopy(summary), project, staff)

    assert [item["id"] for item in scoped["tasks"]] == [101]
    assert scoped["project"]["contract_value"] is None
    assert scoped["metrics"]["budget_cost"] == 0
    assert scoped["metrics"]["actual_cost"] == 0
    assert scoped["tasks"][0]["budget_cost"] == 0
    assert scoped["tasks"][0]["actual_cost"] == 0
    assert scoped["metrics"]["task_count"] == 1


def test_finance_project_role_can_view_project_cost_controls():
    staff, _, _, _, project, _, _ = build_access_fixture()
    finance_user = SimpleNamespace(id=11, role=UserRole.STAFF)
    project.memberships.append(SimpleNamespace(
        user_id=finance_user.id,
        division_id=None,
        project_role="finance_manager",
        is_active=True,
    ))
    summary = {
        "project": {"contract_value": 8_000_000_000},
        "metrics": {
            "budget_cost": 3_000_000_000,
            "actual_cost": 1_500_000_000,
        },
        "tasks": [
            {
                "id": 101,
                "status": TaskStatus.IN_PROGRESS.value,
                "budget_cost": 2_000_000_000,
                "actual_cost": 1_000_000_000,
                "gate": {"start_blockers": [], "completion_blockers": []},
            },
            {
                "id": 102,
                "status": TaskStatus.BLOCKED.value,
                "budget_cost": 1_000_000_000,
                "actual_cost": 500_000_000,
                "gate": {"start_blockers": [], "completion_blockers": []},
            },
        ],
        "lookahead": [
            {"id": 101, "budget_cost": 2_000_000_000, "actual_cost": 1_000_000_000},
            {"id": 102, "budget_cost": 1_000_000_000, "actual_cost": 500_000_000},
        ],
        "materials": [],
        "inspections": [],
        "ncrs": [],
        "overdue_rfis": [],
        "handover": [],
    }

    scoped = _scope_summary_for_user(deepcopy(summary), project, finance_user)

    assert [item["id"] for item in scoped["tasks"]] == [101, 102]
    assert scoped["project"]["contract_value"] == 8_000_000_000
    assert scoped["metrics"]["budget_cost"] == 3_000_000_000
    assert scoped["metrics"]["actual_cost"] == 1_500_000_000