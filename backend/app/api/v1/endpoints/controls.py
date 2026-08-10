from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import (
    CommunicationType, InspectionRequest, MaterialApproval, NonConformance, Project, Task,
    ProductivityBenchmark, TaskControl, TaskDependency, TaskMaterialSpecification, TaskPriority, TaskStatus, User,
    UserRole, VendorProfile, VendorRateCard,
)
from app.schemas.schemas import (
    InspectionCreate, InspectionDecision, InspectionResponse, MaterialApprovalDecision,
    MaterialApprovalResponse, NonConformanceResponse, NonConformanceUpdate,
    ProductivityBenchmarkCreate, ProductivityBenchmarkResponse, ProductivityBenchmarkUpdate,
    TaskControlResponse, TaskControlUpsert, TaskDependencyCreate, TaskDependencyResponse,
    VendorProfileCreate, VendorProfileResponse, VendorProfileUpdate,
    VendorRateCardCreate, VendorRateCardResponse,
)
from app.services.audit_service import log_audit
from app.services.communication_service import add_communication_message, ensure_communication_from_source
from app.services.project_controls import (
    get_or_create_task_control, my_work_summary, project_controls_summary,
    recalculate_project_controls, refresh_handover_dossier, serialize_handover,
    task_gate_snapshot,
)
from app.services.report_workflow import (
    can_access_task, ensure_project_access, ensure_task_access,
)
from app.services.project_role_catalog import is_financial_project_role

router = APIRouter(prefix="/controls", tags=["Construction Project Controls"])
REVIEW_ROLES = (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)


