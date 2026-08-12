from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import (
    DigitalTwinNode, DigitalTwinNodeType, Project, ProjectStatus, Task, TaskControl,
    TaskSpecification, User, UserRole,
)
from app.schemas.schemas import (
    DigitalTwinDatasetImport, DigitalTwinNodeCreate, DigitalTwinReasoningExampleCreate,
    DigitalTwinRelationshipCreate,
)
from app.services.digital_twin import (
    export_graph, import_dataset, seed_default_rules, sync_existing_project_facts,
    validate_dataset,
)


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        name="Digital Twin Manager",
        email="digital-twin@test.local",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db.add(manager)
    db.flush()
    project = Project(
        project_name="Digital Twin Project",
        status=ProjectStatus.ACTIVE,
        owner_id=manager.id,
    )
    db.add(project)
    db.commit()
    return db, manager, project


def test_import_dataset_validates_missing_supplier_then_passes_after_fix():
    db, _, project = build_database()

    payload = DigitalTwinDatasetImport(
        nodes=[
            DigitalTwinNodeCreate(uid="project:1", node_type=DigitalTwinNodeType.PROJECT, name="Project"),
            DigitalTwinNodeCreate(uid="contract:1", node_type=DigitalTwinNodeType.CONTRACT, name="Contract"),
            DigitalTwinNodeCreate(uid="wbs:1", node_type=DigitalTwinNodeType.WBS, name="Pekerjaan Struktur"),
            DigitalTwinNodeCreate(uid="boq:1", node_type=DigitalTwinNodeType.BOQ, name="Beton K-300"),
            DigitalTwinNodeCreate(
                uid="activity:1",
                node_type=DigitalTwinNodeType.ACTIVITY,
                name="Pengecoran Kolom",
                metadata={"is_start": True, "is_finish": True, "duration_days": 2, "productivity_reference": "30 m3/hari"},
            ),
            DigitalTwinNodeCreate(uid="material:1", node_type=DigitalTwinNodeType.MATERIAL, name="Ready Mix K-300"),
        ],
        relationships=[
            DigitalTwinRelationshipCreate(
                from_uid="project:1", to_uid="contract:1",
                relationship_type="has_contract", relationship_name="Project memiliki contract",
            ),
            DigitalTwinRelationshipCreate(
                from_uid="contract:1", to_uid="wbs:1",
                relationship_type="defines_wbs", relationship_name="Contract mendefinisikan WBS",
            ),
            DigitalTwinRelationshipCreate(
                from_uid="wbs:1", to_uid="boq:1",
                relationship_type="has_boq", relationship_name="WBS memiliki BOQ",
            ),
            DigitalTwinRelationshipCreate(
                from_uid="boq:1", to_uid="activity:1",
                relationship_type="defines_quantity_for", relationship_name="BOQ menjadi dasar activity",
            ),
            DigitalTwinRelationshipCreate(
                from_uid="activity:1", to_uid="material:1",
                relationship_type="uses_material", relationship_name="Activity menggunakan material",
            ),
        ],
    )
    summary = import_dataset(db, project.id, payload)

    assert summary["nodes_upserted"] == 6
    result = validate_dataset(db, project.id)
    assert result["passed"] is False
    assert "material_without_supplier" in {issue["code"] for issue in result["issues"]}

    fix_payload = DigitalTwinDatasetImport(
        nodes=[
            DigitalTwinNodeCreate(uid="supplier:1", node_type=DigitalTwinNodeType.SUPPLIER, name="PT Beton Supplier"),
        ],
        relationships=[
            DigitalTwinRelationshipCreate(
                from_uid="material:1", to_uid="supplier:1",
                relationship_type="purchased_from", relationship_name="Material dibeli dari supplier",
            ),
        ],
    )
    import_dataset(db, project.id, fix_payload)
    fixed = validate_dataset(db, project.id)

    assert "material_without_supplier" not in {issue["code"] for issue in fixed["issues"]}


def test_seed_rules_and_reasoning_examples_are_exported():
    db, _, project = build_database()

    seed_default_rules(db, project.id)
    payload = DigitalTwinDatasetImport(
        nodes=[
            DigitalTwinNodeCreate(uid="project:1", node_type=DigitalTwinNodeType.PROJECT, name="Project"),
            DigitalTwinNodeCreate(uid="activity:1", node_type=DigitalTwinNodeType.ACTIVITY, name="Pembesian Kolom"),
        ],
        reasoning_examples=[
            DigitalTwinReasoningExampleCreate(
                example_uid="QA-001",
                question="Mengapa bekisting dilakukan setelah pembesian?",
                context="WBS struktur, method statement, dan rule scheduling.",
                reasoning="Tulangan harus berada di dalam cetakan sebelum beton dicor.",
                answer="Bekisting dilakukan setelah pembesian agar tulangan berada pada posisi yang benar di dalam cetakan.",
                reference="R-SCH-002",
                related_node_uid="activity:1",
            )
        ],
    )
    import_dataset(db, project.id, payload)
    graph = export_graph(db, project.id)

    assert len(graph["rules"]) >= 5
    assert graph["reasoning_examples"][0]["example_uid"] == "QA-001"
    assert graph["reasoning_examples"][0]["related_node_uid"] == "activity:1"


def test_sync_existing_cpmis_task_creates_wbs_boq_activity_nodes():
    db, manager, project = build_database()
    task = Task(
        title="Pengecoran Kolom Lantai 1",
        project_id=project.id,
        created_by=manager.id,
    )
    db.add(task)
    db.flush()
    db.add(TaskSpecification(
        task_id=task.id,
        wbs_code="1.2.3",
        work_package="Struktur Kolom",
        location="Lantai 1",
        acceptance_criteria="Beton sesuai spesifikasi dan lolos inspeksi.",
    ))
    db.add(TaskControl(
        task_id=task.id,
        unit="m3",
        planned_quantity=60,
        planned_manpower=8,
        boq_value=51_000_000,
    ))
    db.commit()

    result = sync_existing_project_facts(db, project)
    graph = export_graph(db, project.id)
    node_types = {node["node_type"] for node in graph["nodes"]}
    rel_types = {edge["relationship_type"] for edge in graph["relationships"]}

    assert result["nodes_upserted"] >= 3
    assert {"project", "wbs", "boq", "activity"}.issubset(node_types)
    assert {"has_wbs", "has_boq", "defines_quantity_for"}.issubset(rel_types)
    assert db.query(DigitalTwinNode).filter(DigitalTwinNode.uid == f"task:{task.id}").first()
