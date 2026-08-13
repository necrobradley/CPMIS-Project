import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.user import (
    Division, Document, Project, Task, TaskPriority, TaskRequirement,
    TaskMaterialSpecification, TaskSpecification,
)
from app.services.project_controls import mark_tasks_revision_impacted, recalculate_project_controls
from app.services.project_staffing import (
    active_pic_roles,
    resolve_task_project_role,
    select_task_pic,
)


PROJECT_FIELDS = {
    "project_name": ("Nama proyek", "high"),
    "location": ("Lokasi proyek", "medium"),
    "contract_value": ("Nilai kontrak", "high"),
    "start_date": ("Tanggal mulai", "high"),
    "end_date": ("Tanggal selesai", "high"),
}


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _normal(value: Any) -> str:
    return (_clean_text(value) or "").casefold()


def _date_value(value: Any) -> Optional[str]:
    if value in (None, "", "null"):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _datetime_value(value: Any) -> Optional[datetime]:
    parsed = _date_value(value)
    return datetime.fromisoformat(parsed) if parsed else None


def _number_value(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serialize_project_value(field: str, value: Any) -> Any:
    if field in ("start_date", "end_date"):
        return _date_value(value)
    if field == "contract_value":
        return _number_value(value)
    return _clean_text(value)


def _serialize_requirement(requirement: Any, wbs_code: str, index: int) -> Dict[str, Any]:
    item = requirement if isinstance(requirement, dict) else {}
    raw_code = _clean_text(item.get("code")) or str(index)
    code = raw_code if raw_code.startswith(f"{wbs_code}-") else f"{wbs_code}-{raw_code}"
    return {
        "code": code[:80],
        "title": (_clean_text(item.get("title")) or f"Requirement {index}")[:200],
        "description": _clean_text(item.get("description")),
        "requirement_type": _clean_text(item.get("requirement_type")) or "checklist",
        "validation_rule": _clean_text(item.get("validation_rule")) or "manual_confirmation",
        "is_mandatory": bool(item.get("is_mandatory", True)),
        "sequence": index,
    }


def _serialize_material(material: Any, index: int) -> Optional[Dict[str, Any]]:
    item = material if isinstance(material, dict) else {}
    name = _clean_text(item.get("material_name") or item.get("name"))
    if not name:
        return None
    return {
        "material_code": _clean_text(item.get("material_code") or item.get("code")),
        "material_name": name[:200],
        "category": _clean_text(item.get("category")),
        "technical_specification": _clean_text(item.get("technical_specification") or item.get("specification")),
        "standard_reference": _clean_text(item.get("standard_reference") or item.get("standard")),
        "grade": _clean_text(item.get("grade")),
        "approved_manufacturer": _clean_text(item.get("approved_manufacturer") or item.get("manufacturer") or item.get("brand")),
        "dimensions": _clean_text(item.get("dimensions")),
        "unit": _clean_text(item.get("unit")),
        "planned_quantity": _number_value(item.get("planned_quantity") or item.get("quantity")),
        "certificate_required": bool(item.get("certificate_required", False)),
        "test_required": bool(item.get("test_required", False)),
        "approval_required": bool(item.get("approval_required", True)),
        "source_page": _clean_text(item.get("source_page") or item.get("page")),
        "revision": _clean_text(item.get("revision")),
        "sequence": index,
    }


def _serialize_task_candidate(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    wbs_code = _clean_text(candidate.get("wbs_code"))
    title = _clean_text(candidate.get("title"))
    if not wbs_code or not title:
        return None
    priority = str(candidate.get("priority") or TaskPriority.MEDIUM.value).lower()
    if priority not in {item.value for item in TaskPriority}:
        priority = TaskPriority.MEDIUM.value
    requirements = candidate.get("requirements") or []
    if not requirements:
        requirements = [
            {"code": "SCOPE", "title": "Lingkup pekerjaan telah diperiksa", "description": "Konfirmasi terhadap dokumen sumber."},
            {"code": "QUALITY", "title": "Kriteria mutu telah diperiksa", "description": "Konfirmasi terhadap acceptance criteria."},
        ]
    materials = [
        serialized for index, item in enumerate(
            candidate.get("materials") or candidate.get("material_specifications") or [], start=1
        )
        if (serialized := _serialize_material(item, index)) is not None
    ]
    return {
        "wbs_code": wbs_code[:80],
        "parent_wbs": _clean_text(candidate.get("parent_wbs")),
        "title": title[:200],
        "description": _clean_text(candidate.get("description")),
        "priority": priority,
        "deadline": _date_value(candidate.get("deadline")),
        "division_name": _clean_text(candidate.get("division")),
        "project_role": _clean_text(candidate.get("project_role")),
        "work_package": _clean_text(candidate.get("work_package") or candidate.get("division")),
        "location": _clean_text(candidate.get("location")),
        "acceptance_criteria": _clean_text(candidate.get("acceptance_criteria")) or "Wajib diverifikasi manager berdasarkan dokumen sumber.",
        "reporting_instructions": _clean_text(candidate.get("reporting_instructions")),
        "required_photo_count": max(0, int(candidate.get("required_photo_count") or 0)),
        "required_document_count": max(0, int(candidate.get("required_document_count") or 0)),
        "requirements": [_serialize_requirement(item, wbs_code, index) for index, item in enumerate(requirements, start=1)],
        "materials": materials,
    }


def _serialize_existing_task(task: Task) -> Dict[str, Any]:
    specification = task.specification
    return {
        "wbs_code": specification.wbs_code if specification else None,
        "parent_wbs": task.parent.specification.wbs_code if task.parent and task.parent.specification else None,
        "title": task.title,
        "description": task.description,
        "priority": task.priority.value if hasattr(task.priority, "value") else task.priority,
        "deadline": _date_value(task.deadline),
        "division_name": task.division.division_name if task.division else None,
        "work_package": specification.work_package if specification else None,
        "location": specification.location if specification else None,
        "acceptance_criteria": specification.acceptance_criteria if specification else None,
        "reporting_instructions": specification.reporting_instructions if specification else None,
        "required_photo_count": specification.required_photo_count if specification else 0,
        "required_document_count": specification.required_document_count if specification else 0,
        "requirements": [
            {
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "requirement_type": item.requirement_type,
                "validation_rule": item.validation_rule,
                "is_mandatory": item.is_mandatory,
                "sequence": item.sequence,
            }
            for item in task.requirements
        ],
        "materials": [
            {
                "material_code": item.material_code,
                "material_name": item.material_name,
                "category": item.category,
                "technical_specification": item.technical_specification,
                "standard_reference": item.standard_reference,
                "grade": item.grade,
                "approved_manufacturer": item.approved_manufacturer,
                "dimensions": item.dimensions,
                "unit": item.unit,
                "planned_quantity": item.planned_quantity,
                "certificate_required": item.certificate_required,
                "test_required": item.test_required,
                "approval_required": item.approval_required,
                "source_page": item.source_page,
                "revision": item.revision,
                "sequence": item.sequence,
            }
            for item in task.materials
        ],
    }


def _task_changed(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    managed_fields = (
        "parent_wbs", "title", "description", "priority", "deadline", "division_name",
        "work_package", "location", "acceptance_criteria", "reporting_instructions",
        "required_photo_count", "required_document_count", "requirements",
    )
    if any(before.get(field) != after.get(field) for field in managed_fields):
        return True
    return bool(after.get("materials")) and before.get("materials") != after.get("materials")


def build_sync_plan(
    db: Session,
    document: Document,
    analysis: Dict[str, Any],
    task_candidates: Optional[Iterable[Dict[str, Any]]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    project = db.query(Project).filter(Project.id == document.project_id).first()
    if not project:
        raise ValueError("Proyek dokumen tidak ditemukan")

    changes: List[Dict[str, Any]] = []
    plan_warnings = list(warnings or [])
    for field, (label, risk) in PROJECT_FIELDS.items():
        proposed = _serialize_project_value(field, analysis.get(field))
        current = _serialize_project_value(field, getattr(project, field))
        if proposed is not None and proposed != current:
            changes.append({
                "id": f"project:{field}", "entity": "project", "operation": "update",
                "field": field, "label": label, "risk": risk, "before": current, "after": proposed,
            })

    existing_divisions = {
        _normal(item.division_name): item for item in db.query(Division).filter(Division.project_id == project.id).all()
    }
    proposed_divisions = analysis.get("divisions_needed") or []
    for name in proposed_divisions:
        clean_name = _clean_text(name)
        if clean_name and _normal(clean_name) not in existing_divisions:
            changes.append({
                "id": f"division:create:{_normal(clean_name)}", "entity": "division", "operation": "create",
                "field": None, "label": f"Divisi {clean_name}", "risk": "low", "before": None,
                "after": {"division_name": clean_name[:100], "description": "Dibuat dari sinkronisasi dokumen"},
            })

    specifications = db.query(TaskSpecification).join(Task).filter(Task.project_id == project.id).all()
    existing_tasks = {item.wbs_code: item.task for item in specifications}
    seen_wbs = set()
    for raw_candidate in task_candidates or []:
        proposed_task = _serialize_task_candidate(raw_candidate)
        if not proposed_task:
            plan_warnings.append("Satu task dilewati karena tidak memiliki WBS atau judul.")
            continue
        wbs_code = proposed_task["wbs_code"]
        if wbs_code in seen_wbs:
            plan_warnings.append(f"WBS {wbs_code} duplikat pada hasil analisis dan hanya dipakai sekali.")
            continue
        seen_wbs.add(wbs_code)
        existing = existing_tasks.get(wbs_code)
        if existing:
            before = _serialize_existing_task(existing)
            if _task_changed(before, proposed_task):
                changes.append({
                    "id": f"task:update:{wbs_code}", "entity": "task", "operation": "update",
                    "field": None, "label": f"WBS {wbs_code} - {proposed_task['title']}", "risk": "medium",
                    "before": before, "after": proposed_task,
                })
        else:
            changes.append({
                "id": f"task:create:{wbs_code}", "entity": "task", "operation": "create",
                "field": None, "label": f"WBS {wbs_code} - {proposed_task['title']}", "risk": "medium",
                "before": None, "after": proposed_task,
            })

    if not task_candidates:
        plan_warnings.append("Belum ada kandidat WBS. Metadata proyek dan divisi tetap dapat disinkronkan.")
    plan_warnings.append("Sinkronisasi tidak menghapus task, laporan, evidence, status pekerjaan, progres task, atau PIC yang sudah ada.")

    summary = {
        "total": len(changes),
        "project_updates": sum(1 for item in changes if item["entity"] == "project"),
        "divisions_created": sum(1 for item in changes if item["entity"] == "division"),
        "tasks_created": sum(1 for item in changes if item["entity"] == "task" and item["operation"] == "create"),
        "tasks_updated": sum(1 for item in changes if item["entity"] == "task" and item["operation"] == "update"),
        "high_risk": sum(1 for item in changes if item["risk"] == "high"),
    }
    return {
        "version": 1,
        "document": {"id": document.id, "file_name": document.file_name, "version": document.version},
        "project": {"id": project.id, "project_name": project.project_name},
        "summary": summary,
        "changes": changes,
        "warnings": list(dict.fromkeys(plan_warnings)),
        "policy": {
            "match_key": "wbs_code",
            "delete_missing": False,
            "preserve_status_progress_assignee": True,
            "require_approval": True,
        },
    }


def _find_division(db: Session, project_id: int, name: Optional[str]) -> Optional[Division]:
    if not name:
        return None
    divisions = db.query(Division).filter(Division.project_id == project_id).all()
    return next((item for item in divisions if _normal(item.division_name) == _normal(name)), None)


def _upsert_task_requirements(task: Task, requirements: List[Dict[str, Any]]) -> None:
    existing = {item.code: item for item in task.requirements}
    for data in requirements:
        requirement = existing.get(data["code"])
        if not requirement:
            requirement = TaskRequirement(task_id=task.id, code=data["code"])
            task.requirements.append(requirement)
        requirement.title = data["title"]
        requirement.description = data.get("description")
        requirement.requirement_type = data.get("requirement_type") or "checklist"
        requirement.validation_rule = data.get("validation_rule") or "manual_confirmation"
        requirement.is_mandatory = bool(data.get("is_mandatory", True))
        requirement.sequence = int(data.get("sequence") or 0)


def _upsert_task_materials(task: Task, materials: List[Dict[str, Any]], document_id: int) -> None:
    existing = {
        _normal(item.material_code or item.material_name): item for item in task.materials
    }
    for data in materials:
        key = _normal(data.get("material_code") or data.get("material_name"))
        material = existing.get(key)
        if not material:
            material = TaskMaterialSpecification(task_id=task.id, material_name=data["material_name"])
            task.materials.append(material)
            existing[key] = material
        for field in (
            "material_code", "material_name", "category", "technical_specification",
            "standard_reference", "grade", "approved_manufacturer", "dimensions",
            "unit", "planned_quantity", "certificate_required", "test_required",
            "approval_required", "source_page", "revision", "sequence",
        ):
            setattr(material, field, data.get(field))
        material.source_document_id = document_id


def _apply_task_data(
    db: Session,
    task: Task,
    data: Dict[str, Any],
    document_id: int,
    project_id: int,
    assign_pic: bool = False,
) -> None:
    task.title = data["title"]
    task.description = data.get("description")
    task.priority = data.get("priority") or TaskPriority.MEDIUM.value
    task.deadline = _datetime_value(data.get("deadline"))
    division = _find_division(db, project_id, data.get("division_name"))
    if division:
        task.division_id = division.id
    if assign_pic:
        allowed_role_codes = {role["code"] for role in active_pic_roles(db, project_id)}
        project_role = resolve_task_project_role(data, allowed_role_codes)
        assignment = select_task_pic(
            db,
            project_id=project_id,
            requested_project_role=project_role,
        )
        if assignment:
            task.assigned_to = assignment.user_id
            task.division_id = assignment.division_id
    if not task.specification:
        task.specification = TaskSpecification(
            wbs_code=data["wbs_code"],
            acceptance_criteria=data.get("acceptance_criteria") or "Wajib diverifikasi manager.",
        )
    specification = task.specification
    specification.wbs_code = data["wbs_code"]
    specification.work_package = data.get("work_package")
    specification.location = data.get("location")
    specification.acceptance_criteria = data.get("acceptance_criteria") or "Wajib diverifikasi manager."
    specification.reporting_instructions = data.get("reporting_instructions")
    specification.required_photo_count = int(data.get("required_photo_count") or 0)
    specification.required_document_count = int(data.get("required_document_count") or 0)
    specification.source_document_id = document_id
    _upsert_task_requirements(task, data.get("requirements") or [])
    _upsert_task_materials(task, data.get("materials") or [], document_id)


def apply_sync_plan(
    db: Session,
    *,
    plan: Dict[str, Any],
    selected_change_ids: Iterable[str],
    actor_id: int,
) -> Dict[str, Any]:
    selected = set(selected_change_ids)
    available = {item["id"]: item for item in plan.get("changes", [])}
    unknown = selected.difference(available)
    if unknown:
        raise ValueError(f"Perubahan tidak dikenal: {', '.join(sorted(unknown))}")

    project_id = int(plan["project"]["id"])
    document_id = int(plan["document"]["id"])
    project = db.query(Project).filter(Project.id == project_id).first()
    document = db.query(Document).filter(Document.id == document_id, Document.project_id == project_id).first()
    if not project or not document:
        raise ValueError("Proyek atau dokumen sinkronisasi tidak ditemukan")

    applied = {"project_updates": 0, "divisions_created": 0, "tasks_created": 0, "tasks_updated": 0}
    task_changes = []
    revision_impacted_tasks = []
    for change_id in selected:
        change = available[change_id]
        if change["entity"] == "project":
            field = change["field"]
            value = change["after"]
            if field in ("start_date", "end_date"):
                value = _datetime_value(value)
            setattr(project, field, value)
            applied["project_updates"] += 1
        elif change["entity"] == "division":
            data = change["after"]
            if not _find_division(db, project_id, data["division_name"]):
                db.add(Division(project_id=project_id, division_name=data["division_name"], description=data.get("description")))
                db.flush()
                applied["divisions_created"] += 1
        elif change["entity"] == "task":
            task_changes.append(change)

    db.flush()
    specifications = db.query(TaskSpecification).join(Task).filter(Task.project_id == project_id).all()
    tasks_by_wbs = {item.wbs_code: item.task for item in specifications}
    parent_links = []
    for change in task_changes:
        data = change["after"]
        task = tasks_by_wbs.get(data["wbs_code"])
        created = task is None
        if created:
            task = Task(
                title=data["title"], project_id=project_id, created_by=actor_id,
                ai_generated=True, ai_source=document.file_name,
            )
            db.add(task)
            db.flush()
            applied["tasks_created"] += 1
        else:
            applied["tasks_updated"] += 1
            revision_impacted_tasks.append(task)
        _apply_task_data(
            db,
            task,
            data,
            document_id,
            project_id,
            assign_pic=created,
        )
        db.flush()
        tasks_by_wbs[data["wbs_code"]] = task
        parent_links.append((task, data.get("parent_wbs")))

    for task, parent_wbs in parent_links:
        parent = tasks_by_wbs.get(parent_wbs) if parent_wbs else None
        if parent and parent.id != task.id:
            task.parent_task_id = parent.id

    db.flush()
    applied["revision_impacts"] = mark_tasks_revision_impacted(
        db, revision_impacted_tasks, document.file_name,
    )
    recalculate_project_controls(db, project_id)
    applied["project_progress"] = project.progress_percent
    applied["selected_changes"] = len(selected)
    return applied
