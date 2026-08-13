from datetime import datetime, timedelta
from collections import defaultdict
from math import ceil
import re
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.user import (
    ApprovalStatus, CommunicationItem, CommunicationStatus, CommunicationType, DailyReport, Division,
    DailyReportWorkflow, HandoverItem, InspectionRequest, MaterialApproval,
    NonConformance, Notification, ProductivityBenchmark, Project, ProjectMembership, ReportProgressEntry,
    ReportStatus, Task, TaskAttachment, TaskControl, TaskDependency, TaskPriority,
    TaskMaterialSpecification, TaskStatus, User, UserRole, VendorProfile, VendorRateCard,
)
from app.services.report_workflow import can_access_task


OPEN_NCR_STATUSES = ("open", "corrective_action", "ready_for_close")
OPEN_COMMUNICATION_STATUSES = (
    CommunicationStatus.DRAFT, CommunicationStatus.OPEN, CommunicationStatus.IN_REVIEW,
)
SPECIALIST_VENDOR_KEYWORDS = (
    "facade", "fasad", "hvac", "panel", "lift", "elevator", "waterproofing",
    "pancang", "bored pile", "testing", "commissioning", "fire alarm",
    "aluminium", "kaca", "post tension", "geoteknik", "precast",
)
SPECIAL_EQUIPMENT_KEYWORDS = (
    "crane", "excavator", "concrete pump", "bor", "bored pile", "scaffolding",
    "tower", "genset", "welding", "survey", "batching",
)
WORK_CATEGORY_KEYWORDS = {
    "structure": ("struktur", "beton", "kolom", "balok", "slab", "pile cap", "pondasi", "basement"),
    "facade": ("facade", "fasad", "aluminium", "kaca", "curtain wall"),
    "hvac": ("hvac", "ducting", "chiller", "ac", "mekanikal"),
    "electrical": ("panel", "lvmdp", "listrik", "elektrikal", "kabel"),
    "waterproofing": ("waterproofing", "waterstop", "membrane", "coating", "kedap air"),
    "finishing": ("finishing", "interior", "lobby", "granit", "gypsum", "plafon"),
    "hse": ("k3", "safety", "rambu", "keselamatan", "apd"),
    "testing": ("testing", "commissioning", "uji", "test"),
}
VENDOR_MANAGEMENT_FEE_RATE = 0.05


def get_or_create_task_control(db: Session, task: Task) -> TaskControl:
    control = db.query(TaskControl).filter(TaskControl.task_id == task.id).first()
    if control:
        return control
    control = TaskControl(
        task_id=task.id,
        planned_finish=task.deadline,
        location=task.specification.location if task.specification else None,
    )
    db.add(control)
    db.flush()
    return control


def task_gate_snapshots(
    db: Session,
    tasks: list[Task],
    controls_by_task: Optional[dict[int, TaskControl]] = None,
) -> dict[int, dict]:
    """Hitung gate banyak task dengan jumlah query konstan."""
    if not tasks:
        return {}
    task_ids = [task.id for task in tasks]
    controls_by_task = controls_by_task or {
        item.task_id: item
        for item in db.query(TaskControl).filter(TaskControl.task_id.in_(task_ids)).all()
    }

    dependencies_by_task = defaultdict(list)
    for item in db.query(TaskDependency).options(
        joinedload(TaskDependency.predecessor),
    ).filter(TaskDependency.task_id.in_(task_ids)).all():
        dependencies_by_task[item.task_id].append(item)

    materials_by_task = defaultdict(list)
    required_materials = db.query(TaskMaterialSpecification).filter(
        TaskMaterialSpecification.task_id.in_(task_ids),
        TaskMaterialSpecification.approval_required == True,
    ).all()
    for item in required_materials:
        materials_by_task[item.task_id].append(item)
    approval_by_material = {
        item.material_id: item
        for item in db.query(MaterialApproval).filter(
            MaterialApproval.material_id.in_([material.id for material in required_materials])
        ).all()
    } if required_materials else {}

    ncrs_by_task = defaultdict(list)
    for item in db.query(NonConformance).filter(
        NonConformance.task_id.in_(task_ids),
        NonConformance.status.in_(OPEN_NCR_STATUSES),
    ).all():
        ncrs_by_task[item.task_id].append(item)

    reports_by_task = defaultdict(list)
    for item in db.query(DailyReportWorkflow).filter(
        DailyReportWorkflow.task_id.in_(task_ids),
        DailyReportWorkflow.status == ReportStatus.APPROVED,
    ).all():
        reports_by_task[item.task_id].append(item)

    inspections_by_task = defaultdict(list)
    for item in db.query(InspectionRequest).filter(
        InspectionRequest.task_id.in_(task_ids),
        InspectionRequest.is_required == True,
        InspectionRequest.status != "cancelled",
    ).all():
        inspections_by_task[item.task_id].append(item)

    snapshots = {}
    for task in tasks:
        control = controls_by_task.get(task.id)
        dependencies = dependencies_by_task[task.id]
        required_task_materials = materials_by_task[task.id]
        open_ncrs = ncrs_by_task[task.id]
        approved_reports = reports_by_task[task.id]
        required_inspections = inspections_by_task[task.id]
        start_blockers = []
        completion_blockers = []

        if (task.approval_status or ApprovalStatus.APPROVED.value) != ApprovalStatus.APPROVED.value:
            start_blockers.append({
                "code": "task_pm_approval_required",
                "label": "Task belum approved oleh Project Manager",
                "entity_id": task.approval_id,
            })

        for dependency in dependencies:
            predecessor = dependency.predecessor
            if predecessor and predecessor.status != TaskStatus.DONE:
                start_blockers.append({
                    "code": "dependency_incomplete",
                    "label": f"Predecessor belum selesai: {predecessor.title}",
                    "entity_id": predecessor.id,
                })

        for material in required_task_materials:
            approval = approval_by_material.get(material.id)
            if not approval or approval.status != "approved":
                start_blockers.append({
                    "code": "material_not_approved",
                    "label": f"Material belum approved: {material.material_name}",
                    "entity_id": material.id,
                })

        for ncr in open_ncrs:
            start_blockers.append({
                "code": "open_ncr",
                "label": f"NCR masih terbuka: {ncr.ncr_number}",
                "entity_id": ncr.id,
            })

        if control and control.revision_attention_required:
            start_blockers.append({
                "code": "revision_review_required",
                "label": control.revision_note or "Revisi drawing/specification perlu ditinjau",
                "entity_id": control.id,
            })

        if not approved_reports:
            completion_blockers.append({
                "code": "approved_report_missing",
                "label": "Belum ada laporan lapangan yang disetujui",
            })
        elif not any(item.validation_passed for item in approved_reports):
            completion_blockers.append({
                "code": "evidence_incomplete",
                "label": "Laporan approved belum memenuhi validation/evidence gate",
            })

        if control and control.planned_quantity and control.planned_quantity > 0:
            actual_quantity = control.actual_quantity or 0
            if actual_quantity + 1e-9 < control.planned_quantity:
                completion_blockers.append({
                    "code": "boq_volume_incomplete",
                    "label": (
                        f"Volume BOQ belum selesai: {actual_quantity:g}/{control.planned_quantity:g} "
                        f"{control.unit or ''}"
                    ).strip(),
                    "entity_id": control.id,
                })

        if not required_inspections:
            completion_blockers.append({
                "code": "inspection_missing",
                "label": "Inspection request wajib belum dibuat",
            })
        elif any(item.status != "passed" for item in required_inspections):
            completion_blockers.append({
                "code": "inspection_not_passed",
                "label": "Seluruh inspeksi wajib harus berstatus passed",
            })

        completion_blockers.extend(start_blockers)
        snapshots[task.id] = {
            "task_id": task.id,
            "can_start": not start_blockers,
            "can_complete": not completion_blockers,
            "start_blockers": start_blockers,
            "completion_blockers": completion_blockers,
            "approved_report_count": len(approved_reports),
            "required_inspection_count": len(required_inspections),
            "passed_inspection_count": sum(1 for item in required_inspections if item.status == "passed"),
            "open_ncr_count": len(open_ncrs),
            "required_material_count": len(required_task_materials),
            "approved_material_count": sum(
                1 for material in required_task_materials
                if approval_by_material.get(material.id) and approval_by_material[material.id].status == "approved"
            ),
        }
    return snapshots


