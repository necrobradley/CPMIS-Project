from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import (
    DailyReport, DailyReportWorkflow, InspectionRequest, MaterialApproval, Project,
    ProductivityBenchmark, ProjectStatus, ReportProgressEntry, ReportStatus, Task, TaskControl,
    TaskDependency, TaskMaterialSpecification, TaskPriority, TaskStatus, User, UserRole,
    VendorProfile, VendorRateCard,
)
from app.services.project_controls import (
    apply_approved_report,
    my_work_summary,
    project_controls_summary,
    task_gate_snapshot,
    vendor_strategy_snapshot,
)


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        name="Manager Controls", email="manager-controls@test.local",
        password_hash="x", role=UserRole.MANAGER,
    )
    db.add(manager)
    db.flush()
    project = Project(
        project_name="Project Controls Test", status=ProjectStatus.ACTIVE,
        owner_id=manager.id,
    )
    db.add(project)
    db.flush()
    task = Task(
        title="Concrete work", project_id=project.id, created_by=manager.id,
        status=TaskStatus.TODO,
    )
    db.add(task)
    db.flush()
    control = TaskControl(
        task_id=task.id, unit="m3", planned_quantity=100,
        budget_cost=1_000_000,
    )
    material = TaskMaterialSpecification(
        task_id=task.id, material_name="Ready mix concrete",
        approval_required=True,
    )
    db.add_all([control, material])
    db.commit()
    return db, manager, project, task, material


def _add_control_tasks(db, manager, project, count=29):
    for index in range(count):
        db.add(Task(
            title=f"Control task {index}",
            project_id=project.id,
            created_by=manager.id,
            status=TaskStatus.TODO,
        ))
    db.commit()


def _count_sql_queries(db, callback):
    count = 0

    def before_cursor_execute(*args, **kwargs):
        nonlocal count
        count += 1

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        result = callback()
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)
    return result, count


def test_my_work_query_count_does_not_grow_per_task():
    db, manager, project, _, _ = build_database()
    _add_control_tasks(db, manager, project)

    result, query_count = _count_sql_queries(db, lambda: my_work_summary(db, manager))

    assert len(result["tasks"]) == 30
    assert query_count <= 25


def test_project_controls_summary_query_count_does_not_grow_per_task():
    db, manager, project, _, _ = build_database()
    _add_control_tasks(db, manager, project)

    result, query_count = _count_sql_queries(db, lambda: project_controls_summary(db, project))

    assert len(result["tasks"]) == 30
    assert query_count <= 40


def test_start_gate_requires_material_and_predecessor():
    db, manager, project, task, material = build_database()

    pending_gate = task_gate_snapshot(db, task)
    assert pending_gate["can_start"] is False
    assert "material_not_approved" in {item["code"] for item in pending_gate["start_blockers"]}

    db.add(MaterialApproval(
        material_id=material.id, status="approved",
        decided_by=manager.id, decided_at=datetime.utcnow(),
    ))
    predecessor = Task(
        title="Formwork", project_id=project.id, created_by=manager.id,
        status=TaskStatus.IN_PROGRESS,
    )
    db.add(predecessor)
    db.flush()
    db.add(TaskDependency(task_id=task.id, depends_on_task_id=predecessor.id))
    db.commit()

    dependency_gate = task_gate_snapshot(db, task)
    assert dependency_gate["can_start"] is False
    assert "dependency_incomplete" in {item["code"] for item in dependency_gate["start_blockers"]}

    predecessor.status = TaskStatus.DONE
    db.commit()
    assert task_gate_snapshot(db, task)["can_start"] is True


def test_approved_report_updates_volume_and_requires_passed_inspection():
    db, manager, project, task, material = build_database()
    db.add(MaterialApproval(
        material_id=material.id, status="approved",
        decided_by=manager.id, decided_at=datetime.utcnow(),
    ))
    report = DailyReport(
        project_id=project.id, user_id=manager.id,
        report_text="Concrete volume completed and measured.",
        manpower_count=10, work_progress="100 m3 completed",
    )
    db.add(report)
    db.flush()
    report.workflow = DailyReportWorkflow(
        task_id=task.id, status=ReportStatus.APPROVED,
        validation_passed=True, validation_score=100,
        approved_by=manager.id, approved_at=datetime.utcnow(),
    )
    report.progress_entry = ReportProgressEntry(
        task_id=task.id, quantity_this_report=100, cost_this_report=800_000,
    )
    task.status = TaskStatus.REVIEW
    db.commit()

    apply_approved_report(db, report, manager.id)
    db.commit()
    db.refresh(task)
    assert task.progress_percent == 100
    assert task.status == TaskStatus.REVIEW
    assert "inspection_missing" in {
        item["code"] for item in task_gate_snapshot(db, task)["completion_blockers"]
    }

    db.add(InspectionRequest(
        project_id=project.id, task_id=task.id, inspection_type="itp",
        title="Concrete ITP", status="passed", is_required=True,
        requested_by=manager.id, inspected_by=manager.id,
        inspected_at=datetime.utcnow(),
    ))
    db.commit()
    apply_approved_report(db, report, manager.id)
    db.commit()
    db.refresh(task)

    gate = task_gate_snapshot(db, task)
    assert gate["can_complete"] is True
    assert task.status == TaskStatus.DONE
    assert task.progress_percent == 100
    assert len(project.tasks) == 1


