"""
Documents Endpoint - AI CPMIS
Upload file ke private object storage, AI analysis, dan versioning.
"""
import uuid
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models.user import (
    ApprovalRequest, ApprovalStatus, ApprovalType, Document, DocumentSyncSession,
    DocumentSyncStatus, DocumentType, Notification, Project, User, UserRole,
)
from app.core.security import get_current_user, require_roles
from app.schemas.schemas import (
    DocumentAnswer, DocumentQuestion, DocumentSyncPreviewRequest,
    DocumentSyncResponse, DocumentSyncSelection,
)
from app.services.storage_service import storage_service
from app.services.ai_service import AIService
from app.services import document_rag
from app.services.n8n_service import n8n_service
from app.services.audit_service import log_audit
from app.services.document_sync import apply_sync_plan, build_sync_plan
from app.services.report_workflow import ensure_project_access
from app.services.safety_guard import check_ai_output, check_user_question, refusal_message

router = APIRouter(prefix="/documents", tags=["Documents"])
ai_service = AIService()
CONTROL_ROLES = (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)
SENSITIVE_DOCUMENT_TYPES = (DocumentType.TENDER, DocumentType.CONTRACT)


def _project_for_user(db: Session, project_id: int, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(user, project)
    return project


def _ensure_document_access(db: Session, document: Document, user: User) -> None:
    _project_for_user(db, document.project_id, user)
    if user.role not in CONTROL_ROLES and document.file_type in SENSITIVE_DOCUMENT_TYPES:
        raise HTTPException(status_code=403, detail="Dokumen tender/kontrak hanya tersedia untuk management")


def _sync_response(session: DocumentSyncSession):
    return {
        "id": session.id,
        "document_id": session.document_id,
        "project_id": session.project_id,
        "created_by": session.created_by,
        "approval_id": session.approval_id,
        "status": session.status,
        "plan": json.loads(session.plan_json),
        "selected_change_ids": json.loads(session.selected_change_ids or "[]"),
        "generated_with_ai": session.generated_with_ai,
        "reviewed_by": session.reviewed_by,
        "applied_by": session.applied_by,
        "requested_at": session.requested_at,
        "reviewed_at": session.reviewed_at,
        "applied_at": session.applied_at,
        "error_message": session.error_message,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }

ALLOWED_TYPES = {
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg", "image/png", "image/webp",
}


@router.post("/upload", summary="Upload file ke MinIO + analisis AI opsional")
async def upload_document(
    project_id: int = Form(...),
    doc_type: DocumentType = Form(...),
    analyze_with_ai: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload file ke private object storage. Bila diminta, analisis AI diselesaikan
    dalam request yang sama agar hasilnya pasti tersimpan pada runtime serverless.
    """
    _project_for_user(db, project_id, current_user)
    if current_user.role not in CONTROL_ROLES and doc_type in SENSITIVE_DOCUMENT_TYPES:
        raise HTTPException(status_code=403, detail="Staff tidak dapat mengunggah dokumen tender/kontrak")
    if current_user.role not in CONTROL_ROLES and analyze_with_ai:
        raise HTTPException(status_code=403, detail="Analisis dokumen hanya tersedia untuk management")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipe file tidak didukung: {file.content_type}")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File terlalu besar (maks 50MB)")

    # Buat object name unik dengan folder per proyek
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    object_name = f"projects/{project_id}/{doc_type.value}/{uuid.uuid4()}.{ext}"

    try:
        storage_service.upload_file(content, object_name, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload gagal: {str(e)}")

    # Cek versi dokumen yang sama
    latest = db.query(Document).filter(
        Document.project_id == project_id,
        Document.file_name == file.filename,
    ).order_by(Document.version.desc()).first()
    version = (latest.version + 1) if latest else 1

    doc = Document(
        project_id=project_id,
        uploaded_by=current_user.id,
        file_name=file.filename,
        file_path=object_name,
        file_type=doc_type,
        file_size=len(content),
        mime_type=file.content_type,
        version=version,
    )
    db.add(doc)
    db.flush()
    log_audit(
        db,
        actor_id=current_user.id,
        action="document.uploaded",
        entity_type="document",
        entity_id=doc.id,
        project_id=project_id,
        summary=f"Dokumen diupload: {file.filename}",
        after={"file_name": file.filename, "file_type": doc_type.value, "version": version},
    )
    db.commit()
    db.refresh(doc)

    try:
        indexed_chunks = document_rag.index_document(db, doc, content, file.filename)
    except Exception as exc:
        indexed_chunks = 0
        import logging; logging.getLogger(__name__).warning(f"Document RAG indexing skipped: {exc}")

    ai_analysis_supported = file.content_type in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    ai_analysis_requested = analyze_with_ai and ai_analysis_supported
    ai_analysis_complete = False
    if ai_analysis_requested:
        ai_analysis_complete = await _analyze_and_notify(
            doc.id, content, file.filename, doc_type.value,
            project_id, current_user.name, db,
        )

    if ai_analysis_complete:
        message = "Upload dan analisis AI berhasil"
    elif ai_analysis_requested:
        message = "Dokumen tersimpan, tetapi analisis AI gagal. Periksa endpoint model."
    else:
        message = "Upload berhasil"

    return {
        "document_id": doc.id,
        "file_name":   file.filename,
        "file_path":   object_name,
        "version":     version,
        "size_bytes":  len(content),
        "rag_chunks":  indexed_chunks,
        "ai_analysis_complete": ai_analysis_complete,
        "message":     message,
    }


async def _analyze_and_notify(doc_id, content, filename, doc_type, project_id, uploader_name, db):
    """Jalankan analisis AI, persist hasil, lalu trigger integrasi notifikasi."""
    from app.models.user import Project
    try:
        analysis = await ai_service.analyze_document(content=content, filename=filename, doc_type=doc_type)
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.ai_analysis = json.dumps(analysis, ensure_ascii=False)
            db.commit()
        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.project_name if project else f"Proyek #{project_id}"
        from app.models.user import User, UserRole
        managers = db.query(User).filter(User.role.in_(["manager","director"]), User.telegram_id != None).all()
        mgr_ids = [m.telegram_id for m in managers]
        await n8n_service.trigger_tender_analysis(
            document_id=doc_id, project_id=project_id, project_name=project_name,
            file_name=filename, uploader_name=uploader_name,
            analysis_result=analysis, generated_tasks_count=0, manager_telegram_ids=mgr_ids,
        )
        return True
    except Exception as e:
        import logging; logging.getLogger(__name__).error(f"Document AI analysis error: {e}")
        return False


@router.get("", summary="List dokumen per proyek")
def list_documents(
    project_id: int,
    doc_type: Optional[DocumentType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ambil daftar dokumen proyek."""
    _project_for_user(db, project_id, current_user)
    q = db.query(Document).filter(Document.project_id == project_id)
    if current_user.role not in CONTROL_ROLES:
        q = q.filter(Document.file_type.notin_(SENSITIVE_DOCUMENT_TYPES))
    if doc_type:
        q = q.filter(Document.file_type == doc_type)
    docs = q.order_by(Document.created_at.desc()).all()
    result = []
    for d in docs:
        latest_sync = db.query(DocumentSyncSession).filter(
            DocumentSyncSession.document_id == d.id
        ).order_by(DocumentSyncSession.created_at.desc()).first()
        result.append({
            "id":          d.id,
            "file_name":   d.file_name,
            "file_type":   d.file_type,
            "file_size":   d.file_size,
            "version":     d.version,
            "has_ai":      bool(d.ai_analysis),
            "uploaded_by": d.uploaded_by,
            "created_at":  d.created_at,
            "latest_sync_id": latest_sync.id if latest_sync else None,
            "sync_status": latest_sync.status.value if latest_sync else None,
        })
    return result


@router.post("/qa", response_model=DocumentAnswer, summary="Tanya dokumen proyek dengan sumber")
async def question_answer_documents(
    payload: DocumentQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _project_for_user(db, payload.project_id, current_user)
    safety = check_user_question(payload.question)
    if not safety.allowed:
        return {
            "answer": refusal_message(safety),
            "sources": [],
            "governance": "AI Safety Guard memblokir pertanyaan sebelum dikirim ke model.",
            "retrieval_mode": "blocked",
            "safety_status": safety.category,
        }

    docs_query = db.query(Document).filter(Document.project_id == payload.project_id)
    if current_user.role not in CONTROL_ROLES:
        docs_query = docs_query.filter(Document.file_type.notin_(SENSITIVE_DOCUMENT_TYPES))
    docs = docs_query.order_by(Document.created_at.desc()).all()
    if not docs:
        raise HTTPException(status_code=404, detail="Belum ada dokumen pada proyek ini")

    retrieved = document_rag.retrieve_chunks(
        db,
        project_id=payload.project_id,
        question=payload.question,
        allowed_document_ids=[doc.id for doc in docs],
    )
    sources = []
    context_blocks = []
    if retrieved:
        docs_by_id = {doc.id: doc for doc in docs}
        for item in retrieved:
            doc = docs_by_id.get(item.chunk.document_id)
            if not doc:
                continue
            snippet = item.chunk.text[:900]
            sources.append({
                "document_id": doc.id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "version": doc.version,
                "snippet": snippet,
                "chunk_id": item.chunk.id,
                "score": item.score,
            })
            context_blocks.append(
                f"[chunk_id={item.chunk.id}; document_id={doc.id}; file_name={doc.file_name}; "
                f"type={doc.file_type}; version={doc.version}; score={item.score}]\n{snippet}"
            )
    else:
        for doc in docs[:8]:
            source_text = doc.ai_analysis or f"Dokumen {doc.file_name}, tipe {doc.file_type}, versi {doc.version}."
            try:
                parsed = json.loads(source_text) if doc.ai_analysis else source_text
                snippet = json.dumps(parsed, ensure_ascii=False)[:700] if isinstance(parsed, (dict, list)) else str(parsed)[:700]
            except Exception:
                snippet = str(source_text)[:700]
            sources.append({
                "document_id": doc.id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "version": doc.version,
                "snippet": snippet,
            })
            context_blocks.append(
                f"[document_id={doc.id}; file_name={doc.file_name}; type={doc.file_type}; version={doc.version}]\n{snippet}"
            )

    if AIService.is_configured():
        prompt = (
            "Jawab pertanyaan hanya berdasarkan potongan dokumen proyek berikut. "
            "Sebutkan chunk_id, document_id, dan file_name sumber yang dipakai. "
            "Jika data tidak ada pada potongan sumber, katakan tidak ditemukan. "
            "Jangan memakai pengetahuan umum di luar sumber.\n\n"
            f"Pertanyaan: {payload.question}\n\nSumber:\n" + "\n\n---\n\n".join(context_blocks)
        )
        answer = await ai_service.chat(message=prompt)
    else:
        answer = (
            "Mode AI belum aktif karena API key AI kosong. Berikut sumber project-scoped yang relevan "
            "untuk ditinjau: " + ", ".join(f"#{s['document_id']} {s['file_name']}" for s in sources[:5])
        )

    output_safety = check_ai_output(answer, has_sources=bool(sources))
    if not output_safety.allowed:
        answer = refusal_message(output_safety, "Jawaban AI diblokir setelah pemeriksaan output.")

    log_audit(
        db,
        actor_id=current_user.id,
        action="document.qa",
        entity_type="document",
        project_id=payload.project_id,
        summary=f"Document QA: {payload.question[:120]}",
        after={
            "question": payload.question,
            "sources": [s["document_id"] for s in sources],
            "chunk_ids": [s.get("chunk_id") for s in sources if s.get("chunk_id")],
            "retrieval_mode": "chunk_vector" if retrieved else "document_summary",
            "safety_status": output_safety.category,
        },
    )
    db.commit()

    return {
        "answer": answer,
        "sources": sources,
        "governance": "Jawaban dibatasi pada chunk dokumen project_id yang dipilih, melewati safety guard, dan wajib ditinjau manusia sebelum menjadi keputusan.",
        "retrieval_mode": "chunk_vector" if retrieved else "document_summary",
        "safety_status": output_safety.category,
    }


@router.post("/{doc_id}/sync/preview", response_model=DocumentSyncResponse)
async def preview_document_sync(
    doc_id: int,
    payload: DocumentSyncPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CONTROL_ROLES)),
):
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    _ensure_document_access(db, document, current_user)
    if document.file_type not in (DocumentType.TENDER, DocumentType.CONTRACT):
        raise HTTPException(status_code=400, detail="Sinkronisasi hanya tersedia untuk dokumen tender atau kontrak")
    if not document.ai_analysis:
        raise HTTPException(status_code=409, detail="Analisis dokumen belum tersedia. Aktifkan analisis AI terlebih dahulu.")

    existing = db.query(DocumentSyncSession).filter(
        DocumentSyncSession.document_id == document.id
    ).order_by(DocumentSyncSession.created_at.desc()).first()
    if existing and not payload.force_new:
        return _sync_response(existing)

    try:
        analysis = json.loads(document.ai_analysis)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Hasil analisis dokumen tidak valid")

    warnings = []
    task_candidates = analysis.get("tasks") or analysis.get("generated_tasks") or []
    generated_with_ai = False
    if payload.include_tasks and not task_candidates:
        if AIService.is_configured("analysis"):
            try:
                task_candidates = await ai_service.generate_tasks(analysis=analysis, project_id=document.project_id)
                generated_with_ai = bool(task_candidates)
            except Exception as exc:
                warnings.append(f"Generate WBS belum berhasil: {str(exc)[:180]}")
        else:
            warnings.append("API AI belum dikonfigurasi; preview WBS akan tersedia setelah API key dipasang.")

    plan = build_sync_plan(
        db, document=document, analysis=analysis, task_candidates=task_candidates, warnings=warnings,
    )
    selected_ids = [item["id"] for item in plan["changes"]]
    session = DocumentSyncSession(
        document_id=document.id,
        project_id=document.project_id,
        created_by=current_user.id,
        status=DocumentSyncStatus.DRAFT,
        plan_json=json.dumps(plan, ensure_ascii=False),
        selected_change_ids=json.dumps(selected_ids),
        generated_with_ai=generated_with_ai,
    )
    db.add(session)
    db.flush()
    log_audit(
        db,
        actor_id=current_user.id,
        action="document.sync.previewed",
        entity_type="document_sync",
        entity_id=session.id,
        project_id=document.project_id,
        summary=f"Preview sinkronisasi dibuat dari {document.file_name}",
        after={"document_id": document.id, "summary": plan["summary"], "warnings": plan["warnings"]},
    )
    db.commit()
    db.refresh(session)
    return _sync_response(session)


@router.get("/sync/{sync_id}", response_model=DocumentSyncResponse)
def get_document_sync(
    sync_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CONTROL_ROLES)),
):
    session = db.query(DocumentSyncSession).filter(DocumentSyncSession.id == sync_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi sinkronisasi tidak ditemukan")
    _project_for_user(db, session.project_id, current_user)
    return _sync_response(session)


@router.post("/sync/{sync_id}/request-approval", response_model=DocumentSyncResponse)
def request_document_sync_approval(
    sync_id: int,
    payload: DocumentSyncSelection,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CONTROL_ROLES)),
):
    session = db.query(DocumentSyncSession).filter(DocumentSyncSession.id == sync_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi sinkronisasi tidak ditemukan")
    _project_for_user(db, session.project_id, current_user)
    if session.status != DocumentSyncStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Sesi sinkronisasi sudah diajukan atau diproses")
    plan = json.loads(session.plan_json)
    available_ids = {item["id"] for item in plan.get("changes", [])}
    selected_ids = list(dict.fromkeys(payload.change_ids))
    if not set(selected_ids).issubset(available_ids):
        raise HTTPException(status_code=422, detail="Pilihan perubahan tidak sesuai preview")

    if payload.approver_id:
        approver = db.query(User).filter(User.id == payload.approver_id, User.is_active == True).first()
        if not approver or approver.role not in (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER):
            raise HTTPException(status_code=422, detail="Approver harus manager, director, atau admin aktif")

    approval = ApprovalRequest(
        project_id=session.project_id,
        requested_by=current_user.id,
        approver_id=payload.approver_id,
        title=f"Sinkronisasi dokumen #{session.document_id}",
        description=f"Persetujuan untuk menerapkan {len(selected_ids)} perubahan terpilih dari dokumen proyek.",
        approval_type=ApprovalType.SCOPE_CHANGE,
        status=ApprovalStatus.PENDING,
        related_entity_type="document_sync",
        related_entity_id=session.id,
    )
    db.add(approval)
    db.flush()
    session.approval_id = approval.id
    session.selected_change_ids = json.dumps(selected_ids)
    session.status = DocumentSyncStatus.PENDING_APPROVAL
    session.requested_at = datetime.utcnow()

    reviewers = db.query(User).filter(
        User.is_active == True,
        User.role.in_([UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER]),
    ).all()
    for reviewer in reviewers:
        if payload.approver_id and reviewer.id != payload.approver_id:
            continue
        db.add(Notification(
            user_id=reviewer.id,
            title="Approval sinkronisasi dokumen",
            message=f"{current_user.name} mengajukan {len(selected_ids)} perubahan dokumen untuk ditinjau.",
            type="approval",
            related_project_id=session.project_id,
            sent_to_telegram=False,
        ))

    log_audit(
        db,
        actor_id=current_user.id,
        action="document.sync.requested",
        entity_type="document_sync",
        entity_id=session.id,
        project_id=session.project_id,
        summary=f"Sinkronisasi diajukan dengan {len(selected_ids)} perubahan",
        after={"approval_id": approval.id, "selected_change_ids": selected_ids},
    )
    db.commit()
    db.refresh(session)
    return _sync_response(session)


@router.post("/sync/{sync_id}/apply", response_model=DocumentSyncResponse)
def apply_document_sync(
    sync_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CONTROL_ROLES)),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Hanya manager, director, atau admin yang dapat menerapkan sinkronisasi")
    session = db.query(DocumentSyncSession).filter(DocumentSyncSession.id == sync_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi sinkronisasi tidak ditemukan")
    _project_for_user(db, session.project_id, current_user)
    if session.status == DocumentSyncStatus.APPLIED:
        return _sync_response(session)
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == session.approval_id).first()
    if not approval or approval.status != ApprovalStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Sinkronisasi harus disetujui sebelum diterapkan")
    if session.status not in (DocumentSyncStatus.APPROVED, DocumentSyncStatus.FAILED):
        raise HTTPException(status_code=409, detail="Status sinkronisasi belum siap diterapkan")

    selected_ids = json.loads(session.selected_change_ids or "[]")
    plan = json.loads(session.plan_json)
    try:
        result = apply_sync_plan(
            db, plan=plan, selected_change_ids=selected_ids, actor_id=current_user.id,
        )
        session.status = DocumentSyncStatus.APPLIED
        session.applied_by = current_user.id
        session.applied_at = datetime.utcnow()
        session.error_message = None
        log_audit(
            db,
            actor_id=current_user.id,
            action="document.sync.applied",
            entity_type="document_sync",
            entity_id=session.id,
            project_id=session.project_id,
            summary=f"Sinkronisasi dokumen diterapkan: {result['selected_changes']} perubahan",
            before={"selected_change_ids": selected_ids},
            after=result,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failed = db.query(DocumentSyncSession).filter(DocumentSyncSession.id == sync_id).first()
        if failed:
            failed.status = DocumentSyncStatus.FAILED
            failed.error_message = str(exc)[:1000]
            db.commit()
        raise HTTPException(status_code=422, detail=f"Sinkronisasi gagal diterapkan: {str(exc)}")
    db.refresh(session)
    return _sync_response(session)


@router.get("/{doc_id}/download-url", summary="Dapatkan signed URL untuk download")
def get_download_url(
    doc_id: int,
    expires_hours: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate signed URL (private, expires sesuai setting)."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    _ensure_document_access(db, doc, current_user)
    try:
        url = storage_service.get_signed_url(doc.file_path, expires_hours=expires_hours)
        return {"download_url": url, "expires_hours": expires_hours, "file_name": doc.file_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal generate URL: {str(e)}")


@router.get("/{doc_id}/download", summary="Download dokumen privat")
def download_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    _ensure_document_access(db, doc, current_user)
    try:
        content = storage_service.get_file_bytes(doc.file_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Dokumen tidak dapat dibaca: {str(exc)}") from exc
    safe_name = doc.file_name.replace('"', "")
    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/{doc_id}/reindex", summary="Bangun ulang index RAG dokumen")
def reindex_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*CONTROL_ROLES)),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    _ensure_document_access(db, doc, current_user)
    try:
        content = storage_service.get_file_bytes(doc.file_path)
        chunks = document_rag.index_document(db, doc, content, doc.file_name)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Reindex RAG gagal: {str(exc)}")
    log_audit(
        db,
        actor_id=current_user.id,
        action="document.rag_reindexed",
        entity_type="document",
        entity_id=doc.id,
        project_id=doc.project_id,
        summary=f"RAG reindex dokumen: {doc.file_name}",
        after={"chunks": chunks},
    )
    db.commit()
    return {"document_id": doc.id, "file_name": doc.file_name, "rag_chunks": chunks}


@router.get("/{doc_id}/analysis", summary="Ambil hasil analisis AI dokumen")
def get_analysis(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    _ensure_document_access(db, doc, current_user)
    if not doc.ai_analysis:
        raise HTTPException(status_code=404, detail="Analisis AI belum tersedia")
    return {"document_id": doc_id, "analysis": json.loads(doc.ai_analysis)}


@router.delete("/{doc_id}", status_code=204, summary="Hapus dokumen dari DB dan MinIO")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    _ensure_document_access(db, doc, current_user)
    if doc.uploaded_by != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.MANAGER, UserRole.DIRECTOR]:
        raise HTTPException(status_code=403, detail="Akses ditolak")
    sync_count = db.query(DocumentSyncSession).filter(DocumentSyncSession.document_id == doc.id).count()
    if sync_count:
        raise HTTPException(status_code=409, detail="Dokumen memiliki histori sinkronisasi dan tidak dapat dihapus")
    storage_service.delete_file(doc.file_path)
    log_audit(
        db,
        actor_id=current_user.id,
        action="document.deleted",
        entity_type="document",
        entity_id=doc.id,
        project_id=doc.project_id,
        summary=f"Dokumen dihapus: {doc.file_name}",
        before={"file_name": doc.file_name, "file_type": doc.file_type.value, "version": doc.version},
    )
    db.delete(doc)
    db.commit()