def task_gate_snapshot(db: Session, task: Task) -> dict:
    return task_gate_snapshots(db, [task])[task.id]


def recalculate_project_controls(db: Session, project_id: int) -> dict:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"progress_percent": 0, "budget_cost": 0, "actual_cost": 0}

    tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.approval_status == ApprovalStatus.APPROVED.value,
    ).all()
    controls = db.query(TaskControl).join(Task).filter(
        Task.project_id == project_id,
        Task.approval_status == ApprovalStatus.APPROVED.value,
    ).all()
    by_task = {item.task_id: item for item in controls}

    totals_by_task = {
        int(task_id): (float(quantity or 0), float(cost or 0))
        for task_id, quantity, cost in db.query(
            ReportProgressEntry.task_id,
            func.coalesce(func.sum(ReportProgressEntry.quantity_this_report), 0.0),
            func.coalesce(func.sum(ReportProgressEntry.cost_this_report), 0.0),
        ).filter(
            ReportProgressEntry.task_id.in_([task.id for task in tasks]),
            ReportProgressEntry.applied_at.isnot(None),
        ).group_by(ReportProgressEntry.task_id).all()
    } if tasks else {}

    for task in tasks:
        control = by_task.get(task.id)
        if not control:
            continue
        quantity, cost = totals_by_task.get(task.id, (0.0, 0.0))
        control.actual_quantity = quantity
        control.actual_cost = cost
        if control.planned_quantity and control.planned_quantity > 0:
            task.progress_percent = round(min(100, (control.actual_quantity / control.planned_quantity) * 100), 2)

    weighted = [
        (task, by_task[task.id].weight_percent)
        for task in tasks
        if task.id in by_task and by_task[task.id].weight_percent
    ]
    budget_weighted = [
        (task, by_task[task.id].budget_cost)
        for task in tasks
        if task.id in by_task and by_task[task.id].budget_cost > 0
    ]
    if weighted:
        denominator = sum(weight for _, weight in weighted)
        progress = sum((task.progress_percent or 0) * weight for task, weight in weighted) / denominator
    elif budget_weighted:
        denominator = sum(cost for _, cost in budget_weighted)
        progress = sum((task.progress_percent or 0) * cost for task, cost in budget_weighted) / denominator
    else:
        progress = sum(task.progress_percent or 0 for task in tasks) / len(tasks) if tasks else 0

    project.progress_percent = round(progress, 2)
    return {
        "progress_percent": project.progress_percent,
        "budget_cost": round(sum(item.budget_cost or 0 for item in controls), 2),
        "actual_cost": round(sum(item.actual_cost or 0 for item in controls), 2),
    }


def _task_weight_map(tasks: list[Task], controls_by_task: dict[int, TaskControl]) -> dict[int, float]:
    weighted = {
        task.id: float(controls_by_task[task.id].weight_percent or 0)
        for task in tasks
        if task.id in controls_by_task and (controls_by_task[task.id].weight_percent or 0) > 0
    }
    if not weighted:
        weighted = {
            task.id: float(controls_by_task[task.id].budget_cost or 0)
            for task in tasks
            if task.id in controls_by_task and (controls_by_task[task.id].budget_cost or 0) > 0
        }
    if not weighted:
        weighted = {task.id: 1.0 for task in tasks}
    denominator = sum(weighted.values()) or 1.0
    return {task_id: round((weight / denominator) * 100, 6) for task_id, weight in weighted.items()}


