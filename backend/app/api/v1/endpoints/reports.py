import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query,
    Response, UploadFile,
)
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import (
    CommunicationType,
    DailyReport, DailyReportWorkflow, EvidenceType, Notification, Project,
    ReportEvidence, ReportProgressEntry, ReportReview, ReportStatus, Task, TaskPriority, User, UserRole,
)
from app.schemas.schemas import (
    DailyReportCreate, DailyReportResponse, DailyReportUpdate, ReportDecision,
    ReportEvidenceResponse, TelegramAutoGroupPreviewRequest,
    TelegramAutoGroupPreviewResponse,
)
from app.services.audit_service import log_audit
from app.services.n8n_service import n8n_service
from app.services.report_workflow import (
    REVIEW_ROLES, apply_validation, can_access_task, ensure_task_access, set_requirement_confirmations,
    validate_report,
)
from app.services.storage_service import storage_service
from app.services.project_controls import apply_approved_report
from app.services.communication_service import ensure_communication_from_source
from app.services.telegram_auto_grouping import MIN_AUTO_GROUP_CONFIDENCE, auto_group_message
from app.services.task_approval import task_is_approved

router = APIRouter(prefix="/reports", tags=["Daily Reports"])

ALLOWED_EVIDENCE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_EVIDENCE_SIZE = 25 * 1024 * 1024


def _auto_group_candidate(match):
    task = match.task
    specification = task.specification
    return {
        "task_id": task.id,
        "title": task.title,
        "wbs_code": specification.wbs_code if specification else None,
        "project_id": task.project_id,
        "project_name": task.project.project_name if task.project else "",
        "confidence": match.confidence,
        "reasons": match.reasons,
    }


def _get_report(db: Session, report_id: int) -> DailyReport:
    report = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")
    if not report.workflow:
        raise HTTPException(status_code=409, detail="Laporan lama belum memiliki workflow terstruktur")
    return report


def _ensure_report_access(user: User, report: DailyReport) -> None:
    if user.role in REVIEW_ROLES and can_access_task(user, report.workflow.task):
        return
    if report.user_id != user.id:
        raise HTTPException(status_code=403, detail="Laporan tidak tersedia untuk akun ini")


def _get_manager_telegram_ids(db: Session) -> list:
    managers = db.query(User).filter(
        User.role.in_([UserRole.MANAGER, UserRole.DIRECTOR, UserRole.ADMIN]),
        User.is_active == True,
        User.telegram_id != None,
    ).all()
    return [item.telegram_id for item in managers if item.telegram_id]


def _notify_reviewers(db: Session, report: DailyReport) -> None:
    reviewers = db.query(User).filter(
        User.role.in_([UserRole.MANAGER, UserRole.DIRECTOR]),
        User.is_active == True,
    ).all()
    for reviewer in reviewers:
        db.add(Notification(
            user_id=reviewer.id,
            title="Laporan siap ditinjau",
            message=f"Laporan #{report.id} untuk task {report.workflow.task.title} menunggu review.",
            type="review",
            related_task_id=report.workflow.task_id,
            related_project_id=report.project_id,
        ))


