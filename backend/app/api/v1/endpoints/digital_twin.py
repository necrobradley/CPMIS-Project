from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import Project, User, UserRole
from app.schemas.schemas import (
    DigitalTwinDatasetImport, DigitalTwinGraphResponse, DigitalTwinImportSummary,
    DigitalTwinValidationSummary,
)
from app.services.audit_service import log_audit
from app.services.digital_twin import (
    export_graph, import_dataset, seed_default_rules, sync_existing_project_facts,
    validate_dataset,
)
from app.services.report_workflow import ensure_project_access

router = APIRouter(prefix="/digital-twin", tags=["Digital Twin Dataset"])
MANAGE_ROLES = {UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER}


def _get_project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project tidak ditemukan")
    return project


def _ensure_dataset_manager(project: Project, user: User) -> None:
    ensure_project_access(user, project)
    if user.role not in MANAGE_ROLES and project.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Digital Twin Dataset hanya dapat dikelola oleh admin, director, manager, atau owner project.",
        )


@router.get("/projects/{project_id}/graph", response_model=DigitalTwinGraphResponse)
def get_project_digital_twin_graph(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(db, project_id)
    _ensure_dataset_manager(project, current_user)
    return export_graph(db, project_id)


@router.post("/projects/{project_id}/import", response_model=DigitalTwinImportSummary)
def import_project_digital_twin_dataset(
    project_id: int,
    payload: DigitalTwinDatasetImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(db, project_id)
    _ensure_dataset_manager(project, current_user)
    try:
        result = import_dataset(db, project_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db,
        actor_id=current_user.id,
        action="digital_twin.dataset_imported",
        entity_type="digital_twin",
        entity_id=str(project_id),
        project_id=project_id,
        summary=(
            f"Digital Twin import: {result['nodes_upserted']} node, "
            f"{result['relationships_upserted']} relationship, "
            f"{result['rules_upserted']} rule."
        ),
        after=result,
    )
    db.commit()
    return result


@router.post("/projects/{project_id}/sync-existing", response_model=DigitalTwinImportSummary)
def sync_existing_cpmis_data_to_digital_twin(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(db, project_id)
    _ensure_dataset_manager(project, current_user)
    result = sync_existing_project_facts(db, project)
    log_audit(
        db,
        actor_id=current_user.id,
        action="digital_twin.synced_existing_data",
        entity_type="digital_twin",
        entity_id=str(project_id),
        project_id=project_id,
        summary="Data task/material/dependency CPMIS disinkronkan ke Digital Twin Dataset.",
        after=result,
    )
    db.commit()
    return result


@router.post("/projects/{project_id}/rules/defaults")
def seed_project_digital_twin_rules(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(db, project_id)
    _ensure_dataset_manager(project, current_user)
    count = seed_default_rules(db, project_id)
    log_audit(
        db,
        actor_id=current_user.id,
        action="digital_twin.default_rules_seeded",
        entity_type="digital_twin_rule",
        entity_id=str(project_id),
        project_id=project_id,
        summary=f"{count} rule awal Digital Twin dibuat/diperbarui.",
        after={"rule_count": count},
    )
    db.commit()
    return {"project_id": project_id, "rules_upserted": count}


@router.post("/projects/{project_id}/validate", response_model=DigitalTwinValidationSummary)
def validate_project_digital_twin_dataset(
    project_id: int,
    persist: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(db, project_id)
    _ensure_dataset_manager(project, current_user)
    result = validate_dataset(db, project_id, persist=persist)
    if persist:
        log_audit(
            db,
            actor_id=current_user.id,
            action="digital_twin.dataset_validated",
            entity_type="digital_twin",
            entity_id=str(project_id),
            project_id=project_id,
            summary=f"Validasi Digital Twin menghasilkan {result['issue_count']} issue.",
            after={"passed": result["passed"], "issue_count": result["issue_count"]},
        )
        db.commit()
    return result


@router.get("/template")
def get_digital_twin_dataset_template():
    return {
        "nodes": [
            {
                "uid": "project:demo",
                "node_type": "project",
                "code": "PRJ-DEMO",
                "name": "Demo Project",
                "metadata": {"owner": "Rencanix"},
            },
            {
                "uid": "wbs:1",
                "node_type": "wbs",
                "code": "1.0",
                "name": "Pekerjaan Struktur",
                "metadata": {},
            },
            {
                "uid": "boq:1",
                "node_type": "boq",
                "code": "BOQ-001",
                "name": "Beton K-300",
                "metadata": {"unit": "m3", "planned_quantity": 100, "boq_value": 85000000},
            },
            {
                "uid": "activity:1",
                "node_type": "activity",
                "code": "ACT-001",
                "name": "Pengecoran kolom lantai 1",
                "metadata": {"duration_days": 2, "productivity_reference": "30 m3/hari"},
            },
        ],
        "relationships": [
            {
                "from_uid": "project:demo",
                "to_uid": "wbs:1",
                "relationship_type": "has_wbs",
                "relationship_name": "Project memiliki WBS",
            },
            {
                "from_uid": "wbs:1",
                "to_uid": "boq:1",
                "relationship_type": "has_boq",
                "relationship_name": "WBS memiliki BOQ",
            },
            {
                "from_uid": "boq:1",
                "to_uid": "activity:1",
                "relationship_type": "defines_quantity_for",
                "relationship_name": "BOQ menjadi dasar activity",
            },
        ],
        "rules": [],
        "reasoning_examples": [],
    }