def build_s_curve(db: Session, tasks: list[Task], controls_by_task: dict[int, TaskControl]) -> list[dict]:
    approved_tasks = [
        task for task in tasks
        if (task.approval_status or ApprovalStatus.APPROVED.value) == ApprovalStatus.APPROVED.value
    ]
    planned_items = []
    for task in approved_tasks:
        control = controls_by_task.get(task.id)
        planned_finish = control.planned_finish if control and control.planned_finish else task.deadline
        if not planned_finish:
            continue
        planned_start = (
            control.planned_start if control and control.planned_start
            else task.created_at or task.project.start_date or planned_finish
        )
        if planned_finish < planned_start:
            planned_start = planned_finish
        planned_items.append((task, control, planned_start, planned_finish))
    if not planned_items:
        return []

    weights = _task_weight_map([task for task, _, _, _ in planned_items], controls_by_task)
    start = min(planned_start for _, _, planned_start, _ in planned_items)
    finish = max(planned_finish for _, _, _, planned_finish in planned_items)
    if finish < start:
        finish = start
    total_days = max(1, (finish.date() - start.date()).days)
    step_days = max(1, ceil(total_days / 11))
    points = {start.date(), finish.date(), datetime.utcnow().date()}
    cursor = start.date()
    while cursor < finish.date():
        points.add(cursor)
        cursor = cursor + timedelta(days=step_days)

    task_ids = [task.id for task, _, _, _ in planned_items]
    progress_entries = db.query(ReportProgressEntry).filter(
        ReportProgressEntry.task_id.in_(task_ids),
        ReportProgressEntry.applied_at.isnot(None),
    ).order_by(ReportProgressEntry.applied_at.asc()).all() if task_ids else []

    rows = []
    now_date = datetime.utcnow().date()
    for point in sorted(points):
        point_dt = datetime.combine(point, datetime.max.time())
        planned_percent = 0.0
        actual_percent = 0.0
        for task, control, planned_start, planned_finish in planned_items:
            weight = weights.get(task.id, 0)
            if point_dt < planned_start:
                planned_task_percent = 0.0
            elif point_dt >= planned_finish:
                planned_task_percent = 100.0
            else:
                duration = max(1, (planned_finish - planned_start).days)
                elapsed = max(0, (point_dt - planned_start).days)
                planned_task_percent = min(100.0, (elapsed / duration) * 100)
            planned_percent += planned_task_percent * weight / 100

            quantity_until_point = sum(
                entry.quantity_this_report or 0
                for entry in progress_entries
                if entry.task_id == task.id and entry.applied_at and entry.applied_at <= point_dt
            )
            if control and control.planned_quantity and control.planned_quantity > 0:
                actual_task_percent = min(100.0, (quantity_until_point / control.planned_quantity) * 100)
                if point >= now_date:
                    actual_task_percent = max(actual_task_percent, task.progress_percent or 0)
            else:
                actual_task_percent = task.progress_percent or 0 if point >= now_date else 0
            actual_percent += actual_task_percent * weight / 100

        rows.append({
            "date": point.isoformat(),
            "planned_percent": round(min(100, planned_percent), 2),
            "actual_percent": round(min(100, actual_percent), 2),
            "variance_percent": round(min(100, actual_percent) - min(100, planned_percent), 2),
        })
    return rows


def _money(value: Optional[float]) -> float:
    return round(float(value or 0), 2)


def _task_analysis_text(task: Task, include_acceptance: bool = False) -> str:
    parts = [
        task.title,
        task.description or "",
    ]
    if include_acceptance and task.specification:
        parts.append(task.specification.acceptance_criteria)
    for material in task.materials or []:
        parts.extend([
            material.material_name or "",
            material.category or "",
            material.technical_specification or "",
        ])
    return " ".join(parts).lower()


def _contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    if " " in keyword or "-" in keyword or len(keyword) <= 2:
        return keyword in text.split() if len(keyword) <= 2 else keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _detect_work_categories(task: Task) -> list[str]:
    text = _task_analysis_text(task)
    categories = [
        category for category, keywords in WORK_CATEGORY_KEYWORDS.items()
        if any(_contains_keyword(text, keyword) for keyword in keywords)
    ]
    return categories or ["general"]


def _control_quantity(control: Optional[TaskControl]) -> float:
    if control and control.planned_quantity and control.planned_quantity > 0:
        return float(control.planned_quantity)
    return 1.0


def _internal_cost_snapshot(
    control: Optional[TaskControl], technical_score: int, best_vendor_total: Optional[float],
    best_productivity: Optional[dict] = None,
) -> dict:
    boq_value = _money(control.boq_value if control else 0) or _money(control.budget_cost if control else 0)
    explicit_components = {
        "material": _money(control.internal_material_cost if control else 0),
        "labor": _money(control.internal_labor_cost if control else 0),
        "equipment": _money(control.internal_equipment_cost if control else 0),
        "overhead": _money(control.internal_overhead_cost if control else 0),
        "risk": _money(control.internal_risk_cost if control else 0),
    }
    explicit_total = sum(explicit_components.values())
    if explicit_total > 0:
        total = _money(explicit_total)
        return {
            "estimated": False,
            "components": explicit_components,
            "total_cost": total,
            "source": "task_control_internal_cost",
            "productivity_benchmark": best_productivity,
        }

    if best_productivity and best_productivity["total_cost"] > 0:
        return {
            "estimated": True,
            "components": best_productivity["components"],
            "total_cost": best_productivity["total_cost"],
            "source": "productivity_benchmark",
            "duration_days": best_productivity["duration_days"],
            "productivity_benchmark": best_productivity,
        }

    if boq_value > 0:
        risk_rate = 0.06 if technical_score < 35 else 0.09 if technical_score < 60 else 0.12
        material = boq_value * 0.42
        labor = boq_value * 0.20
        equipment = boq_value * 0.10
        overhead = boq_value * 0.08
        risk = boq_value * risk_rate
        components = {
            "material": _money(material),
            "labor": _money(labor),
            "equipment": _money(equipment),
            "overhead": _money(overhead),
            "risk": _money(risk),
        }
        return {
            "estimated": True,
            "components": components,
            "total_cost": _money(sum(components.values())),
            "source": "boq_value_heuristic",
            "productivity_benchmark": best_productivity,
        }

    if best_vendor_total:
        total = best_vendor_total * (1.05 if technical_score < 35 else 1.12)
        components = {
            "material": _money(total * 0.48),
            "labor": _money(total * 0.24),
            "equipment": _money(total * 0.10),
            "overhead": _money(total * 0.08),
            "risk": _money(total * 0.10),
        }
        return {
            "estimated": True,
            "components": components,
            "total_cost": _money(sum(components.values())),
            "source": "vendor_benchmark_heuristic",
            "productivity_benchmark": best_productivity,
        }

    return {
        "estimated": True,
        "components": explicit_components,
        "total_cost": 0,
        "source": "missing_cost_data",
        "productivity_benchmark": best_productivity,
    }


def _rate_matches_task(rate: VendorRateCard, task: Task, control: Optional[TaskControl], categories: list[str]) -> tuple[bool, int]:
    text = _task_analysis_text(task)
    score = 0
    scope_score = 0
    category = (rate.work_category or "").lower()
    if category in categories:
        scope_score += 42
    elif category and _contains_keyword(text, category):
        scope_score += 28

    keywords = [
        keyword.strip().lower()
        for keyword in (rate.work_keywords or "").replace(";", ",").split(",")
        if keyword.strip()
    ]
    matched_keywords = [keyword for keyword in keywords if _contains_keyword(text, keyword)]
    if matched_keywords:
        scope_score += min(28, len(matched_keywords) * 10)
    if scope_score <= 0:
        return False, 0
    score += scope_score

    if control and control.unit and rate.unit and control.unit.lower() == rate.unit.lower():
        score += 22
    elif rate.unit.lower() == "ls":
        score += 8

    if rate.vendor and rate.vendor.is_approved:
        score += 8
    return score >= 30, min(100, score)


