import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import (
    Document, DocumentType, Project, ProjectStatus, Task, TaskRequirement,
    TaskMaterialSpecification, TaskSpecification, TaskStatus, User, UserRole,
)
from app.services.document_sync import apply_sync_plan, build_sync_plan


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    manager = User(
        name="Manager Test", email="manager@test.local", password_hash="x",
        role=UserRole.MANAGER,
    )
    session.add(manager)
    session.flush()
    project = Project(
        project_name="Proyek Lama", location="Jakarta", contract_value=100,
        status=ProjectStatus.ACTIVE, owner_id=manager.id, progress_percent=60,
    )
    session.add(project)
    session.flush()
    document = Document(
        project_id=project.id, uploaded_by=manager.id, file_name="kontrak-v2.pdf",
        file_path="projects/1/contract/test.pdf", file_type=DocumentType.CONTRACT,
        version=2, ai_analysis=json.dumps({"project_name": "Proyek Baru"}),
    )
    session.add(document)
    session.flush()
    task = Task(
        title="Pondasi lama", project_id=project.id, created_by=manager.id,
        assigned_to=manager.id, status=TaskStatus.IN_PROGRESS, progress_percent=60,
    )
    session.add(task)
    session.flush()
    task.specification = TaskSpecification(
        wbs_code="1.01", acceptance_criteria="Kriteria lama",
        required_photo_count=1, source_document_id=document.id,
    )
    task.requirements.append(TaskRequirement(
        code="1.01-QUALITY", title="Mutu lama", sequence=1,
    ))
    task.materials.append(TaskMaterialSpecification(
        material_code="MAT-CON", material_name="Beton lama",
        technical_specification="fc' 25 MPa", sequence=1,
    ))
    session.commit()
    return session, manager, project, document, task


def test_preview_matches_existing_task_by_wbs():
    db, _, project, document, _ = build_database()
    analysis = {
        "project_name": "Proyek Baru",
        "location": "Bandung",
        "contract_value": 250,
        "divisions_needed": ["Struktur"],
    }
    candidates = [{
        "wbs_code": "1.01", "title": "Pekerjaan pondasi", "priority": "high",
        "acceptance_criteria": "Kuat tekan sesuai spesifikasi",
        "required_photo_count": 2,
        "requirements": [{"code": "QUALITY", "title": "Mutu beton"}],
        "materials": [{
            "material_code": "MAT-CON", "material_name": "Beton ready mix",
            "grade": "fc' 30 MPa", "standard_reference": "SNI 2847:2019",
            "certificate_required": True, "test_required": True,
        }],
    }]

    plan = build_sync_plan(db, document, analysis, candidates)

    assert plan["summary"]["project_updates"] == 3
    assert plan["summary"]["divisions_created"] == 1
    assert plan["summary"]["tasks_created"] == 0
    assert plan["summary"]["tasks_updated"] == 1
    assert "task:update:1.01" in {item["id"] for item in plan["changes"]}
    assert project.project_name == "Proyek Lama"


def test_apply_is_non_destructive_for_task_workflow_fields():
    db, manager, project, document, task = build_database()
    analysis = {"project_name": "Proyek Baru", "divisions_needed": ["Struktur"]}
    candidates = [
        {
            "wbs_code": "1.01", "title": "Pekerjaan pondasi baru", "priority": "critical",
            "division": "Struktur", "acceptance_criteria": "Sesuai shop drawing",
            "requirements": [{"code": "QUALITY", "title": "Mutu diperbarui"}],
            "materials": [{
                "material_code": "MAT-CON", "material_name": "Beton ready mix",
                "grade": "fc' 35 MPa", "test_required": True,
            }],
        },
        {
            "wbs_code": "1.02", "parent_wbs": "1.01", "title": "Pile cap",
            "priority": "high", "division": "Struktur", "acceptance_criteria": "Dimensi sesuai gambar",
            "materials": [{
                "material_code": "MAT-RBR", "material_name": "Baja tulangan",
                "grade": "BJTS 420B", "certificate_required": True,
            }],
        },
    ]
    plan = build_sync_plan(db, document, analysis, candidates)
    selected = [item["id"] for item in plan["changes"]]

    result = apply_sync_plan(db, plan=plan, selected_change_ids=selected, actor_id=manager.id)
    db.commit()
    db.refresh(task)

    assert result["tasks_created"] == 1
    assert result["tasks_updated"] == 1
    assert project.project_name == "Proyek Baru"
    assert task.title == "Pekerjaan pondasi baru"
    assert task.status == TaskStatus.BLOCKED
    assert task.progress_percent == 60
    assert task.assigned_to == manager.id
    assert task.control.revision_attention_required is True
    assert task.specification.required_photo_count == 0
    assert any(item.code == "1.01-QUALITY" and item.title == "Mutu diperbarui" for item in task.requirements)
    assert any(
        item.material_code == "MAT-CON" and item.grade == "fc' 35 MPa"
        and item.source_document_id == document.id
        for item in task.materials
    )
    child = db.query(Task).join(TaskSpecification).filter(TaskSpecification.wbs_code == "1.02").one()
    assert child.parent_task_id == task.id
    assert any(item.material_code == "MAT-RBR" for item in child.materials)