@router.post(
    "/telegram/auto-group/preview",
    response_model=TelegramAutoGroupPreviewResponse,
)
def preview_telegram_auto_grouping(
    payload: TelegramAutoGroupPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview pengelompokan otomatis pesan Telegram tanpa membuat draft laporan."""
    result = auto_group_message(db, current_user, payload.message)
    task = result.task
    specification = task.specification if task else None
    return {
        "matched": result.is_confident,
        "confidence": result.confidence,
        "threshold": MIN_AUTO_GROUP_CONFIDENCE,
        "task_id": task.id if task else None,
        "title": task.title if task else None,
        "wbs_code": specification.wbs_code if specification else None,
        "project_id": task.project_id if task else None,
        "project_name": task.project.project_name if task and task.project else None,
        "reasons": result.reasons,
        "candidates": [_auto_group_candidate(match) for match in result.candidates],
        "parsed_fields": {
            "report_text": result.fields.report_text,
            "weather": result.fields.weather,
            "manpower_count": result.fields.manpower_count,
            "work_progress": result.fields.work_progress,
            "issues": result.fields.issues,
            "actual_quantity": result.fields.actual_quantity,
            "actual_unit": result.fields.actual_unit,
        },
    }


@router.get("", response_model=List[DailyReportResponse])
def list_reports(
    project_id: Optional[int] = Query(None),
    task_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    status: Optional[ReportStatus] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DailyReport).join(DailyReportWorkflow)
    if project_id:
        query = query.filter(DailyReport.project_id == project_id)
    if task_id:
        query = query.filter(DailyReportWorkflow.task_id == task_id)
    if user_id:
        query = query.filter(DailyReport.user_id == user_id)
    if status:
        query = query.filter(DailyReportWorkflow.status == status)
    if date_from:
        query = query.filter(DailyReport.report_date >= date_from)
    if date_to:
        query = query.filter(DailyReport.report_date <= date_to)
    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        query = query.filter(DailyReport.user_id == current_user.id)
    reports = query.order_by(DailyReport.report_date.desc()).all()
    if current_user.role in (UserRole.ADMIN, UserRole.DIRECTOR):
        return reports
    if current_user.role == UserRole.MANAGER:
        return [item for item in reports if can_access_task(current_user, item.workflow.task)]
    return reports


@router.post("", response_model=DailyReportResponse, status_code=201)
def create_report(
    data: DailyReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == data.project_id).first()
    task = db.query(Task).filter(Task.id == data.task_id).first()
    if not project or not task or task.project_id != project.id:
        raise HTTPException(status_code=400, detail="Proyek dan task laporan tidak sesuai")
    ensure_task_access(current_user, task)
    if not task_is_approved(task):
        raise HTTPException(status_code=409, detail="Task belum approved oleh Project Manager")
    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR) and task.assigned_to != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Staff hanya dapat membuat laporan untuk task yang ditugaskan langsung kepadanya",
        )

    values = data.model_dump(exclude={
        "task_id", "requirement_confirmations", "actual_quantity", "actual_cost",
    })
    report = DailyReport(**values, user_id=current_user.id, report_date=datetime.utcnow())
    db.add(report)
    db.flush()
    report.workflow = DailyReportWorkflow(task_id=task.id, status=ReportStatus.DRAFT)
    report.progress_entry = ReportProgressEntry(
        task_id=task.id,
        quantity_this_report=data.actual_quantity,
        cost_this_report=data.actual_cost,
    )
    set_requirement_confirmations(
        db, report, task, data.requirement_confirmations,
    )
    log_audit(
        db,
        actor_id=current_user.id,
        action="report.draft_created",
        entity_type="daily_report",
        entity_id=report.id,
        project_id=project.id,
        summary=f"Draft laporan dibuat untuk task: {task.title}",
        after={"task_id": task.id, "status": ReportStatus.DRAFT.value},
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}", response_model=DailyReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report(db, report_id)
    _ensure_report_access(current_user, report)
    return report


@router.patch("/{report_id}", response_model=DailyReportResponse)
def update_report(
    report_id: int,
    data: DailyReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report(db, report_id)
    _ensure_report_access(current_user, report)
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Hanya pelapor yang dapat mengubah laporan")
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(status_code=409, detail="Laporan yang sedang direview tidak dapat diubah")

    values = data.model_dump(exclude_unset=True, exclude={
        "requirement_confirmations", "actual_quantity", "actual_cost",
    })
    for field, value in values.items():
        setattr(report, field, value)
    if data.actual_quantity is not None or data.actual_cost is not None:
        if not report.progress_entry:
            report.progress_entry = ReportProgressEntry(
                task_id=report.workflow.task_id,
                quantity_this_report=data.actual_quantity or 0,
                cost_this_report=data.actual_cost or 0,
            )
        else:
            if data.actual_quantity is not None:
                report.progress_entry.quantity_this_report = data.actual_quantity
            if data.actual_cost is not None:
                report.progress_entry.cost_this_report = data.actual_cost
    if data.requirement_confirmations is not None:
        set_requirement_confirmations(
            db, report, report.workflow.task, data.requirement_confirmations,
        )
    report.workflow.status = ReportStatus.DRAFT
    report.workflow.revision_note = None
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/evidence", response_model=ReportEvidenceResponse, status_code=201)
async def upload_evidence(
    report_id: int,
    evidence_type: EvidenceType = Form(...),
    caption: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report(db, report_id)
    _ensure_report_access(current_user, report)
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Hanya pelapor yang dapat menambah evidence")
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(status_code=409, detail="Evidence dikunci saat laporan direview")
    if file.content_type not in ALLOWED_EVIDENCE_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Format evidence tidak didukung")
    if evidence_type == EvidenceType.PHOTO and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Evidence foto harus berupa gambar")

    content = await file.read()
    if len(content) > MAX_EVIDENCE_SIZE:
        raise HTTPException(status_code=413, detail="Ukuran evidence maksimal 25 MB")
    extension = Path(file.filename or "evidence").suffix.lower() or ".bin"
    folder = "photos" if evidence_type == EvidenceType.PHOTO else "documents"
    object_name = (
        f"projects/{report.project_id}/tasks/{report.workflow.task_id}/"
        f"reports/{report.id}/{folder}/{uuid.uuid4()}{extension}"
    )
    storage_service.upload_file(content, object_name, file.content_type)
    evidence = ReportEvidence(
        report_id=report.id,
        uploaded_by=current_user.id,
        evidence_type=evidence_type,
        file_name=file.filename or f"evidence{extension}",
        file_path=object_name,
        file_size=len(content),
        mime_type=file.content_type,
        caption=caption,
    )
    db.add(evidence)
    db.flush()
    log_audit(
        db,
        actor_id=current_user.id,
        action="report.evidence_uploaded",
        entity_type="report_evidence",
        entity_id=evidence.id,
        project_id=report.project_id,
        summary=f"Evidence {evidence_type.value} ditambahkan ke laporan #{report.id}",
        after={"task_id": report.workflow.task_id, "file_name": evidence.file_name},
    )
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/evidence/{evidence_id}/download-url")
def get_evidence_download_url(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = db.query(ReportEvidence).filter(ReportEvidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence tidak ditemukan")
    _ensure_report_access(current_user, evidence.report)
    return {"url": storage_service.get_signed_url(evidence.file_path)}


@router.get("/evidence/{evidence_id}/download")
def download_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = db.query(ReportEvidence).filter(ReportEvidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence tidak ditemukan")
    _ensure_report_access(current_user, evidence.report)
    try:
        content = storage_service.get_file_bytes(evidence.file_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Evidence tidak dapat dibaca: {str(exc)}") from exc
    safe_name = evidence.file_name.replace('"', "")
    return Response(
        content=content,
        media_type=evidence.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = db.query(ReportEvidence).filter(ReportEvidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence tidak ditemukan")
    report = evidence.report
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Hanya pelapor yang dapat menghapus evidence")
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(status_code=409, detail="Evidence dikunci saat laporan direview")
    storage_service.delete_file(evidence.file_path)
    db.delete(evidence)
    db.commit()


@router.post("/{report_id}/submit", response_model=DailyReportResponse)
async def submit_report(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report(db, report_id)
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Hanya pelapor yang dapat submit laporan")
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(status_code=409, detail="Status laporan tidak dapat disubmit")

    before_status = report.workflow.status.value
    result = validate_report(report)
    apply_validation(report.workflow, result)
    task = report.workflow.task
    if (report.issues or "").strip():
        assignee_id = task.created_by if task.created_by != current_user.id else report.project.owner_id
        ensure_communication_from_source(
            db,
            source_type="daily_report_issue",
            source_id=report.id,
            project_id=report.project_id,
            created_by=current_user.id,
            subject=f"Issue laporan #{report.id}: {task.title}",
            description=report.issues,
            communication_type=CommunicationType.ISSUE,
            priority=TaskPriority.HIGH,
            assigned_to=assignee_id,
            related_task_id=task.id,
            location=task.specification.location if task.specification else None,
            system_message=f"Issue dari laporan harian #{report.id}: {report.issues}",
        )
    if not result["passed"]:
        ensure_communication_from_source(
            db,
            source_type="daily_report_validation_blocker",
            source_id=report.id,
            project_id=report.project_id,
            created_by=current_user.id,
            subject=f"Validasi laporan belum lengkap #{report.id}",
            description=result["summary"],
            communication_type=CommunicationType.ISSUE,
            priority=TaskPriority.MEDIUM,
            assigned_to=current_user.id,
            related_task_id=task.id,
            location=task.specification.location if task.specification else None,
            system_message=f"Sistem menemukan blocker validasi laporan: {result['summary']}",
        )
    if result["passed"]:
        _notify_reviewers(db, report)
    db.add(ReportReview(
        report_id=report.id,
        reviewer_id=current_user.id,
        from_status=before_status,
        to_status=report.workflow.status.value,
        note=result["summary"],
    ))
    log_audit(
        db,
        actor_id=current_user.id,
        action="report.submitted",
        entity_type="daily_report",
        entity_id=report.id,
        project_id=report.project_id,
        summary=f"Laporan divalidasi: {result['summary']}",
        before={"status": before_status},
        after={"status": report.workflow.status.value, "score": result["score"]},
    )
    db.commit()
    db.refresh(report)

    if result["passed"]:
        background_tasks.add_task(
            n8n_service.trigger_daily_report,
            report_id=report.id,
            project_id=report.project_id,
            project_name=report.project.project_name,
            reporter_name=current_user.name,
            reporter_telegram_id=current_user.telegram_id,
            manager_telegram_ids=_get_manager_telegram_ids(db),
            report_text=report.report_text,
            ai_summary=report.ai_summary,
            ai_risks=report.ai_risks,
            severity="low",
        )
    return report


@router.patch("/{report_id}/decision", response_model=DailyReportResponse)
def decide_report(
    report_id: int,
    data: ReportDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    report = _get_report(db, report_id)
    _ensure_report_access(current_user, report)
    workflow = report.workflow
    before_status = workflow.status
    target = ReportStatus(data.decision)

    allowed = {
        ReportStatus.READY_FOR_REVIEW: {ReportStatus.NEEDS_REVISION, ReportStatus.VERIFIED},
        ReportStatus.VERIFIED: {ReportStatus.NEEDS_REVISION, ReportStatus.APPROVED},
    }
    if target not in allowed.get(before_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Transisi {before_status.value} ke {target.value} tidak diizinkan",
        )
    if target == ReportStatus.NEEDS_REVISION and not (data.note or "").strip():
        raise HTTPException(status_code=400, detail="Catatan revisi wajib diisi")

    workflow.status = target
    workflow.revision_note = data.note if target == ReportStatus.NEEDS_REVISION else None
    now = datetime.utcnow()
    if target == ReportStatus.VERIFIED:
        workflow.verified_by = current_user.id
        workflow.verified_at = now
    elif target == ReportStatus.APPROVED:
        workflow.approved_by = current_user.id
        workflow.approved_at = now
        apply_approved_report(db, report, current_user.id)

    db.add(ReportReview(
        report_id=report.id,
        reviewer_id=current_user.id,
        from_status=before_status.value,
        to_status=target.value,
        note=data.note,
    ))
    db.add(Notification(
        user_id=report.user_id,
        title=f"Laporan {target.value.replace('_', ' ')}",
        message=data.note or f"Laporan #{report.id} berubah menjadi {target.value}.",
        type="report_status",
        related_task_id=workflow.task_id,
        related_project_id=report.project_id,
    ))
    log_audit(
        db,
        actor_id=current_user.id,
        action="report.reviewed",
        entity_type="daily_report",
        entity_id=report.id,
        project_id=report.project_id,
        summary=f"Status laporan #{report.id}: {target.value}",
        before={"status": before_status.value},
        after={"status": target.value, "note": data.note},
    )
    db.commit()
    db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _get_report(db, report_id)
    if report.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        raise HTTPException(status_code=409, detail="Laporan yang sedang direview tidak dapat dihapus")
    for evidence in report.evidence:
        storage_service.delete_file(evidence.file_path)
    db.delete(report)
    db.commit()