def _vendor_candidate_snapshot(
    rate: VendorRateCard, quantity: float, match_score: int,
) -> dict:
    base_cost = _money((rate.unit_price or 0) * quantity)
    management_cost = _money((base_cost + (rate.mobilization_cost or 0)) * VENDOR_MANAGEMENT_FEE_RATE)
    vendor_quality_risk = max(0.0, (100 - float(rate.vendor.rating or 0)) / 100) * 0.08
    multiplier_risk = max(0.0, float(rate.risk_multiplier or 1) - 1) * 0.35
    risk_cost = _money((base_cost + (rate.mobilization_cost or 0)) * (vendor_quality_risk + multiplier_risk))
    total_cost = _money(base_cost + (rate.mobilization_cost or 0) + management_cost + risk_cost)
    return {
        "vendor_id": rate.vendor_id,
        "vendor_name": rate.vendor.vendor_name,
        "rate_id": rate.id,
        "specialty": rate.vendor.specialty,
        "work_category": rate.work_category,
        "unit": rate.unit,
        "unit_price": _money(rate.unit_price),
        "quantity": _money(quantity),
        "base_cost": base_cost,
        "mobilization_cost": _money(rate.mobilization_cost),
        "management_cost": management_cost,
        "risk_cost": risk_cost,
        "total_cost": total_cost,
        "lead_time_days": rate.lead_time_days,
        "rating": _money(rate.vendor.rating),
        "quality_score": _money(rate.vendor.quality_score),
        "delivery_score": _money(rate.vendor.delivery_score),
        "safety_score": _money(rate.vendor.safety_score),
        "match_score": match_score,
        "includes_material": rate.includes_material,
        "includes_labor": rate.includes_labor,
        "includes_equipment": rate.includes_equipment,
        "notes": rate.notes,
    }


def _vendor_candidates(
    db: Session,
    task: Task,
    control: Optional[TaskControl],
    rates: Optional[list[VendorRateCard]] = None,
) -> list[dict]:
    categories = _detect_work_categories(task)
    quantity = _control_quantity(control)
    if rates is None:
        rates = (
            db.query(VendorRateCard)
            .options(joinedload(VendorRateCard.vendor))
            .join(VendorProfile)
            .filter(VendorProfile.is_approved == True)
            .filter(
                (VendorProfile.project_id == task.project_id) |
                (VendorProfile.project_id.is_(None))
            )
            .all()
        )
    candidates = []
    now = datetime.utcnow()
    for rate in rates:
        if rate.valid_from and rate.valid_from > now:
            continue
        if rate.valid_until and rate.valid_until < now:
            continue
        matched, match_score = _rate_matches_task(rate, task, control, categories)
        if not matched:
            continue
        if rate.min_quantity and quantity < rate.min_quantity:
            match_score = max(0, match_score - 8)
        candidates.append(_vendor_candidate_snapshot(rate, quantity, match_score))
    return sorted(
        candidates,
        key=lambda item: (-item["match_score"], item["total_cost"], -item["rating"]),
    )


def _productivity_matches_task(
    benchmark: ProductivityBenchmark, task: Task, control: Optional[TaskControl], categories: list[str],
) -> tuple[bool, int]:
    text = _task_analysis_text(task, include_acceptance=True)
    score = 0
    category = (benchmark.work_category or "").lower()
    if category in categories:
        score += 42
    elif category and _contains_keyword(text, category):
        score += 28

    keywords = [
        keyword.strip().lower()
        for keyword in (benchmark.work_keywords or "").replace(";", ",").split(",")
        if keyword.strip()
    ]
    matched_keywords = [keyword for keyword in keywords if _contains_keyword(text, keyword)]
    if matched_keywords:
        score += min(28, len(matched_keywords) * 10)

    if control and control.unit and benchmark.unit and control.unit.lower() == benchmark.unit.lower():
        score += 24
    elif not control or not control.unit:
        score += 6

    score += int(min(6, max(0, (benchmark.confidence_score or 0) / 20)))
    return score >= 30, min(100, score)


def _productivity_candidate_snapshot(
    benchmark: ProductivityBenchmark, quantity: float, match_score: int,
) -> dict:
    duration_days = max(1, ceil(quantity / max(float(benchmark.output_per_day or 1), 0.0001)))
    material_cost = _money(quantity * (benchmark.material_cost_per_unit or 0))
    labor_cost = _money(duration_days * (benchmark.labor_cost_per_day or 0))
    equipment_cost = _money(duration_days * (benchmark.equipment_cost_per_day or 0))
    subtotal = material_cost + labor_cost + equipment_cost
    overhead_cost = _money(subtotal * ((benchmark.overhead_percent or 0) / 100))
    risk_cost = _money(subtotal * ((benchmark.risk_percent or 0) / 100))
    total_cost = _money(subtotal + overhead_cost + risk_cost)
    return {
        "benchmark_id": benchmark.id,
        "work_category": benchmark.work_category,
        "unit": benchmark.unit,
        "quantity": _money(quantity),
        "output_per_day": _money(benchmark.output_per_day),
        "duration_days": duration_days,
        "crew_size": benchmark.crew_size,
        "labor_cost_per_day": _money(benchmark.labor_cost_per_day),
        "equipment_cost_per_day": _money(benchmark.equipment_cost_per_day),
        "material_cost_per_unit": _money(benchmark.material_cost_per_unit),
        "components": {
            "material": material_cost,
            "labor": labor_cost,
            "equipment": equipment_cost,
            "overhead": overhead_cost,
            "risk": risk_cost,
        },
        "total_cost": total_cost,
        "match_score": match_score,
        "confidence_score": _money(benchmark.confidence_score),
        "source_label": benchmark.source_label,
        "notes": benchmark.notes,
    }


def _productivity_candidates(
    db: Session,
    task: Task,
    control: Optional[TaskControl],
    benchmarks: Optional[list[ProductivityBenchmark]] = None,
) -> list[dict]:
    categories = _detect_work_categories(task)
    quantity = _control_quantity(control)
    if benchmarks is None:
        benchmarks = (
            db.query(ProductivityBenchmark)
            .filter(
                (ProductivityBenchmark.project_id == task.project_id) |
                (ProductivityBenchmark.project_id.is_(None))
            )
            .all()
        )
    candidates = []
    for benchmark in benchmarks:
        matched, match_score = _productivity_matches_task(benchmark, task, control, categories)
        if not matched:
            continue
        candidates.append(_productivity_candidate_snapshot(benchmark, quantity, match_score))
    return sorted(
        candidates,
        key=lambda item: (-item["match_score"], item["total_cost"], -item["confidence_score"]),
    )


