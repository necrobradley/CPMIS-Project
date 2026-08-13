import io
import json
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.user import (
    ApprovalRequest,
    CommunicationItem,
    DailyReport,
    Document,
    InspectionRequest,
    NonConformance,
    Notification,
    ProductivityBenchmark,
    Project,
    ProjectMembership,
    Task,
    User,
    VendorProfile,
)
from app.services import project_demo_seed
from app.services.project_dataset import import_project_dataset
from app.services.telegram_auto_grouping import auto_group_message, create_report_draft
from scripts.build_demo_project_dataset import (
    build_graph,
    build_instructions,
    build_manifest,
    build_master,
)


def build_archive() -> bytes:
    master = build_master()
    files = {
        "30_AI_Training_Dataset_Master.json": json.dumps(master),
        "30_AI_Knowledge_Graph.json": json.dumps(build_graph(master)),
        "30_AI_Instruction_Dataset.jsonl": "\n".join(
            json.dumps(item) for item in build_instructions()
        ),
        "CPMIS_Demo_Features.json": json.dumps(build_manifest()),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def build_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_full_demo_dataset_populates_features_and_is_idempotent(monkeypatch):
    db = build_database()
    stored_objects = set()
    monkeypatch.setattr(
        project_demo_seed.storage_service,
        "file_exists",
        lambda path: path in stored_objects,
    )

    def fake_upload(content, path, content_type):
        del content, content_type
        stored_objects.add(path)
        return path

    monkeypatch.setattr(project_demo_seed.storage_service, "upload_file", fake_upload)
    content = build_archive()

    first = import_project_dataset(
        db,
        content,
        admin_email="admin@demo.example.com",
        admin_password="strong-demo-password",
        telegram_id="123456789",
    )
    second = import_project_dataset(
        db,
        content,
        admin_email="admin@demo.example.com",
        admin_password="",
        telegram_id="123456789",
    )

    assert first["demo_features_seeded"] is True
    assert first["tasks_upserted"] == 56
    assert first["project_roles_created"] == 45
    assert first["ai_role_tasks"] == 36
    assert first["demo_reports"] == 3
    assert first["demo_documents"] == 3
    assert second["demo_features_seeded"] is True
    assert db.query(Project).count() == 1
    assert db.query(User).count() == 46
    assert db.query(ProjectMembership).count() == 46
    assert db.query(Task).count() == 56
    assert db.query(Document).count() == 3
    assert db.query(DailyReport).count() == 3
    assert db.query(ApprovalRequest).count() == 3
    assert db.query(CommunicationItem).count() == 3
    assert db.query(Notification).count() == 4
    assert db.query(VendorProfile).count() == 2
    assert db.query(ProductivityBenchmark).count() == 2
    assert db.query(InspectionRequest).count() == 2
    assert db.query(NonConformance).count() == 1
    assert len(first["role_assignment_counts"]) == 36
    assert all(count == 1 for count in first["role_assignment_counts"].values())
    assert db.query(Task).filter(
        Task.ai_source == "Demo AI simulation - role coverage",
        Task.assigned_to.isnot(None),
    ).count() == 36
    staff = db.query(User).filter(User.telegram_id == "123456789").one()
    assert staff.role.value == "staff"

    task = db.query(Task).filter(Task.assigned_to == staff.id, Task.status != "done").first()
    result = auto_group_message(
        db,
        staff,
        f"Progress WBS {task.specification.wbs_code} sudah 72%. "
        "Volume 12 m2. Pekerja: 9. Cuaca: cerah. Kendala: tidak ada. "
        "QUALITY: ya. HSE: ya.",
    )
    assert result.is_confident is True
    assert result.task.id == task.id
    report = create_report_draft(
        db,
        staff,
        result.task,
        result.fields,
        telegram_message_id="telegram-e2e-demo",
    )
    assert report.workflow.status.value == "draft"
    assert db.query(DailyReport).count() == 4