def test_make_or_buy_recommends_vendor_when_rate_is_more_profitable():
    db, manager, project, task, material = build_database()
    task.title = "Pemasangan fasad kaca aluminium"
    task.priority = TaskPriority.HIGH
    task.control.unit = "m2"
    task.control.planned_quantity = 700
    task.control.boq_value = 1_050_000_000
    task.control.budget_cost = 900_000_000
    task.control.internal_material_cost = 470_000_000
    task.control.internal_labor_cost = 185_000_000
    task.control.internal_equipment_cost = 95_000_000
    task.control.internal_overhead_cost = 72_000_000
    task.control.internal_risk_cost = 68_000_000
    vendor = VendorProfile(
        project_id=project.id,
        vendor_name="PT Fasad Test",
        specialty="facade",
        rating=90,
        quality_score=90,
        delivery_score=88,
        safety_score=86,
        capacity_score=88,
    )
    db.add(vendor)
    db.flush()
    db.add(VendorRateCard(
        vendor_id=vendor.id,
        work_category="facade",
        work_keywords="fasad,kaca,aluminium",
        unit="m2",
        unit_price=1_050_000,
        mobilization_cost=28_000_000,
        lead_time_days=14,
        includes_equipment=True,
        risk_multiplier=1.02,
    ))
    db.commit()

    gate = task_gate_snapshot(db, task)
    strategy = vendor_strategy_snapshot(task, task.control, gate, db)
    make_or_buy = strategy["make_or_buy"]

    assert make_or_buy["candidate_count"] == 1
    assert make_or_buy["best_vendor"]["vendor_name"] == "PT Fasad Test"
    assert make_or_buy["best_vendor"]["saving_vs_internal"] > 0
    assert make_or_buy["recommendation"] == "vendor_recommended"


def test_make_or_buy_prefers_internal_when_internal_cost_is_lower():
    db, manager, project, task, material = build_database()
    task.title = "Pemasangan rambu keselamatan"
    task.control.unit = "unit"
    task.control.planned_quantity = 50
    task.control.boq_value = 20_000_000
    task.control.internal_material_cost = 5_000_000
    task.control.internal_labor_cost = 2_000_000
    task.control.internal_equipment_cost = 500_000
    task.control.internal_overhead_cost = 500_000
    task.control.internal_risk_cost = 500_000
    vendor = VendorProfile(
        project_id=project.id,
        vendor_name="CV Safety Expensive",
        specialty="hse",
        rating=80,
        quality_score=80,
        delivery_score=80,
        safety_score=80,
        capacity_score=80,
    )
    db.add(vendor)
    db.flush()
    db.add(VendorRateCard(
        vendor_id=vendor.id,
        work_category="hse",
        work_keywords="rambu,safety,keselamatan",
        unit="unit",
        unit_price=350_000,
        mobilization_cost=2_000_000,
        lead_time_days=5,
    ))
    db.commit()

    gate = task_gate_snapshot(db, task)
    strategy = vendor_strategy_snapshot(task, task.control, gate, db)

    assert strategy["make_or_buy"]["candidate_count"] == 1
    assert strategy["make_or_buy"]["best_vendor"]["saving_vs_internal"] < 0
    assert strategy["make_or_buy"]["recommendation"] == "internal_preferred"


def test_make_or_buy_uses_productivity_benchmark_for_internal_cost():
    db, manager, project, task, material = build_database()
    task.title = "Pengecatan dinding lantai 2"
    task.description = "Pekerjaan cat finishing dinding interior"
    task.control.unit = "m2"
    task.control.planned_quantity = 300
    task.control.boq_value = 24_000_000
    db.add(ProductivityBenchmark(
        project_id=project.id,
        work_category="finishing",
        work_keywords="cat, pengecatan, dinding",
        unit="m2",
        output_per_day=30,
        crew_size=3,
        labor_cost_per_day=550_000,
        equipment_cost_per_day=75_000,
        material_cost_per_unit=23_000,
        overhead_percent=8,
        risk_percent=5,
        confidence_score=85,
        source_label="test-painting",
    ))
    vendor = VendorProfile(
        project_id=project.id,
        vendor_name="Vendor Cat Test",
        specialty="finishing",
        rating=80,
        quality_score=80,
        delivery_score=80,
        safety_score=80,
        capacity_score=80,
    )
    db.add(vendor)
    db.flush()
    db.add(VendorRateCard(
        vendor_id=vendor.id,
        work_category="finishing",
        work_keywords="cat, pengecatan, dinding",
        unit="m2",
        unit_price=55_000,
        mobilization_cost=1_000_000,
        lead_time_days=6,
    ))
    db.commit()

    gate = task_gate_snapshot(db, task)
    make_or_buy = vendor_strategy_snapshot(task, task.control, gate, db)["make_or_buy"]

    assert make_or_buy["internal"]["source"] == "productivity_benchmark"
    assert make_or_buy["internal"]["productivity_benchmark"]["duration_days"] == 10
    assert make_or_buy["productivity_benchmark"]["output_per_day"] == 30
    assert make_or_buy["candidate_count"] == 1
