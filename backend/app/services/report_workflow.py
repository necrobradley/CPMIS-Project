import json
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import (
    ApprovalStatus, DailyReport, DailyReportWorkflow, EvidenceType, Project, ReportRequirementCheck,
    ReportStatus, Task, TaskRequirement, User, UserRole,
)
from app.services.project_role_catalog import (
    can_role_access_task_division,
)


REVIEW_ROLES = {UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER}


def can_access_task(user: User, task: Task) -> bool:
    if user.role in {UserRole.ADMIN, UserRole.DIRECTOR}:
        return True
    if (
        user.role in {UserRole.STAFF, UserRole.SUBCONTRACTOR}
        and (getattr(task, "approval_status", None) or ApprovalStatus.APPROVED.value) != ApprovalStatus.APPROVED.value
    ):
        return False
    if task.project.owner_id == user.id:
        return True
    if task.assigned_to == user.id or task.created_by == user.id:
        return True
    membership = next((
        item for item in task.project.memberships
        if item.user_id == user.id and item.is_active
    ), None)
    if membership:
        return can_role_access_task_division(
            membership.project_role,
            membership.division_id,
            task.division_id,
        )
    if task.division and task.division.manager_id == user.id:
        return True
    return False


def can_access_project(user: User, project: Project) -> bool:
    if user.role in {UserRole.ADMIN, UserRole.DIRECTOR}:
        return True
    if project.owner_id == user.id:
        return True
    if any(item.user_id == user.id and item.is_active for item in project.memberships):
        return True
    if any(division.manager_id == user.id for division in project.divisions):
        return True
    if any(task.assigned_to == user.id or task.created_by == user.id for task in project.tasks):
        return True
    if any(report.user_id == user.id for report in project.daily_reports):
        return True
    return False


def ensure_project_access(user: User, project: Project) -> None:
    if not can_access_project(user, project):
        raise HTTPException(status_code=403, detail="Proyek tidak tersedia untuk akun ini")


def ensure_task_access(user: User, task: Task) -> None:
    if not can_access_task(user, task):
        raise HTTPException(status_code=403, detail="Task tidak tersedia untuk akun ini")


def set_requirement_confirmations(
    db: Session,
    report: DailyReport,
    task: Task,
    confirmations: Iterable,
) -> None:
    valid_requirement_ids = {item.id for item in task.requirements}
    for item in confirmations:
        if item.requirement_id not in valid_requirement_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Requirement #{item.requirement_id} tidak berasal dari task laporan",
            )
        check = db.query(ReportRequirementCheck).filter(
            ReportRequirementCheck.report_id == report.id,
            ReportRequirementCheck.requirement_id == item.requirement_id,
        ).first()
        if not check:
            check = ReportRequirementCheck(
                report_id=report.id,
                requirement_id=item.requirement_id,
            )
            db.add(check)
        check.confirmed = item.confirmed
        check.note = item.note


def validate_report(report: DailyReport) -> dict:
    task = report.workflow.task
    specification = task.specification
    evidence = list(report.evidence)
    photo_count = sum(1 for item in evidence if item.evidence_type == EvidenceType.PHOTO)
    document_count = sum(1 for item in evidence if item.evidence_type == EvidenceType.DOCUMENT)
    checks_by_requirement = {
        item.requirement_id: item for item in report.requirement_checks
    }

    items = []

    def add(code: str, label: str, passed: bool, message: str) -> None:
        items.append({
            "code": code,
            "label": label,
            "passed": passed,
            "message": message,
        })

    report_text_ok = len((report.report_text or "").strip()) >= 20
    add(
        "REPORT_TEXT",
        "Uraian kegiatan",
        report_text_ok,
        "Uraian minimal 20 karakter" if not report_text_ok else "Uraian kegiatan tersedia",
    )
    progress_ok = bool((report.work_progress or "").strip())
    add(
        "WORK_PROGRESS",
        "Progress pekerjaan",
        progress_ok,
        "Progress pekerjaan wajib dijelaskan" if not progress_ok else "Progress pekerjaan tersedia",
    )
    manpower_ok = report.manpower_count is not None and report.manpower_count >= 0
    add(
        "MANPOWER",
        "Jumlah tenaga kerja",
        manpower_ok,
        "Jumlah tenaga kerja wajib diisi" if not manpower_ok else "Jumlah tenaga kerja tersedia",
    )

    control = getattr(task, "control", None)
    if control and control.planned_quantity and control.planned_quantity > 0:
        progress_entry = getattr(report, "progress_entry", None)
        reported_quantity = progress_entry.quantity_this_report if progress_entry else 0
        quantity_ok = reported_quantity > 0
        add(
            "ACTUAL_QUANTITY",
            f"Volume aktual ({control.unit or 'unit'})",
            quantity_ok,
            "Volume aktual wajib diisi untuk task berbasis BOQ"
            if not quantity_ok else f"Volume laporan: {reported_quantity:g}",
        )
        if quantity_ok:
            total_after_report = (control.actual_quantity or 0) + reported_quantity
            quantity_limit = control.planned_quantity * 1.05
            add(
                "ACTUAL_QUANTITY_REASONABLE",
                "Kewajaran volume aktual",
                total_after_report <= quantity_limit,
                (
                    f"Total setelah laporan {total_after_report:g} melebihi batas toleransi "
                    f"{quantity_limit:g} {control.unit or 'unit'}"
                ) if total_after_report > quantity_limit else (
                    f"Total setelah laporan {total_after_report:g}/{control.planned_quantity:g} "
                    f"{control.unit or 'unit'} masih dalam toleransi"
                ),
            )

    required_photos = specification.required_photo_count if specification else 0
    required_documents = specification.required_document_count if specification else 0
    add(
        "PHOTO_COUNT",
        "Foto lapangan",
        photo_count >= required_photos,
        f"{photo_count}/{required_photos} foto tersedia",
    )
    add(
        "DOCUMENT_COUNT",
        "Dokumen pendukung",
        document_count >= required_documents,
        f"{document_count}/{required_documents} dokumen tersedia",
    )

    for requirement in task.requirements:
        if not requirement.is_mandatory:
            continue
        check = checks_by_requirement.get(requirement.id)
        passed = bool(check and check.confirmed)
        add(
            requirement.code,
            requirement.title,
            passed,
            "Dikonfirmasi oleh pelapor" if passed else "Checklist wajib belum dikonfirmasi",
        )

    passed_count = sum(1 for item in items if item["passed"])
    total = len(items)
    score = round((passed_count / total) * 100, 2) if total else 100.0
    return {
        "passed": passed_count == total,
        "score": score,
        "summary": f"{passed_count} dari {total} pemeriksaan terpenuhi",
        "checked_at": datetime.utcnow().isoformat(),
        "items": items,
        "evidence": {
            "photos": photo_count,
            "documents": document_count,
            "required_photos": required_photos,
            "required_documents": required_documents,
        },
    }


def apply_validation(workflow: DailyReportWorkflow, result: dict) -> None:
    workflow.validation_passed = result["passed"]
    workflow.validation_score = result["score"]
    workflow.validation_result = json.dumps(result, ensure_ascii=False)
    workflow.status = (
        ReportStatus.READY_FOR_REVIEW if result["passed"] else ReportStatus.NEEDS_REVISION
    )
    workflow.submitted_at = datetime.utcnow()
