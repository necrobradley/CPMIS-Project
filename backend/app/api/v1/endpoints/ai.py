from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from app.db.database import get_db
from app.models.user import (
    User, Project, Task, Document, DailyReport, Division, UserRole, DocumentType,
    TaskMaterialSpecification, TaskRequirement, TaskSpecification,
)
from app.schemas.schemas import TaskResponse
from app.core.security import get_current_user
from app.services.ai_service import AIService
from app.services.ai_provider_routing import available_models
from app.services.n8n_service import n8n_service
from app.services.report_workflow import ensure_project_access
from app.services.task_approval import request_task_approval
from app.services.project_staffing import (
    active_pic_roles,
    resolve_task_project_role,
    select_task_pic,
)

router = APIRouter(prefix="/ai", tags=["AI Features"])
ai_service = AIService()
AI_MANAGEMENT_ROLES = {UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER}


def _ensure_ai_management(user: User) -> None:
    if user.role not in AI_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="AI automation hanya tersedia untuk management")


def _get_manager_telegram_ids(db: Session) -> list:
    managers = db.query(User).filter(
        User.role.in_(["manager", "director"]),
        User.is_active == True,
        User.telegram_id != None,
    ).all()
    return [m.telegram_id for m in managers if m.telegram_id]


@router.post("/analyze-document", summary="Analisis dokumen tender/kontrak dengan AI")
async def analyze_document(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    doc_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload dokumen (PDF/DOCX) → AI ekstrak info penting.
    Selesai → trigger N8N Workflow 2 (Tender Analysis Flow).
    """
    _ensure_ai_management(current_user)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    content = await file.read()

    doc = Document(
        project_id=project_id,
        uploaded_by=current_user.id,
        file_name=file.filename,
        file_path=f"temp/{file.filename}",
        file_type=doc_type,
        file_size=len(content),
        mime_type=file.content_type,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        analysis = await ai_service.analyze_document(
            content=content,
            filename=file.filename,
            doc_type=doc_type.value
        )
        doc.ai_analysis = json.dumps(analysis, ensure_ascii=False)
        db.commit()

        # Ambil nama proyek
        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.project_name if project else f"Proyek #{project_id}"
        manager_tg_ids = _get_manager_telegram_ids(db)

        # Trigger N8N Workflow 2 di background
        background_tasks.add_task(
            n8n_service.trigger_tender_analysis,
            document_id=doc.id,
            project_id=project_id,
            project_name=project_name,
            file_name=file.filename,
            uploader_name=current_user.name,
            analysis_result=analysis,
            generated_tasks_count=0,  # diupdate setelah generate-tasks
            manager_telegram_ids=manager_tg_ids,
        )

        return {"document_id": doc.id, "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis gagal: {str(e)}")


@router.post("/generate-tasks/{project_id}", response_model=List[TaskResponse])
async def generate_tasks_from_document(
    project_id: int,
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dari hasil analisis dokumen → AI buat task breakdown otomatis.
    Selesai → update N8N dengan jumlah task yang digenerate.
    """
    _ensure_ai_management(current_user)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.project_id == project_id
    ).first()

    if not doc or not doc.ai_analysis:
        raise HTTPException(status_code=404, detail="Dokumen atau analisis AI tidak ditemukan")

    analysis = json.loads(doc.ai_analysis)

    available_roles = active_pic_roles(db, project_id)
    allowed_role_codes = {role["code"] for role in available_roles}
    try:
        task_list = await ai_service.generate_tasks(
            analysis=analysis,
            project_id=project_id,
            available_roles=available_roles,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generate task gagal: {str(e)}")

    created_tasks = []
    tasks_by_wbs = {}
    project_divisions = db.query(Division).filter(Division.project_id == project_id).all()
    for t in task_list:
        division_name = (t.get("division") or "").lower()
        matched_division = next(
            (item for item in project_divisions if division_name and division_name in item.division_name.lower()),
            None,
        )
        project_role = resolve_task_project_role(t, allowed_role_codes)
        assignment = select_task_pic(
            db,
            project_id=project_id,
            requested_project_role=project_role,
        )
        assigned_division_id = assignment.division_id if assignment else (matched_division.id if matched_division else None)
        task = Task(
            title=t["title"],
            description=t.get("description"),
            project_id=project_id,
            division_id=assigned_division_id,
            assigned_to=assignment.user_id if assignment else None,
            priority=t.get("priority", "medium"),
            deadline=None,
            created_by=current_user.id,
            ai_generated=True,
            ai_source=doc.file_name,
        )
        db.add(task)
        db.flush()
        wbs_code = t.get("wbs_code") or f"AI-{task.id}"
        task.specification = TaskSpecification(
            wbs_code=wbs_code,
            work_package=t.get("division"),
            acceptance_criteria=t.get("acceptance_criteria") or "Wajib diverifikasi manager berdasarkan dokumen sumber.",
            reporting_instructions=t.get("reporting_instructions"),
            required_photo_count=max(0, int(t.get("required_photo_count") or 0)),
            required_document_count=max(0, int(t.get("required_document_count") or 0)),
            template_name="Laporan Harian Lapangan",
            template_version="1.0",
            source_document_id=doc.id,
        )
        requirements = t.get("requirements") or []
        if not requirements:
            requirements = [
                {"code": "SCOPE", "title": "Lingkup pekerjaan telah diperiksa", "description": "Konfirmasi terhadap scope tender."},
                {"code": "QUALITY", "title": "Kriteria mutu telah diperiksa", "description": "Konfirmasi terhadap acceptance criteria."},
            ]
        for index, requirement in enumerate(requirements, start=1):
            task.requirements.append(TaskRequirement(
                code=f"{wbs_code}-{requirement.get('code', index)}",
                title=requirement.get("title") or f"Requirement {index}",
                description=requirement.get("description"),
                requirement_type="checklist",
                validation_rule="manual_confirmation",
                is_mandatory=True,
                sequence=index,
            ))
        for index, material in enumerate(t.get("materials") or [], start=1):
            material_name = material.get("material_name") or material.get("name")
            if not material_name:
                continue
            task.materials.append(TaskMaterialSpecification(
                material_code=material.get("material_code") or material.get("code"),
                material_name=material_name,
                category=material.get("category"),
                technical_specification=material.get("technical_specification") or material.get("specification"),
                standard_reference=material.get("standard_reference") or material.get("standard"),
                grade=material.get("grade"),
                approved_manufacturer=material.get("approved_manufacturer") or material.get("manufacturer"),
                dimensions=material.get("dimensions"),
                unit=material.get("unit"),
                planned_quantity=material.get("planned_quantity") or material.get("quantity"),
                certificate_required=bool(material.get("certificate_required", False)),
                test_required=bool(material.get("test_required", False)),
                approval_required=bool(material.get("approval_required", True)),
                source_document_id=doc.id,
                source_page=material.get("source_page") or material.get("page"),
                revision=material.get("revision"),
                sequence=index,
            ))
        created_tasks.append(task)
        tasks_by_wbs[wbs_code] = task
        request_task_approval(
            db,
            task,
            current_user,
            description=(
                "Draft task dari analisis dokumen. Project Manager perlu memeriksa scope, "
                "PIC, divisi, baseline, dan milestone tender sebelum task aktif."
            ),
        )

    for source, task in zip(task_list, created_tasks):
        parent = tasks_by_wbs.get(source.get("parent_wbs"))
        if parent and parent.id != task.id:
            task.parent_task_id = parent.id

    db.commit()
    for t in created_tasks:
        db.refresh(t)

    # Ambil info proyek & manager
    project_name = project.project_name if project else f"Proyek #{project_id}"
    analysis_result = json.loads(doc.ai_analysis) if doc.ai_analysis else {}
    manager_tg_ids = _get_manager_telegram_ids(db)

    # Trigger N8N Workflow 2 dengan jumlah task yang benar
    background_tasks.add_task(
        n8n_service.trigger_tender_analysis,
        document_id=doc.id,
        project_id=project_id,
        project_name=project_name,
        file_name=doc.file_name,
        uploader_name=current_user.name,
        analysis_result=analysis_result,
        generated_tasks_count=len(created_tasks),
        manager_telegram_ids=manager_tg_ids,
    )

    return created_tasks


@router.post("/summarize-report/{report_id}", summary="Ringkas laporan harian dengan AI")
async def summarize_report(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI meringkas laporan harian dan mendeteksi risiko."""
    _ensure_ai_management(current_user)
    report = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")
    ensure_project_access(current_user, report.project)

    try:
        result = await ai_service.summarize_report(
            report_text=report.report_text,
            issues=report.issues or "",
            work_progress=report.work_progress or ""
        )
        report.ai_summary = result.get("summary")
        report.ai_risks   = result.get("risks")
        db.commit()

        severity = result.get("severity", "low")

        # Jika severity tinggi → trigger N8N untuk kirim notif segera
        if severity in ("high", "critical"):
            project = db.query(Project).filter(Project.id == report.project_id).first()
            project_name = project.project_name if project else f"Proyek #{report.project_id}"
            reporter = db.query(User).filter(User.id == report.user_id).first()
            manager_tg_ids = _get_manager_telegram_ids(db)

            background_tasks.add_task(
                n8n_service.trigger_daily_report,
                report_id=report.id,
                project_id=report.project_id,
                project_name=project_name,
                reporter_name=reporter.name if reporter else "Unknown",
                reporter_telegram_id=reporter.telegram_id if reporter else None,
                manager_telegram_ids=manager_tg_ids,
                report_text=report.report_text,
                ai_summary=result.get("summary"),
                ai_risks=result.get("risks"),
                severity=severity,
            )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarize gagal: {str(e)}")


@router.get("/models", summary="Daftar model AI yang tersedia")
def list_ai_models(
    current_user: User = Depends(get_current_user),
):
    _ensure_ai_management(current_user)
    return {"models": available_models()}


@router.post("/chat", summary="Chat dengan AI tentang proyek")
async def chat_with_ai(
    message: str,
    project_id: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chat bebas dengan AI tentang proyek konstruksi."""
    _ensure_ai_management(current_user)
    context = ""
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
        ensure_project_access(current_user, project)
        context = f"Proyek: {project.project_name}, Status: {project.status}, Progress: {project.progress_percent}%"

    try:
        response = await ai_service.chat(
            message=message,
            context=context,
            provider=provider,
            model=model,
        )
        return {
            "response": response,
            "provider": provider,
            "model": model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat gagal: {str(e)}")