def make_or_buy_snapshot(
    db: Optional[Session], task: Task, control: Optional[TaskControl], technical_strategy: dict,
    vendor_rates: Optional[list[VendorRateCard]] = None,
    productivity_benchmarks: Optional[list[ProductivityBenchmark]] = None,
) -> dict:
    technical_score = int(technical_strategy.get("score") or 0)
    boq_value = _money(control.boq_value if control else 0) or _money(control.budget_cost if control else 0)
    candidates = _vendor_candidates(db, task, control, vendor_rates) if db else []
    best_vendor = candidates[0] if candidates else None
    productivity_candidates = _productivity_candidates(
        db, task, control, productivity_benchmarks,
    ) if db else []
    best_productivity = productivity_candidates[0] if productivity_candidates else None
    internal = _internal_cost_snapshot(
        control, technical_score, best_vendor["total_cost"] if best_vendor else None,
        best_productivity,
    )
    internal_total = internal["total_cost"]

    if boq_value > 0:
        internal["margin"] = _money(boq_value - internal_total)
        internal["margin_percent"] = round((internal["margin"] / boq_value) * 100, 2)
    else:
        internal["margin"] = None
        internal["margin_percent"] = None

    for candidate in candidates:
        candidate["saving_vs_internal"] = _money(internal_total - candidate["total_cost"]) if internal_total else 0
        if boq_value > 0:
            candidate["margin"] = _money(boq_value - candidate["total_cost"])
            candidate["margin_percent"] = round((candidate["margin"] / boq_value) * 100, 2)
        else:
            candidate["margin"] = None
            candidate["margin_percent"] = None

    reasons = []
    data_points = 0
    if boq_value > 0:
        data_points += 1
    if control and control.planned_quantity:
        data_points += 1
    if internal_total > 0:
        data_points += 1
    if best_productivity:
        data_points += 1
    if candidates:
        data_points += 1
    confidence = "high" if data_points >= 4 else "medium" if data_points >= 2 else "low"

    if not candidates:
        recommendation = "need_vendor_rate"
        label = "Butuh data harga vendor"
        reasons.append("Belum ada rate card vendor yang cocok dengan kategori, keyword, dan satuan pekerjaan.")
        if best_productivity:
            reasons.append(
                "Estimasi internal sudah memakai benchmark produktivitas "
                f"{best_productivity['output_per_day']:g} {best_productivity['unit']}/hari."
            )
    elif internal_total <= 0:
        recommendation = "need_internal_cost"
        label = "Butuh estimasi biaya internal"
        reasons.append("Harga vendor tersedia, tetapi estimasi biaya internal belum cukup untuk membandingkan margin.")
    else:
        saving = best_vendor["total_cost"] - internal_total
        saving_percent = (saving / internal_total) * 100 if internal_total else 0
        vendor_margin = best_vendor.get("margin")
        internal_margin = internal.get("margin")

        if best_vendor["total_cost"] <= internal_total * 0.92 and technical_score >= 35:
            recommendation = "vendor_recommended"
            label = "Vendor lebih menguntungkan dan teknisnya layak direview"
            reasons.append("Vendor terbaik lebih murah minimal 8% dari estimasi internal.")
        elif best_vendor["total_cost"] <= internal_total * 0.97:
            recommendation = "vendor_review"
            label = "Vendor perlu dibandingkan oleh PM/Procurement"
            reasons.append("Vendor terbaik sedikit lebih murah dari estimasi internal.")
        elif technical_score >= 60 and best_vendor["total_cost"] <= internal_total * 1.08:
            recommendation = "vendor_review"
            label = "Vendor layak direview karena risiko teknis tinggi"
            reasons.append("Biaya vendor masih dekat dengan internal, sementara kompleksitas teknis tinggi.")
        elif technical_score >= 35 and (control and control.planned_manpower and control.planned_manpower >= 20):
            recommendation = "hybrid_review"
            label = "Pertimbangkan internal dengan support vendor"
            reasons.append("Kapasitas internal terlihat berat sehingga opsi hybrid perlu dihitung.")
        elif best_productivity and best_vendor.get("lead_time_days") and best_productivity["duration_days"] > best_vendor["lead_time_days"] * 1.25:
            recommendation = "vendor_review"
            label = "Vendor layak direview karena durasi internal lebih panjang"
            reasons.append(
                "Benchmark produktivitas menunjukkan durasi internal lebih lambat dari lead time vendor."
            )
        else:
            recommendation = "internal_preferred"
            label = "Kerjakan internal lebih rasional"
            reasons.append("Estimasi internal masih lebih baik daripada vendor yang tersedia.")

        if best_productivity:
            reasons.append(
                "Produktivitas internal dihitung dari "
                f"{best_productivity['output_per_day']:g} {best_productivity['unit']}/hari, "
                f"durasi estimasi {best_productivity['duration_days']} hari."
            )
        if vendor_margin is not None and internal_margin is not None:
            delta = _money(vendor_margin - internal_margin)
            if delta > 0:
                reasons.append(f"Margin vendor lebih tinggi sekitar Rp {delta:,.0f}.")
            elif delta < 0:
                reasons.append(f"Margin internal lebih tinggi sekitar Rp {abs(delta):,.0f}.")
        if saving_percent > 0:
            reasons.append(f"Biaya vendor lebih tinggi sekitar {abs(round(saving_percent, 2))}% dari internal.")

    return {
        "recommendation": recommendation,
        "label": label,
        "data_confidence": confidence,
        "boq_value": boq_value,
        "quantity": _money(_control_quantity(control)),
        "unit": control.unit if control else None,
        "internal": internal,
        "productivity_benchmark": best_productivity,
        "productivity_candidates": productivity_candidates[:3],
        "best_vendor": best_vendor,
        "candidates": candidates[:3],
        "candidate_count": len(candidates),
        "reasons": reasons,
    }