def _get_task(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    return task


def _get_project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    return project


def _scope_summary_for_user(result: dict, project: Project, user: User) -> dict:
    if user.role in REVIEW_ROLES:
        return result
    can_view_financials = any(
        item.user_id == user.id and item.is_active and is_financial_project_role(item.project_role)
        for item in project.memberships
    )

    allowed_task_ids = {
        task.id for task in project.tasks if can_access_task(user, task)
    }
    result["tasks"] = [row for row in result["tasks"] if row["id"] in allowed_task_ids]
    result["lookahead"] = [row for row in result["lookahead"] if row["id"] in allowed_task_ids]
    result["materials"] = [row for row in result["materials"] if row["task_id"] in allowed_task_ids]
    result["inspections"] = [row for row in result["inspections"] if row["task_id"] in allowed_task_ids]
    result["ncrs"] = [row for row in result["ncrs"] if row["task_id"] in allowed_task_ids]
    result["overdue_rfis"] = [
        row for row in result["overdue_rfis"]
        if row["related_task_id"] in allowed_task_ids or row["assigned_to"] == user.id
    ]
    result["handover"] = [
        row for row in result["handover"] if row["task_id"] in allowed_task_ids
    ]

    if not can_view_financials:
        for row in result["tasks"]:
            row["boq_value"] = 0
            row["budget_cost"] = 0
            row["actual_cost"] = 0
            row["internal_material_cost"] = 0
            row["internal_labor_cost"] = 0
            row["internal_equipment_cost"] = 0
            row["internal_overhead_cost"] = 0
            row["internal_risk_cost"] = 0
            if row.get("vendor_strategy"):
                row["vendor_strategy"]["make_or_buy"] = {
                    "recommendation": "restricted",
                    "label": "Analisis biaya dibatasi untuk role manajerial/komersial",
                    "data_confidence": "restricted",
                    "boq_value": 0,
                    "quantity": row.get("planned_quantity") or 0,
                    "unit": row.get("unit"),
                    "internal": None,
                    "best_vendor": None,
                    "candidates": [],
                    "candidate_count": 0,
                    "reasons": ["Data biaya internal/vendor tidak ditampilkan untuk role ini."],
                }
        for row in result["lookahead"]:
            row["boq_value"] = 0
            row["budget_cost"] = 0
            row["actual_cost"] = 0
            row["internal_material_cost"] = 0
            row["internal_labor_cost"] = 0
            row["internal_equipment_cost"] = 0
            row["internal_overhead_cost"] = 0
            row["internal_risk_cost"] = 0
            if row.get("vendor_strategy"):
                row["vendor_strategy"]["make_or_buy"] = {
                    "recommendation": "restricted",
                    "label": "Analisis biaya dibatasi untuk role manajerial/komersial",
                    "data_confidence": "restricted",
                    "boq_value": 0,
                    "quantity": row.get("planned_quantity") or 0,
                    "unit": row.get("unit"),
                    "internal": None,
                    "best_vendor": None,
                    "candidates": [],
                    "candidate_count": 0,
                    "reasons": ["Data biaya internal/vendor tidak ditampilkan untuk role ini."],
                }
        result["project"]["contract_value"] = None
        result["metrics"]["budget_cost"] = 0
        result["metrics"]["actual_cost"] = 0
        result["metrics"]["make_or_buy_review_count"] = 0
        result["metrics"]["vendor_saving_potential"] = 0
    result["metrics"]["task_count"] = len(result["tasks"])
    result["metrics"]["pending_task_approval_count"] = sum(
        1 for row in result["tasks"] if row.get("approval_status") == "pending"
    )
    result["metrics"]["blocked_task_count"] = sum(
        1 for row in result["tasks"] if row["status"] == TaskStatus.BLOCKED.value
    )
    result["metrics"]["start_blocker_count"] = sum(
        len(row["gate"]["start_blockers"]) for row in result["tasks"]
    )
    result["metrics"]["completion_blocker_count"] = sum(
        len(row["gate"]["completion_blockers"]) for row in result["tasks"]
    )
    result["metrics"]["pending_material_count"] = sum(
        1 for row in result["materials"] if row["status"] != "approved"
    )
    result["metrics"]["pending_inspection_count"] = sum(
        1 for row in result["inspections"] if row["status"] == "pending"
    )
    result["metrics"]["open_ncr_count"] = sum(
        1 for row in result["ncrs"] if row["status"] != "closed"
    )
    result["metrics"]["overdue_rfi_count"] = len(result["overdue_rfis"])
    result["metrics"]["handover_item_count"] = len(result["handover"])
    result["metrics"]["vendor_review_count"] = sum(
        1 for row in result["tasks"]
        if row.get("vendor_strategy", {}).get("recommendation") in ("vendor_review", "vendor_recommended")
    )
    result["metrics"]["vendor_recommended_count"] = sum(
        1 for row in result["tasks"]
        if row.get("vendor_strategy", {}).get("recommendation") == "vendor_recommended"
    )
    return result


@router.get("/my-work")
def get_my_work(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return my_work_summary(db, current_user)


@router.get("/projects/{project_id}/summary")
def get_project_controls_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    result = project_controls_summary(db, project)
    result = _scope_summary_for_user(result, project, current_user)
    db.commit()
    return result


@router.get("/projects/{project_id}/vendors", response_model=List[VendorProfileResponse])
def list_project_vendors(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    return (
        db.query(VendorProfile)
        .filter((VendorProfile.project_id == project.id) | (VendorProfile.project_id.is_(None)))
        .order_by(VendorProfile.specialty, VendorProfile.vendor_name)
        .all()
    )


@router.post("/projects/{project_id}/vendors", response_model=VendorProfileResponse, status_code=201)
def create_project_vendor(
    project_id: int,
    data: VendorProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    vendor = VendorProfile(
        project_id=project.id,
        **data.model_dump(exclude={"rate_cards"}),
    )
    db.add(vendor)
    db.flush()
    for rate_data in data.rate_cards:
        db.add(VendorRateCard(vendor_id=vendor.id, **rate_data.model_dump()))
    log_audit(
        db, actor_id=current_user.id, action="vendor.created",
        entity_type="vendor", entity_id=vendor.id, project_id=project.id,
        summary=f"Vendor dibuat: {vendor.vendor_name}",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/vendors/{vendor_id}", response_model=VendorProfileResponse)
def update_vendor_profile(
    vendor_id: int,
    data: VendorProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    vendor = db.query(VendorProfile).filter(VendorProfile.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor tidak ditemukan")
    if vendor.project:
        ensure_project_access(current_user, vendor.project)
    before = {
        "vendor_name": vendor.vendor_name,
        "specialty": vendor.specialty,
        "is_approved": vendor.is_approved,
        "rating": vendor.rating,
    }
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vendor, field, value)
    log_audit(
        db, actor_id=current_user.id, action="vendor.updated",
        entity_type="vendor", entity_id=vendor.id, project_id=vendor.project_id,
        summary=f"Vendor diperbarui: {vendor.vendor_name}",
        before=before, after=data.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(vendor)
    return vendor


@router.post("/vendors/{vendor_id}/rates", response_model=VendorRateCardResponse, status_code=201)
def create_vendor_rate(
    vendor_id: int,
    data: VendorRateCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    vendor = db.query(VendorProfile).filter(VendorProfile.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor tidak ditemukan")
    if vendor.project:
        ensure_project_access(current_user, vendor.project)
    rate = VendorRateCard(vendor_id=vendor.id, **data.model_dump())
    db.add(rate)
    db.flush()
    log_audit(
        db, actor_id=current_user.id, action="vendor.rate_created",
        entity_type="vendor_rate", entity_id=rate.id, project_id=vendor.project_id,
        summary=f"Rate vendor dibuat: {vendor.vendor_name} - {rate.work_category}",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(rate)
    return rate


@router.get("/projects/{project_id}/productivity", response_model=List[ProductivityBenchmarkResponse])
def list_productivity_benchmarks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    return (
        db.query(ProductivityBenchmark)
        .filter((ProductivityBenchmark.project_id == project.id) | (ProductivityBenchmark.project_id.is_(None)))
        .order_by(ProductivityBenchmark.work_category, ProductivityBenchmark.unit, ProductivityBenchmark.output_per_day.desc())
        .all()
    )


@router.post("/projects/{project_id}/productivity", response_model=ProductivityBenchmarkResponse, status_code=201)
def create_productivity_benchmark(
    project_id: int,
    data: ProductivityBenchmarkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    benchmark = ProductivityBenchmark(project_id=project.id, **data.model_dump())
    db.add(benchmark)
    db.flush()
    log_audit(
        db, actor_id=current_user.id, action="productivity.created",
        entity_type="productivity_benchmark", entity_id=benchmark.id, project_id=project.id,
        summary=f"Benchmark produktivitas dibuat: {benchmark.work_category} {benchmark.output_per_day:g} {benchmark.unit}/hari",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(benchmark)
    return benchmark


@router.patch("/productivity/{benchmark_id}", response_model=ProductivityBenchmarkResponse)
def update_productivity_benchmark(
    benchmark_id: int,
    data: ProductivityBenchmarkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    benchmark = db.query(ProductivityBenchmark).filter(ProductivityBenchmark.id == benchmark_id).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark produktivitas tidak ditemukan")
    if benchmark.project:
        ensure_project_access(current_user, benchmark.project)
    before = {
        "work_category": benchmark.work_category,
        "unit": benchmark.unit,
        "output_per_day": benchmark.output_per_day,
        "crew_size": benchmark.crew_size,
        "labor_cost_per_day": benchmark.labor_cost_per_day,
    }
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(benchmark, field, value)
    log_audit(
        db, actor_id=current_user.id, action="productivity.updated",
        entity_type="productivity_benchmark", entity_id=benchmark.id, project_id=benchmark.project_id,
        summary=f"Benchmark produktivitas diperbarui: {benchmark.work_category}",
        before=before, after=data.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(benchmark)
    return benchmark


@router.post("/projects/{project_id}/baseline/bootstrap")
def bootstrap_project_baseline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    created = 0
    for task in project.tasks:
        existing = db.query(TaskControl).filter(TaskControl.task_id == task.id).first()
        if not existing:
            get_or_create_task_control(db, task)
            created += 1
    log_audit(
        db, actor_id=current_user.id, action="controls.baseline_bootstrapped",
        entity_type="project", entity_id=project.id, project_id=project.id,
        summary=f"Baseline control dibuat untuk {created} task",
        after={"created_task_controls": created},
    )
    db.commit()
    return {"created": created, "task_count": len(project.tasks)}


@router.get("/tasks/{task_id}/gate")
def get_task_gate(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _get_task(db, task_id)
    ensure_task_access(current_user, task)
    return task_gate_snapshot(db, task)


@router.get("/tasks/{task_id}/plan", response_model=TaskControlResponse)
def get_task_plan(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    task = _get_task(db, task_id)
    ensure_task_access(current_user, task)
    control = get_or_create_task_control(db, task)
    db.commit()
    db.refresh(control)
    return control


@router.put("/tasks/{task_id}/plan", response_model=TaskControlResponse)
def update_task_plan(
    task_id: int,
    data: TaskControlUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    task = _get_task(db, task_id)
    ensure_task_access(current_user, task)
    control = get_or_create_task_control(db, task)
    before = {
        "planned_start": control.planned_start,
        "planned_finish": control.planned_finish,
        "planned_quantity": control.planned_quantity,
        "boq_value": control.boq_value,
        "budget_cost": control.budget_cost,
        "internal_material_cost": control.internal_material_cost,
        "internal_labor_cost": control.internal_labor_cost,
        "internal_equipment_cost": control.internal_equipment_cost,
        "internal_overhead_cost": control.internal_overhead_cost,
        "internal_risk_cost": control.internal_risk_cost,
    }
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(control, field, value)
    if control.planned_start and control.planned_finish and control.planned_finish < control.planned_start:
        raise HTTPException(status_code=400, detail="Tanggal selesai baseline tidak boleh sebelum tanggal mulai")
    if control.planned_finish:
        task.deadline = control.planned_finish
    recalculate_project_controls(db, task.project_id)
    log_audit(
        db, actor_id=current_user.id, action="controls.task_plan_updated",
        entity_type="task_control", entity_id=control.id, project_id=task.project_id,
        summary=f"Baseline, volume, resource, atau biaya diperbarui: {task.title}",
        before=before, after=data.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(control)
    return control


@router.post("/tasks/{task_id}/dependencies", response_model=TaskDependencyResponse, status_code=201)
def create_dependency(
    task_id: int,
    data: TaskDependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    task = _get_task(db, task_id)
    predecessor = _get_task(db, data.depends_on_task_id)
    ensure_task_access(current_user, task)
    ensure_task_access(current_user, predecessor)
    if task.project_id != predecessor.project_id:
        raise HTTPException(status_code=400, detail="Dependency harus berada dalam proyek yang sama")
    if task.id == predecessor.id:
        raise HTTPException(status_code=400, detail="Task tidak dapat bergantung pada dirinya sendiri")
    existing = db.query(TaskDependency).filter(
        TaskDependency.task_id == task.id,
        TaskDependency.depends_on_task_id == predecessor.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Dependency sudah tersedia")
    dependency = TaskDependency(task_id=task.id, **data.model_dump())
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.delete("/dependencies/{dependency_id}", status_code=204)
def delete_dependency(
    dependency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    dependency = db.query(TaskDependency).filter(TaskDependency.id == dependency_id).first()
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency tidak ditemukan")
    ensure_task_access(current_user, dependency.task)
    db.delete(dependency)
    db.commit()


@router.patch("/materials/{material_id}/approval", response_model=MaterialApprovalResponse)
def decide_material_approval(
    material_id: int,
    data: MaterialApprovalDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    material = db.query(TaskMaterialSpecification).filter(
        TaskMaterialSpecification.id == material_id,
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material tidak ditemukan")
    ensure_task_access(current_user, material.task)
    if data.status in ("approved", "rejected") and current_user.role not in REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Keputusan material approval memerlukan manager")
    approval = db.query(MaterialApproval).filter(MaterialApproval.material_id == material.id).first()
    if not approval:
        approval = MaterialApproval(material_id=material.id)
        db.add(approval)
        db.flush()
    approval.status = data.status
    approval.note = data.note
    now = datetime.utcnow()
    if data.status == "submitted":
        approval.submitted_by = current_user.id
        approval.submitted_at = now
    if data.status in ("approved", "rejected"):
        approval.decided_by = current_user.id
        approval.decided_at = now
    log_audit(
        db, actor_id=current_user.id, action=f"material.{data.status}",
        entity_type="material_approval", entity_id=approval.id,
        project_id=material.task.project_id,
        summary=f"Material {material.material_name}: {data.status}",
        after={"material_id": material.id, "status": data.status, "note": data.note},
    )
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/inspections", response_model=InspectionResponse, status_code=201)
def create_inspection(
    data: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _get_task(db, data.task_id)
    ensure_task_access(current_user, task)
    if task.project_id != data.project_id:
        raise HTTPException(status_code=400, detail="Task tidak berasal dari proyek inspeksi")
    inspection = InspectionRequest(**data.model_dump(), requested_by=current_user.id)
    db.add(inspection)
    db.flush()
    log_audit(
        db, actor_id=current_user.id, action="inspection.requested",
        entity_type="inspection", entity_id=inspection.id, project_id=task.project_id,
        summary=f"Inspection request dibuat: {inspection.title}",
        after={"task_id": task.id, "inspection_type": inspection.inspection_type},
    )
    db.commit()
    db.refresh(inspection)
    return inspection


@router.patch("/inspections/{inspection_id}/decision", response_model=InspectionResponse)
def decide_inspection(
    inspection_id: int,
    data: InspectionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    inspection = db.query(InspectionRequest).filter(InspectionRequest.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection request tidak ditemukan")
    ensure_task_access(current_user, inspection.task)
    inspection.status = data.status
    inspection.result_note = data.result_note
    inspection.inspected_by = current_user.id
    inspection.inspected_at = datetime.utcnow()
    task = inspection.task

    if data.status == "failed":
        existing = db.query(NonConformance).filter(
            NonConformance.inspection_id == inspection.id,
            NonConformance.status.in_(["open", "corrective_action", "ready_for_close"]),
        ).first()
        if not existing:
            sequence = db.query(NonConformance).filter(
                NonConformance.project_id == inspection.project_id,
            ).count() + 1
            ncr = NonConformance(
                project_id=inspection.project_id,
                task_id=inspection.task_id,
                inspection_id=inspection.id,
                ncr_number=f"NCR-{inspection.project_id:03d}-{sequence:04d}",
                title=data.ncr_title or f"Failed inspection: {inspection.title}",
                description=data.result_note,
                severity=data.ncr_severity,
                assigned_to=data.ncr_assigned_to or task.assigned_to,
                due_date=data.ncr_due_date,
            )
            db.add(ncr)
            db.flush()
            ensure_communication_from_source(
                db,
                source_type="ncr",
                source_id=ncr.id,
                project_id=ncr.project_id,
                created_by=current_user.id,
                subject=f"{ncr.ncr_number}: {ncr.title}",
                description=ncr.description,
                communication_type=CommunicationType.ESCALATION if ncr.severity == "critical" else CommunicationType.ISSUE,
                priority=TaskPriority.CRITICAL if ncr.severity == "critical" else TaskPriority.HIGH,
                assigned_to=ncr.assigned_to,
                related_task_id=ncr.task_id,
                due_date=ncr.due_date,
                location=task.specification.location if task.specification else None,
                system_message=f"Inspection gagal dan NCR dibuat: {ncr.ncr_number}. {ncr.description or ''}",
            )
        task.status = TaskStatus.BLOCKED

    log_audit(
        db, actor_id=current_user.id, action=f"inspection.{data.status}",
        entity_type="inspection", entity_id=inspection.id, project_id=inspection.project_id,
        summary=f"Inspection {inspection.title}: {data.status}",
        after=data.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(inspection)
    return inspection


@router.patch("/ncr/{ncr_id}", response_model=NonConformanceResponse)
def update_ncr(
    ncr_id: int,
    data: NonConformanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ncr = db.query(NonConformance).filter(NonConformance.id == ncr_id).first()
    if not ncr:
        raise HTTPException(status_code=404, detail="NCR tidak ditemukan")
    if current_user.role in REVIEW_ROLES:
        ensure_task_access(current_user, ncr.task)
    if data.status == "closed" and current_user.role not in REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Penutupan NCR memerlukan manager")
    if current_user.role not in REVIEW_ROLES and ncr.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="NCR tidak ditugaskan kepada akun ini")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ncr, field, value)
    if data.status == "closed":
        if not (ncr.corrective_action or "").strip():
            raise HTTPException(status_code=400, detail="Corrective action wajib sebelum NCR ditutup")
        ncr.closed_by = current_user.id
        ncr.closed_at = datetime.utcnow()
    communication = ensure_communication_from_source(
        db,
        source_type="ncr",
        source_id=ncr.id,
        project_id=ncr.project_id,
        created_by=current_user.id,
        subject=f"{ncr.ncr_number}: {ncr.title}",
        description=ncr.description,
        communication_type=CommunicationType.ESCALATION if ncr.severity == "critical" else CommunicationType.ISSUE,
        priority=TaskPriority.CRITICAL if ncr.severity == "critical" else TaskPriority.HIGH,
        assigned_to=ncr.assigned_to,
        related_task_id=ncr.task_id,
        due_date=ncr.due_date,
        location=ncr.task.specification.location if ncr.task and ncr.task.specification else None,
        system_message=f"NCR dibuat/terhubung: {ncr.ncr_number}.",
    )
    update_note = data.corrective_action or f"Status NCR diperbarui menjadi {ncr.status}."
    add_communication_message(
        db,
        communication,
        update_note,
        actor_id=current_user.id,
        message_type="status_update",
        notify_participants=True,
    )
    log_audit(
        db, actor_id=current_user.id, action="ncr.updated", entity_type="ncr",
        entity_id=ncr.id, project_id=ncr.project_id,
        summary=f"{ncr.ncr_number} diperbarui menjadi {ncr.status}",
        after=data.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(ncr)
    return ncr


@router.post("/tasks/{task_id}/revision/clear")
def clear_revision_impact(
    task_id: int,
    note: str = "Dampak revisi telah ditinjau",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    task = _get_task(db, task_id)
    ensure_task_access(current_user, task)
    control = get_or_create_task_control(db, task)
    control.revision_attention_required = False
    control.revision_note = note
    log_audit(
        db, actor_id=current_user.id, action="revision.impact_cleared",
        entity_type="task_control", entity_id=control.id, project_id=task.project_id,
        summary=f"Dampak revisi task ditinjau: {task.title}", after={"note": note},
    )
    db.commit()
    return task_gate_snapshot(db, task)


@router.post("/projects/{project_id}/handover/refresh")
def refresh_project_handover(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*REVIEW_ROLES)),
):
    project = _get_project(db, project_id)
    ensure_project_access(current_user, project)
    items = refresh_handover_dossier(db, project_id)
    db.commit()
    return [serialize_handover(item) for item in items]
