from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import (
    Division,
    Project,
    ProjectMembership,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskRequirement,
    TaskSpecification,
    TaskStatus,
    User,
    UserRole,
)
from app.services.telegram_auto_grouping import (
    auto_group_message,
    create_report_draft,
    merge_ai_report_fields,
    parse_report_fields,
)
from app.services.telegram_service import _get_active_report


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    manager = User(
        name="Manager Test",
        email="manager-telegram@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    staff = User(
        name="Staff Lapangan",
        email="staff-telegram@test.local",
        password_hash="x",
        role=UserRole.STAFF,
        telegram_id="770910605",
    )
    db.add_all([manager, staff])
    db.flush()

    project = Project(
        project_name="Gedung Test",
        status=ProjectStatus.ACTIVE,
        owner_id=manager.id,
    )
    db.add(project)
    db.flush()

    division = Division(
        project_id=project.id,
        division_name="Struktur",
        manager_id=manager.id,
    )
    db.add(division)
    db.flush()
    staff.division_id = division.id
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=staff.id,
        division_id=division.id,
        project_role="staff",
    ))

    pile_cap = Task(
        title="Pekerjaan pondasi pile cap zona A",
        description="Pembesian dan pengecoran pile cap",
        project_id=project.id,
        division_id=division.id,
        assigned_to=staff.id,
        created_by=manager.id,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
    )
    facade = Task(
        title="Pekerjaan fasad eksterior",
        description="Panel fasad dan finishing luar",
        project_id=project.id,
        division_id=division.id,
        assigned_to=staff.id,
        created_by=manager.id,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
    )
    db.add_all([pile_cap, facade])
    db.flush()
    db.add(TaskSpecification(
        task_id=pile_cap.id,
        wbs_code="WBS-STR-PILECAP-A",
        work_package="Pile cap zona A",
        location="Zona A",
        acceptance_criteria="Pembesian sesuai shop drawing dan beton siap inspeksi.",
        required_photo_count=2,
        required_document_count=1,
    ))
    db.add(TaskSpecification(
        task_id=facade.id,
        wbs_code="WBS-ARS-FACADE",
        work_package="Fasad eksterior",
        location="Tower",
        acceptance_criteria="Panel fasad terpasang sesuai elevasi.",
    ))
    db.add(TaskRequirement(
        task_id=pile_cap.id,
        code="REQ-BESI",
        title="Pembesian sesuai shop drawing",
        sequence=1,
    ))
    db.commit()
    return db, staff, pile_cap


def test_auto_group_message_selects_task_from_wbs_and_location():
    db, staff, pile_cap = build_database()

    result = auto_group_message(
        db,
        staff,
        "Progress: pembesian pile cap WBS-STR-PILECAP-A zona A sudah 80%. Pekerja: 6",
    )

    assert result.is_confident is True
    assert result.task.id == pile_cap.id
    assert result.confidence >= 0.45
    assert result.fields.manpower_count == 6
    assert "WBS cocok" in " ".join(result.reasons)


def test_parse_report_fields_keeps_decimal_wbs_code():
    fields = parse_report_fields(
        "Progress: pekerjaan pondasi pile cap WBS 1.02 sudah 80%. "
        "Pekerja: 6. Cuaca: cerah. Kendala: tidak ada."
    )

    assert "WBS 1.02" in fields.work_progress
    assert fields.manpower_count == 6
    assert fields.weather == "cerah"
    assert fields.issues == "tidak ada"


def test_parse_free_text_quantity_weather_and_manpower():
    fields = parse_report_fields(
        "Hari ini ngecat dinding lantai 2 sekitar 30 m2, 3 tukang, cuaca hujan, kendala cat kurang."
    )

    assert fields.actual_quantity == 30
    assert fields.actual_unit == "m2"
    assert fields.manpower_count == 3
    assert fields.weather == "hujan"
    assert fields.issues == "cat kurang"


def test_ai_payload_can_enrich_local_telegram_fields():
    fields = parse_report_fields("Progress pengecatan dinding selesai sebagian.")
    enriched = merge_ai_report_fields(fields, {
        "weather": "cerah",
        "manpower_count": 4,
        "actual_quantity": 12.5,
        "actual_unit": "m2",
        "work_progress": "Pengecatan dinding 12,5 m2.",
    })

    assert enriched.weather == "cerah"
    assert enriched.manpower_count == 4
    assert enriched.actual_quantity == 12.5
    assert enriched.actual_unit == "m2"


def test_create_report_draft_from_auto_grouping_result():
    db, staff, pile_cap = build_database()
    result = auto_group_message(
        db,
        staff,
        "Progress: pile cap zona A selesai pembesian. Pekerja: 6. REQ-BESI: ya",
    )

    report = create_report_draft(
        db=db,
        user=staff,
        task=result.task,
        fields=result.fields,
        telegram_message_id="123",
    )

    assert report.project_id == pile_cap.project_id
    assert report.workflow.task_id == pile_cap.id
    assert report.workflow.status.value == "draft"
    assert report.telegram_message_id == "123"
    assert len(report.requirement_checks) == 1
    assert report.requirement_checks[0].confirmed is True


def test_create_report_draft_adds_progress_entry_from_telegram_quantity():
    db, staff, pile_cap = build_database()
    result = auto_group_message(
        db,
        staff,
        "Progress: pile cap zona A selesai 5 m3. Pekerja: 6. REQ-BESI: ya",
    )

    report = create_report_draft(
        db=db,
        user=staff,
        task=result.task,
        fields=result.fields,
        telegram_message_id="124",
    )

    assert report.progress_entry.quantity_this_report == 5
    assert report.progress_entry.cost_this_report == 0


def test_active_report_falls_back_to_database_after_serverless_cold_start():
    db, staff, _ = build_database()
    result = auto_group_message(
        db,
        staff,
        "Progress: pile cap zona A selesai pembesian. Pekerja: 6. REQ-BESI: ya",
    )
    report = create_report_draft(db, staff, result.task, result.fields, "cold-start")

    class ContextWithoutMemory:
        user_data = {}

    recovered = _get_active_report(staff, ContextWithoutMemory(), db)

    assert recovered.id == report.id
    assert recovered.workflow.status.value == "draft"