def vendor_strategy_snapshot(
    task: Task, control: Optional[TaskControl], gate: dict, db: Optional[Session] = None,
    vendor_rates: Optional[list[VendorRateCard]] = None,
    productivity_benchmarks: Optional[list[ProductivityBenchmark]] = None,
) -> dict:
    title = f"{task.title} {task.description or ''}".lower()
    material_count = len(task.materials or [])
    technical_material_count = sum(
        1 for material in task.materials
        if material.certificate_required or material.test_required or material.approval_required
    )
    equipment_text = (control.planned_equipment or "").lower() if control else ""
    criteria = []

    def add(key: str, label: str, matched: bool, weight: int, reason: str) -> None:
        criteria.append({
            "key": key,
            "label": label,
            "matched": matched,
            "weight": weight,
            "reason": reason,
        })

    add(
        "specialist_scope",
        "Pekerjaan membutuhkan spesialis/vendor tersertifikasi",
        any(keyword in title for keyword in SPECIALIST_VENDOR_KEYWORDS),
        20,
        "Judul/deskripsi mengandung pekerjaan spesialis seperti fasad, HVAC, panel, waterproofing, testing, atau pekerjaan pondasi khusus.",
    )
    add(
        "technical_material",
        "Material membutuhkan submittal, sertifikat, approval, atau pengujian",
        technical_material_count >= 2,
        15,
        f"{technical_material_count}/{material_count} material memiliki kebutuhan approval, sertifikat, atau test.",
    )
    add(
        "special_equipment",
        "Membutuhkan alat khusus atau resource yang tidak selalu tersedia internal",
        any(keyword in equipment_text for keyword in SPECIAL_EQUIPMENT_KEYWORDS),
        15,
        control.planned_equipment if control and control.planned_equipment else "Belum ada alat khusus pada baseline.",
    )
    add(
        "high_quality_safety_risk",
        "Risiko mutu/K3 tinggi atau prioritas kritikal",
        task.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL),
        12,
        f"Prioritas task: {task.priority.value if task.priority else 'medium'}.",
    )
    add(
        "capacity_pressure",
        "Kapasitas internal berpotensi tidak cukup",
        bool(control and control.planned_manpower and control.planned_manpower >= 20),
        10,
        f"Rencana tenaga kerja: {control.planned_manpower if control else 0} orang.",
    )
    planned_finish = control.planned_finish if control and control.planned_finish else task.deadline
    add(
        "schedule_pressure",
        "Deadline dekat dengan progres rendah",
        bool(planned_finish and planned_finish <= datetime.utcnow() + timedelta(days=21) and (task.progress_percent or 0) < 50),
        10,
        f"Target: {planned_finish.date().isoformat() if planned_finish else 'belum ada'}; progress {task.progress_percent or 0}%.",
    )
    add(
        "gate_complexity",
        "Banyak gate teknis sebelum mulai/selesai",
        len(gate["start_blockers"]) + len(gate["completion_blockers"]) >= 3,
        10,
        f"{len(gate['start_blockers'])} start blocker dan {len(gate['completion_blockers'])} completion blocker.",
    )
    add(
        "packageable_scope",
        "Lingkup mudah dipaketkan sebagai pekerjaan vendor/subkon",
        any(keyword in title for keyword in ("instalasi", "fabrikasi", "pemasangan", "pengujian", "commissioning", "finishing")),
        8,
        "Lingkup terlihat sebagai paket kerja yang dapat dipisah dari pekerjaan harian internal.",
    )

    score = sum(item["weight"] for item in criteria if item["matched"])
    if score >= 60:
        recommendation = "vendor_recommended"
        label = "Direkomendasikan alih ke vendor"
    elif score >= 35:
        recommendation = "vendor_review"
        label = "Perlu review vendor oleh PM/Procurement"
    else:
        recommendation = "internal_preferred"
        label = "Masih layak dikerjakan internal"
    snapshot = {
        "score": min(100, score),
        "recommendation": recommendation,
        "label": label,
        "criteria": criteria,
    }
    snapshot["make_or_buy"] = make_or_buy_snapshot(
        db,
        task,
        control,
        snapshot,
        vendor_rates=vendor_rates,
        productivity_benchmarks=productivity_benchmarks,
    )
    return snapshot


def apply_approved_report(db: Session, report: DailyReport, actor_id: int) -> dict:
    task = report.workflow.task
    entry = report.progress_entry
    if entry:
        entry.applied_at = datetime.utcnow()
    db.flush()

    totals = recalculate_project_controls(db, report.project_id)
    db.flush()
    control = db.query(TaskControl).filter(TaskControl.task_id == task.id).first()
    if entry and control:
        entry.cumulative_quantity = control.actual_quantity
        entry.progress_after_approval = task.progress_percent or 0

    gate = task_gate_snapshot(db, task)
    if gate["can_complete"] and task.status == TaskStatus.REVIEW:
        task.status = TaskStatus.DONE
        task.progress_percent = 100
        recalculate_project_controls(db, report.project_id)
    elif task.status == TaskStatus.REVIEW:
        blocker_text = "; ".join(item["label"] for item in gate["completion_blockers"][:4])
        db.add(Notification(
            user_id=report.user_id,
            title="Laporan approved, task belum dapat ditutup",
            message=blocker_text,
            type="workflow_blocker",
            related_task_id=task.id,
            related_project_id=report.project_id,
        ))
    refresh_handover_dossier(db, report.project_id)
    return {"gate": gate, "project": totals}


def mark_tasks_revision_impacted(
    db: Session, tasks: Iterable[Task], document_name: str, revision: Optional[str] = None,
) -> int:
    count = 0
    for task in tasks:
        control = get_or_create_task_control(db, task)
        control.revision_attention_required = True
        control.revision_note = (
            f"Tinjau dampak revisi {revision or 'baru'} dari {document_name} sebelum pekerjaan dilanjutkan"
        )
        if task.status == TaskStatus.IN_PROGRESS:
            task.status = TaskStatus.BLOCKED
        count += 1
    return count


def refresh_handover_dossier(db: Session, project_id: int) -> list[HandoverItem]:
    approved_reports = db.query(DailyReport).join(DailyReportWorkflow).filter(
        DailyReport.project_id == project_id,
        DailyReportWorkflow.status == ReportStatus.APPROVED,
    ).all()
    for report in approved_reports:
        _upsert_handover(
            db, project_id, report.workflow.task_id, "approved_report",
            f"Approved field report #{report.id}", "daily_report", report.id,
        )
        for evidence in report.evidence:
            _upsert_handover(
                db, project_id, report.workflow.task_id, "report_evidence",
                evidence.file_name, "report_evidence", evidence.id,
            )

    inspections = db.query(InspectionRequest).filter(
        InspectionRequest.project_id == project_id,
        InspectionRequest.status == "passed",
    ).all()
    for inspection in inspections:
        _upsert_handover(
            db, project_id, inspection.task_id, "inspection_test",
            inspection.title, "inspection", inspection.id, inspection.document_id,
        )

    closed_ncrs = db.query(NonConformance).filter(
        NonConformance.project_id == project_id,
        NonConformance.status == "closed",
    ).all()
    for ncr in closed_ncrs:
        _upsert_handover(
            db, project_id, ncr.task_id, "closed_ncr",
            f"{ncr.ncr_number} - {ncr.title}", "ncr", ncr.id,
        )

    attachments = db.query(TaskAttachment).join(Task).filter(Task.project_id == project_id).all()
    for attachment in attachments:
        _upsert_handover(
            db, project_id, attachment.task_id, "task_attachment",
            attachment.file_name, "task_attachment", attachment.id, attachment.document_id,
        )
    db.flush()
    return db.query(HandoverItem).filter(HandoverItem.project_id == project_id).order_by(
        HandoverItem.category, HandoverItem.created_at,
    ).all()


