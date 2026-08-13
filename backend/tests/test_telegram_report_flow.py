from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.user import (
    DailyReport,
    Division,
    EvidenceType,
    Project,
    ProjectMembership,
    ReportEvidence,
    Task,
    TaskControl,
    TaskRequirement,
    TaskSpecification,
    TaskStatus,
    User,
    UserRole,
)
from app.services import telegram_service


class FakeTelegramFile:
    async def download_as_bytearray(self):
        return bytearray(b"fake-jpeg")


class FakeBot:
    async def get_file(self, _file_id):
        return FakeTelegramFile()


class FakeMessage:
    def __init__(self, text="", *, caption=None, with_photo=False):
        self.text = text
        self.caption = caption
        self.photo = [SimpleNamespace(file_id="photo-1")] if with_photo else []
        self.message_id = 7001
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append({"text": text, **kwargs})


class FakeCallbackQuery:
    def __init__(self, data):
        self.data = data
        self.edits = []

    async def answer(self):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append({"text": text, **kwargs})


class FakeUpdate:
    def __init__(self, telegram_id, *, text="", callback_data=None, caption=None, with_photo=False):
        self.effective_user = SimpleNamespace(id=telegram_id)
        self.message = FakeMessage(text, caption=caption, with_photo=with_photo)
        self.callback_query = FakeCallbackQuery(callback_data) if callback_data else None


class FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot = FakeBot()


def build_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    manager = User(
        name="MEP Lead",
        email="mep.lead@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
        telegram_id="9002",
    )
    staff = User(
        name="Demo MEP Engineer",
        email="mep.engineer@test.local",
        password_hash="x",
        role=UserRole.STAFF,
        telegram_id="9001",
    )
    db.add_all([manager, staff])
    db.flush()
    project = Project(project_name="Demo MEP", owner_id=manager.id)
    db.add(project)
    db.flush()
    division = Division(project_id=project.id, division_name="MEP", manager_id=manager.id)
    db.add(division)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=staff.id,
        division_id=division.id,
        project_role="mep_engineer",
    ))
    assigned_first = Task(
        title="Instalasi pipa air bersih",
        project_id=project.id,
        division_id=division.id,
        assigned_to=staff.id,
        created_by=manager.id,
        status=TaskStatus.TODO,
    )
    assigned_selected = Task(
        title="Instalasi panel listrik lantai dua",
        project_id=project.id,
        division_id=division.id,
        assigned_to=staff.id,
        created_by=manager.id,
        status=TaskStatus.IN_PROGRESS,
    )
    unassigned = Task(
        title="Testing pompa transfer",
        project_id=project.id,
        division_id=division.id,
        assigned_to=None,
        created_by=manager.id,
        status=TaskStatus.TODO,
    )
    db.add_all([assigned_first, assigned_selected, unassigned])
    db.flush()
    db.add(TaskSpecification(
        task_id=assigned_selected.id,
        wbs_code="MEP-EL-02",
        work_package="Electrical lantai dua",
        location="Lantai 2 zona timur",
        acceptance_criteria="Panel terpasang, berlabel, dan lolos inspeksi.",
        reporting_instructions="Laporkan volume kabel dan hasil pengujian.",
        required_photo_count=2,
        required_document_count=1,
    ))
    db.add(TaskControl(
        task_id=assigned_selected.id,
        unit="m",
        planned_quantity=120,
        actual_quantity=20,
        planned_manpower=6,
    ))
    db.add(TaskRequirement(
        task_id=assigned_selected.id,
        code="REQ-LABEL",
        title="Label panel dan kabel terpasang",
        description="Label harus sesuai single line diagram.",
        is_mandatory=True,
        sequence=1,
    ))
    db.commit()
    return session_factory, staff.id, assigned_first.id, assigned_selected.id, unassigned.id


@pytest.mark.asyncio
async def test_report_menu_only_lists_tasks_assigned_directly_to_staff(monkeypatch):
    session_factory, _, first_id, selected_id, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    update = FakeUpdate("9001")

    await telegram_service.report_interactive(update, FakeContext())

    keyboard = update.message.replies[0]["reply_markup"].inline_keyboard
    callback_ids = {button.callback_data for row in keyboard for button in row}
    assert callback_ids == {f"select_task_{first_id}", f"select_task_{selected_id}"}


@pytest.mark.asyncio
async def test_selected_task_opens_persistent_draft_with_real_task_requirements(monkeypatch):
    session_factory, staff_id, _, selected_id, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    update = FakeUpdate("9001", callback_data=f"select_task_{selected_id}")

    await telegram_service.handle_callback(update, FakeContext())

    db = session_factory()
    report = db.query(DailyReport).filter(DailyReport.user_id == staff_id).one()
    assert report.workflow.task_id == selected_id
    prompt = update.callback_query.edits[0]["text"]
    assert "Target volume: 120 m" in prompt
    assert "Progress awal: 20/120 m" in prompt
    assert "Lantai 2 zona timur" in prompt
    assert "Panel terpasang, berlabel, dan lolos inspeksi." in prompt
    assert "REQ-LABEL: ya/tidak - Label panel dan kabel terpasang" in prompt
    assert "Bukti wajib: 2 foto, 1 dokumen" in prompt
    db.close()


