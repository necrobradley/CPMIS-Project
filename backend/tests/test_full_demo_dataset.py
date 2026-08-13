import copy
import io
import json
import zipfile
from collections import Counter

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.user import (
    ApprovalRequest,
    CommunicationItem,
    DailyReport,
    Division,
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
from app.core.security import get_password_hash
from app.models.user import UserRole
from app.services.project_dataset import import_project_dataset, sync_dataset_task_divisions
from app.services.telegram_auto_grouping import auto_group_message, create_report_draft
from scripts.build_demo_project_dataset import (
    build_graph,
    build_instructions,
    build_manifest,
    build_master,
)


def build_archive(
    *,
    project_name: str | None = None,
    first_work_package: str | None = None,
) -> bytes:
    master = copy.deepcopy(build_master())
    if project_name:
        master["project_summary"]["project_name"] = project_name
    if first_work_package:
        master["linked_chains"][0]["wbs"]["wbs_name"] = first_work_package
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
    admin = db.query(User).filter(User.email == "admin@demo.example.com").one()
    manually_assigned_task = db.query(Task).order_by(Task.id).first()
    manually_assigned_task.assigned_to = admin.id
    db.commit()
    second = import_project_dataset(
        db,
        content,
        admin_email="admin@demo.example.com",
        admin_password="",
        telegram_id="123456789",
    )

    assert first["demo_features_seeded"] is True
    assert first["tasks_upserted"] == 20
    assert first["project_roles_created"] == 0
    assert first["ai_role_tasks"] == 0
    assert first["demo_reports"] == 3
    assert first["demo_documents"] == 3
    assert second["demo_features_seeded"] is True
    assert db.query(Project).count() == 1
    assert db.query(User).count() == 1
    assert db.query(ProjectMembership).count() == 1
    assert db.query(Task).count() == 20
    assert db.query(Document).count() == 3
    assert db.query(DailyReport).count() == 3
    assert db.query(ApprovalRequest).count() == 3
    assert db.query(CommunicationItem).count() == 3
    assert db.query(Notification).count() == 4
    assert db.query(VendorProfile).count() == 2
    assert db.query(ProductivityBenchmark).count() == 2
    assert db.query(InspectionRequest).count() == 2
    assert db.query(NonConformance).count() == 1
    assert first["generated_accounts"] == []
    assert first["role_assignment_counts"] == {}
    assert db.query(Task).filter(
        Task.ai_source == "Demo AI simulation - role coverage",
        Task.assigned_to.isnot(None),
    ).count() == 0
    db.refresh(manually_assigned_task)
    assert manually_assigned_task.assigned_to == admin.id
    assert db.query(Task).filter(Task.assigned_to.isnot(None)).count() == 1


def test_imported_project_tasks_are_grouped_under_divisions(monkeypatch):
    db = build_database()
    monkeypatch.setattr(project_demo_seed.storage_service, "file_exists", lambda path: False)
    monkeypatch.setattr(
        project_demo_seed.storage_service,
        "upload_file",
        lambda content, path, content_type: path,
    )

    result = import_project_dataset(
        db,
        build_archive(),
        admin_email="admin.division@example.com",
        admin_password="strong-demo-password",
    )

    project_tasks = db.query(Task).filter(Task.project_id == result["project_id"]).all()
    divisions_with_tasks = {
        task.division_id for task in project_tasks if task.division_id is not None
    }
    assert len(project_tasks) == 20
    assert db.query(Task).filter(
        Task.project_id == result["project_id"],
        Task.division_id.is_(None),
    ).count() == 0
    assert len(divisions_with_tasks) >= 5
    assert db.query(Division).filter(
        Division.project_id == result["project_id"],
        Division.id.in_(divisions_with_tasks),
    ).count() == len(divisions_with_tasks)
    assert Counter(task.division.division_name for task in project_tasks) == {
        "Site Management": 1,
        "Site Execution": 6,
        "Architecture": 4,
        "MEP": 6,
        "QA/QC": 1,
        "Document Control": 2,
    }


def test_legacy_dataset_division_backfill_is_safe_and_idempotent(monkeypatch):
    db = build_database()
    monkeypatch.setattr(project_demo_seed.storage_service, "file_exists", lambda path: False)
    monkeypatch.setattr(
        project_demo_seed.storage_service,
        "upload_file",
        lambda content, path, content_type: path,
    )
    result = import_project_dataset(
        db,
        build_archive(),
        admin_email="admin.backfill@example.com",
        admin_password="strong-demo-password",
    )
    legacy_division = db.query(Division).filter(
        Division.project_id == result["project_id"],
        Division.division_name == "Project Controls & Digital Engineering",
    ).one()
    project_tasks = db.query(Task).filter(Task.project_id == result["project_id"]).all()
    for task in project_tasks:
        task.division_id = legacy_division.id
    db.commit()

    first = sync_dataset_task_divisions(db, result["project_id"])
    db.commit()
    second = sync_dataset_task_divisions(db, result["project_id"])
    db.commit()

    assert first == {"tasks_updated": 20, "divisions_created": 0}
    assert second == {"tasks_updated": 0, "divisions_created": 0}
    assert len({task.division_id for task in project_tasks}) == 6


def test_first_dataset_import_populates_existing_blank_admin_project(monkeypatch):
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
    admin = User(
        name="Admin Proyek Baru",
        email="admin.baru@example.com",
        password_hash=get_password_hash("admin-password-123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.flush()
    blank_project = Project(project_name="Pembangunan Tunnel", owner_id=admin.id)
    db.add(blank_project)
    db.flush()
    db.add(ProjectMembership(
        project_id=blank_project.id,
        user_id=admin.id,
        project_role="project_admin",
        is_active=True,
    ))
    original_project_id = blank_project.id
    db.commit()

    result = import_project_dataset(
        db,
        build_archive(),
        admin_email=admin.email,
        admin_password="",
    )

    assert result["project_id"] == original_project_id
    assert db.query(Project).count() == 1
    db.refresh(blank_project)
    assert blank_project.project_name == "Pusat Inovasi Terpadu Nusantara"
    assert db.query(Task).filter(Task.project_id == original_project_id).count() == 20


def test_existing_imported_project_rejects_zip_for_different_project(monkeypatch):
    db = build_database()
    stored_objects = set()
    monkeypatch.setattr(project_demo_seed.storage_service, "file_exists", lambda path: path in stored_objects)
    monkeypatch.setattr(
        project_demo_seed.storage_service,
        "upload_file",
        lambda content, path, content_type: stored_objects.add(path) or path,
    )
    first = import_project_dataset(
        db,
        build_archive(),
        admin_email="admin.protected@example.com",
        admin_password="admin-password-123",
    )

    with pytest.raises(ValueError) as exc:
        import_project_dataset(
            db,
            build_archive(project_name="Proyek Berbeda"),
            admin_email="admin.protected@example.com",
            admin_password="",
        )

    assert "tidak dapat menggantikannya" in str(exc.value)
    assert db.query(Project).count() == 1
    assert db.query(Project).one().id == first["project_id"]


def test_same_demo_zip_can_be_imported_by_different_project_admins(monkeypatch):
    db = build_database()
    stored_objects = set()
    monkeypatch.setattr(project_demo_seed.storage_service, "file_exists", lambda path: path in stored_objects)
    monkeypatch.setattr(
        project_demo_seed.storage_service,
        "upload_file",
        lambda content, path, content_type: stored_objects.add(path) or path,
    )

    first = import_project_dataset(
        db,
        build_archive(),
        admin_email="admin.demo.one@example.com",
        admin_password="admin-password-123",
    )
    second = import_project_dataset(
        db,
        build_archive(),
        admin_email="admin.demo.two@example.com",
        admin_password="admin-password-456",
    )

    assert first["project_id"] != second["project_id"]
    assert db.query(Project).count() == 2
    assert db.query(Project).filter(Project.project_name == "Pusat Inovasi Terpadu Nusantara").count() == 2


def test_new_discipline_is_created_per_project_without_demo_name_dependency(monkeypatch):
    db = build_database()
    monkeypatch.setattr(project_demo_seed.storage_service, "file_exists", lambda path: False)
    monkeypatch.setattr(
        project_demo_seed.storage_service,
        "upload_file",
        lambda content, path, content_type: path,
    )
    first = import_project_dataset(
        db,
        build_archive(project_name="Pelabuhan Samudra", first_work_package="pekerjaan kelautan"),
        admin_email="admin.pelabuhan@example.com",
        admin_password="admin-password-123",
    )
    second = import_project_dataset(
        db,
        build_archive(project_name="Kawasan Teknologi", first_work_package="BIM coordination"),
        admin_email="admin.teknologi@example.com",
        admin_password="admin-password-456",
    )

    assert db.query(Division).filter(
        Division.project_id == first["project_id"],
        Division.division_name == "Pekerjaan Kelautan",
    ).count() == 1
    assert db.query(Division).filter(
        Division.project_id == second["project_id"],
        Division.division_name == "BIM Coordination",
    ).count() == 1
    assert db.query(Division).filter(
        Division.project_id == first["project_id"],
        Division.division_name == "BIM Coordination",
    ).count() == 0