def _upsert_handover(
    db: Session, project_id: int, task_id: Optional[int], category: str, title: str,
    source_type: str, source_id: int, document_id: Optional[int] = None,
) -> HandoverItem:
    item = db.query(HandoverItem).filter(
        HandoverItem.project_id == project_id,
        HandoverItem.source_type == source_type,
        HandoverItem.source_id == source_id,
    ).first()
    if not item:
        item = HandoverItem(
            project_id=project_id, task_id=task_id, category=category, title=title,
            source_type=source_type, source_id=source_id, document_id=document_id,
        )
        db.add(item)
    return item


def project_controls_summary(db: Session, project: Project) -> dict:
    tasks = db.query(Task).options(
        joinedload(Task.specification),
        selectinload(Task.materials),
    ).filter(Task.project_id == project.id).order_by(Task.deadline).all()
    controls = db.query(TaskControl).join(Task).filter(Task.project_id == project.id).all()
    by_task = {item.task_id: item for item in controls}
    gates_by_task = task_gate_snapshots(db, tasks, by_task)
    vendor_rates = (
        db.query(VendorRateCard)
        .options(joinedload(VendorRateCard.vendor))
        .join(VendorProfile)
        .filter(VendorProfile.is_approved == True)
        .filter(
            (VendorProfile.project_id == project.id) |
            (VendorProfile.project_id.is_(None))
        )
        .all()
    )
    productivity_benchmarks = db.query(ProductivityBenchmark).filter(
        (ProductivityBenchmark.project_id == project.id) |
        (ProductivityBenchmark.project_id.is_(None))
    ).all()
    now = datetime.utcnow()
    lookahead_end = now + timedelta(days=21)

    task_rows = []
    for task in tasks:
        control = by_task.get(task.id)
        gate = gates_by_task[task.id]
        task_rows.append({
            "id": task.id,
            "title": task.title,
            "wbs_code": task.specification.wbs_code if task.specification else None,
            "status": task.status.value,
            "approval_status": task.approval_status or ApprovalStatus.APPROVED.value,
            "approval_id": task.approval_id,
            "priority": task.priority.value,
            "assigned_to": task.assigned_to,
            "deadline": task.deadline,
            "planned_start": control.planned_start if control else None,
            "planned_finish": control.planned_finish if control else task.deadline,
            "location": control.location if control else None,
            "unit": control.unit if control else None,
            "planned_quantity": control.planned_quantity if control else None,
            "actual_quantity": control.actual_quantity if control else 0,
            "progress_percent": task.progress_percent,
            "boq_value": control.boq_value if control else 0,
            "budget_cost": control.budget_cost if control else 0,
            "actual_cost": control.actual_cost if control else 0,
            "internal_material_cost": control.internal_material_cost if control else 0,
            "internal_labor_cost": control.internal_labor_cost if control else 0,
            "internal_equipment_cost": control.internal_equipment_cost if control else 0,
            "internal_overhead_cost": control.internal_overhead_cost if control else 0,
            "internal_risk_cost": control.internal_risk_cost if control else 0,
            "planned_manpower": control.planned_manpower if control else None,
            "planned_equipment": control.planned_equipment if control else None,
            "gate": gate,
            "vendor_strategy": vendor_strategy_snapshot(
                task,
                control,
                gate,
                db,
                vendor_rates=vendor_rates,
                productivity_benchmarks=productivity_benchmarks,
            ),
        })

    material_rows = []
    materials = db.query(TaskMaterialSpecification).join(Task).filter(
        Task.project_id == project.id,
        TaskMaterialSpecification.approval_required == True,
    ).all()
    approvals = {
        item.material_id: item
        for item in db.query(MaterialApproval).filter(
            MaterialApproval.material_id.in_([material.id for material in materials])
        ).all()
    } if materials else {}
    for material in materials:
        approval = approvals.get(material.id)
        material_rows.append({
            "id": material.id,
            "task_id": material.task_id,
            "material_name": material.material_name,
            "material_code": material.material_code,
            "status": approval.status if approval else "pending",
            "approval_id": approval.id if approval else None,
            "note": approval.note if approval else None,
        })

    inspections = db.query(InspectionRequest).filter(InspectionRequest.project_id == project.id).order_by(
        InspectionRequest.due_date, InspectionRequest.created_at.desc(),
    ).all()
    ncrs = db.query(NonConformance).filter(NonConformance.project_id == project.id).order_by(
        NonConformance.created_at.desc(),
    ).all()
    overdue_rfis = db.query(CommunicationItem).filter(
        CommunicationItem.project_id == project.id,
        CommunicationItem.communication_type == CommunicationType.RFI,
        CommunicationItem.status.in_(OPEN_COMMUNICATION_STATUSES),
        CommunicationItem.due_date.isnot(None),
        CommunicationItem.due_date < now,
    ).all()
    dossier = refresh_handover_dossier(db, project.id)
    cost = recalculate_project_controls(db, project.id)
    s_curve = build_s_curve(db, tasks, by_task)
    vendor_review_count = sum(
        1 for row in task_rows
        if row["vendor_strategy"]["recommendation"] in ("vendor_review", "vendor_recommended")
    )
    vendor_recommended_count = sum(
        1 for row in task_rows
        if row["vendor_strategy"]["recommendation"] == "vendor_recommended"
    )
    make_or_buy_review_count = sum(
        1 for row in task_rows
        if row["vendor_strategy"]["make_or_buy"]["recommendation"] in (
            "vendor_review", "vendor_recommended", "hybrid_review",
        )
    )
    vendor_saving_potential = sum(
        max(0, (row["vendor_strategy"]["make_or_buy"].get("best_vendor") or {}).get("saving_vs_internal", 0) or 0)
        for row in task_rows
    )
    db.flush()

    return {
        "project": {
            "id": project.id, "name": project.project_name,
            "progress_percent": project.progress_percent,
            "contract_value": project.contract_value,
        },
        "setup": {
            "contract_ready": any(document.file_type.value == "contract" for document in project.documents),
            "wbs_ready": bool(tasks) and all(task.specification for task in tasks),
            "boq_baseline_ready": bool(controls) and all(item.planned_quantity is not None for item in controls),
            "schedule_ready": bool(controls) and all(item.planned_finish for item in controls),
            "organization_ready": bool(project.divisions) and bool(project.memberships),
            "document_structure_ready": bool(project.documents),
        },
        "metrics": {
            "task_count": len(tasks),
            "pending_task_approval_count": sum(
                1 for task in tasks
                if (task.approval_status or ApprovalStatus.APPROVED.value) == ApprovalStatus.PENDING.value
            ),
            "blocked_task_count": sum(1 for task in tasks if task.status == TaskStatus.BLOCKED),
            "start_blocker_count": sum(len(row["gate"]["start_blockers"]) for row in task_rows),
            "completion_blocker_count": sum(len(row["gate"]["completion_blockers"]) for row in task_rows),
            "pending_material_count": sum(1 for row in material_rows if row["status"] != "approved"),
            "pending_inspection_count": sum(1 for item in inspections if item.status == "pending"),
            "open_ncr_count": sum(1 for item in ncrs if item.status in OPEN_NCR_STATUSES),
            "overdue_rfi_count": len(overdue_rfis),
            "handover_item_count": len(dossier),
            "vendor_review_count": vendor_review_count,
            "vendor_recommended_count": vendor_recommended_count,
            "make_or_buy_review_count": make_or_buy_review_count,
            "vendor_saving_potential": round(vendor_saving_potential, 2),
            **cost,
        },
        "s_curve": s_curve,
        "lookahead": [
            row for row in task_rows
            if row["status"] != TaskStatus.DONE.value and (
                not row["planned_start"] or row["planned_start"] <= lookahead_end
            )
        ],
        "tasks": task_rows,
        "materials": material_rows,
        "inspections": [serialize_inspection(item) for item in inspections],
        "ncrs": [serialize_ncr(item) for item in ncrs],
        "overdue_rfis": [{
            "id": item.id, "subject": item.subject, "due_date": item.due_date,
            "assigned_to": item.assigned_to, "related_task_id": item.related_task_id,
        } for item in overdue_rfis],
        "handover": [serialize_handover(item) for item in dossier],
    }