@pytest.mark.asyncio
async def test_report_text_updates_selected_draft_after_serverless_context_loss(monkeypatch):
    session_factory, staff_id, _, selected_id, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    monkeypatch.setattr(telegram_service.settings, "TELEGRAM_AI_PARSE_ENABLED", False)
    selection = FakeUpdate("9001", callback_data=f"select_task_{selected_id}")
    await telegram_service.handle_callback(selection, FakeContext())

    report_text = (
        "Cuaca: cerah\nPekerja: 6 orang\nProgress: kabel terpasang 15 m\n"
        "Kendala: tidak ada\nREQ-LABEL: ya"
    )
    cold_context = FakeContext()
    await telegram_service.handle_text_message(FakeUpdate("9001", text=report_text), cold_context)

    db = session_factory()
    reports = db.query(DailyReport).filter(DailyReport.user_id == staff_id).all()
    assert len(reports) == 1
    assert reports[0].workflow.task_id == selected_id
    assert reports[0].report_text == report_text
    assert reports[0].progress_entry.quantity_this_report == 15
    assert reports[0].requirement_checks[0].confirmed is True
    db.close()


@pytest.mark.asyncio
async def test_staff_cannot_select_unassigned_division_task(monkeypatch):
    session_factory, staff_id, _, _, unassigned_id = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    update = FakeUpdate("9001", callback_data=f"select_task_{unassigned_id}")

    await telegram_service.handle_callback(update, FakeContext())

    db = session_factory()
    assert db.query(DailyReport).filter(DailyReport.user_id == staff_id).count() == 0
    assert "bukan assignment" in update.callback_query.edits[0]["text"].lower()
    db.close()


@pytest.mark.asyncio
async def test_division_manager_report_menu_also_requires_direct_assignment(monkeypatch):
    session_factory, _, _, _, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    update = FakeUpdate("9002")

    await telegram_service.report_interactive(update, FakeContext())

    assert "tidak ada task aktif" in update.message.replies[0]["text"].lower()


@pytest.mark.asyncio
async def test_division_manager_cannot_report_task_only_because_they_manage_it(monkeypatch):
    session_factory, _, _, _, unassigned_id = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    update = FakeUpdate("9002", callback_data=f"select_task_{unassigned_id}")

    await telegram_service.handle_callback(update, FakeContext())

    assert "bukan assignment" in update.callback_query.edits[0]["text"].lower()


@pytest.mark.asyncio
async def test_photo_is_rejected_until_report_is_selected(monkeypatch):
    session_factory, staff_id, _, selected_id, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    monkeypatch.setattr(telegram_service.storage_service, "upload_file", lambda *_args: None)
    update = FakeUpdate(
        "9001",
        caption="Instalasi panel listrik lantai dua",
        with_photo=True,
    )

    await telegram_service.handle_structured_photo(update, FakeContext())

    db = session_factory()
    assert db.query(DailyReport).filter(DailyReport.user_id == staff_id).count() == 0
    assert db.query(ReportEvidence).count() == 0
    assert "/report" in update.message.replies[0]["text"]
    db.close()


@pytest.mark.asyncio
async def test_reselecting_report_after_old_photo_starts_fresh_photo_count(monkeypatch):
    session_factory, staff_id, _, selected_id, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    monkeypatch.setattr(telegram_service.storage_service, "upload_file", lambda *_args: None)
    await telegram_service.handle_callback(
        FakeUpdate("9001", callback_data=f"select_task_{selected_id}"), FakeContext()
    )
    db = session_factory()
    old_report = db.query(DailyReport).filter(DailyReport.user_id == staff_id).one()
    db.add(ReportEvidence(
        report_id=old_report.id,
        uploaded_by=staff_id,
        evidence_type=EvidenceType.PHOTO,
        file_name="old-photo.jpg",
        file_path="old/photo.jpg",
        file_size=10,
        mime_type="image/jpeg",
    ))
    db.commit()
    old_report_id = old_report.id
    db.close()

    await telegram_service.handle_callback(
        FakeUpdate("9001", callback_data=f"select_task_{selected_id}"), FakeContext()
    )
    photo_update = FakeUpdate("9001", caption="Bukti baru", with_photo=True)
    await telegram_service.handle_structured_photo(photo_update, FakeContext())

    db = session_factory()
    reports = db.query(DailyReport).filter(DailyReport.user_id == staff_id).order_by(DailyReport.id).all()
    assert len(reports) == 2
    assert reports[0].id == old_report_id
    assert len(reports[0].evidence) == 1
    assert len(reports[1].evidence) == 1
    assert "1/2" in photo_update.message.replies[-1]["text"]
    db.close()


@pytest.mark.asyncio
async def test_reselecting_older_draft_makes_it_the_persistent_active_report(monkeypatch):
    session_factory, staff_id, first_id, selected_id, _ = build_database()
    monkeypatch.setattr(telegram_service, "get_db", session_factory)
    monkeypatch.setattr(telegram_service.settings, "TELEGRAM_AI_PARSE_ENABLED", False)
    await telegram_service.handle_callback(
        FakeUpdate("9001", callback_data=f"select_task_{first_id}"), FakeContext()
    )
    await telegram_service.handle_callback(
        FakeUpdate("9001", callback_data=f"select_task_{selected_id}"), FakeContext()
    )
    await telegram_service.handle_callback(
        FakeUpdate("9001", callback_data=f"select_task_{first_id}"), FakeContext()
    )

    report_text = "Cuaca: cerah\nPekerja: 4 orang\nProgress: pipa terpasang 10 m\nKendala: tidak ada"
    await telegram_service.handle_text_message(
        FakeUpdate("9001", text=report_text), FakeContext()
    )

    db = session_factory()
    reports = db.query(DailyReport).filter(DailyReport.user_id == staff_id).all()
    report_by_task = {report.workflow.task_id: report for report in reports}
    assert report_by_task[first_id].report_text == report_text
    assert report_by_task[selected_id].report_text == ""
    db.close()