def my_work_summary(db: Session, user: User) -> dict:
    task_query = db.query(Task).filter(Task.status != TaskStatus.DONE)
    accessible_project_ids = None
    if user.role != UserRole.DIRECTOR:
        accessible_project_ids = {
            item.project_id for item in db.query(ProjectMembership).filter(
                ProjectMembership.user_id == user.id,
                ProjectMembership.is_active == True,
            ).all()
        }
        accessible_project_ids.update(
            item.id for item in db.query(Project).filter(Project.owner_id == user.id).all()
        )
        accessible_project_ids.update(
            item.project_id for item in db.query(Division).filter(Division.manager_id == user.id).all()
        )
        task_query = task_query.filter(Task.project_id.in_(accessible_project_ids or [-1]))
    tasks = task_query.order_by(Task.deadline).limit(120).all()
    if user.role != UserRole.DIRECTOR:
        tasks = [task for task in tasks if can_access_task(user, task)]
    tasks = tasks[:30]
    gates_by_task = task_gate_snapshots(db, tasks)

    report_query = db.query(DailyReport).join(DailyReportWorkflow).filter(
        DailyReportWorkflow.status.in_([
            ReportStatus.NEEDS_REVISION, ReportStatus.READY_FOR_REVIEW, ReportStatus.VERIFIED,
        ])
    )
    if user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        report_query = report_query.filter(DailyReport.user_id == user.id)
    elif accessible_project_ids is not None:
        report_query = report_query.filter(DailyReport.project_id.in_(accessible_project_ids or [-1]))
    reports = report_query.options(
        joinedload(DailyReport.workflow),
        joinedload(DailyReport.reporter),
    ).order_by(DailyReport.report_date.desc()).limit(20).all()

    ncr_query = db.query(NonConformance).filter(NonConformance.status.in_(OPEN_NCR_STATUSES))
    if user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        ncr_query = ncr_query.filter(NonConformance.assigned_to == user.id)
    elif accessible_project_ids is not None:
        ncr_query = ncr_query.filter(NonConformance.project_id.in_(accessible_project_ids or [-1]))
    ncrs = ncr_query.order_by(NonConformance.due_date).limit(20).all()

    return {
        "role": user.role.value,
        "tasks": [{
            "id": task.id, "title": task.title, "project_id": task.project_id,
            "status": task.status.value, "deadline": task.deadline,
            "priority": task.priority.value, "progress_percent": task.progress_percent,
            "gate": gates_by_task[task.id],
        } for task in tasks],
        "reports": [{
            "id": report.id, "task_id": report.workflow.task_id,
            "status": report.workflow.status.value, "report_date": report.report_date,
            "reporter": report.reporter.name,
        } for report in reports],
        "ncrs": [serialize_ncr(item) for item in ncrs],
    }


def serialize_inspection(item: InspectionRequest) -> dict:
    return {
        "id": item.id, "project_id": item.project_id, "task_id": item.task_id,
        "inspection_type": item.inspection_type, "title": item.title, "status": item.status,
        "is_required": item.is_required, "due_date": item.due_date,
        "requested_by": item.requested_by, "inspected_by": item.inspected_by,
        "inspected_at": item.inspected_at, "result_note": item.result_note,
        "document_id": item.document_id, "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_ncr(item: NonConformance) -> dict:
    return {
        "id": item.id, "project_id": item.project_id, "task_id": item.task_id,
        "inspection_id": item.inspection_id, "ncr_number": item.ncr_number,
        "title": item.title, "description": item.description, "severity": item.severity,
        "status": item.status, "assigned_to": item.assigned_to, "due_date": item.due_date,
        "corrective_action": item.corrective_action, "closed_by": item.closed_by,
        "closed_at": item.closed_at, "created_at": item.created_at, "updated_at": item.updated_at,
    }


def serialize_handover(item: HandoverItem) -> dict:
    return {
        "id": item.id, "project_id": item.project_id, "task_id": item.task_id,
        "category": item.category, "title": item.title, "status": item.status,
        "document_id": item.document_id, "source_type": item.source_type,
        "source_id": item.source_id, "auto_collected": item.auto_collected,
        "created_at": item.created_at,
    }
