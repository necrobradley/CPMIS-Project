"""
AI Compliance Checker - AI CPMIS
Cek kontrak vs deliverables, temukan missing items.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, Document, Task, Project, DocumentType, UserRole
from app.core.security import require_roles
from app.services.ai_service import AIService
from app.services.report_workflow import ensure_project_access

router = APIRouter(prefix="/compliance", tags=["AI Compliance"])
ai_service = AIService()


@router.post("/{project_id}/check", summary="Cek compliance proyek vs kontrak")
async def check_compliance(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    """
    AI memeriksa:
    - Task yang ada vs scope kontrak
    - Missing deliverables
    - Kelengkapan dokumentasi
    - Status milestone
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)

    # Ambil dokumen kontrak/tender yang sudah dianalisis
    contract_docs = db.query(Document).filter(
        Document.project_id == project_id,
        Document.file_type.in_([DocumentType.CONTRACT, DocumentType.TENDER]),
        Document.ai_analysis != None,
    ).all()

    # Ambil semua task proyek
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    task_titles = [t.title for t in tasks]
    task_statuses = {t.title: t.status for t in tasks}

    if not contract_docs:
        return {
            "project_id": project_id,
            "status": "no_contract",
            "message": "Belum ada dokumen kontrak/tender yang dianalisis untuk proyek ini.",
            "compliance_score": None,
        }

    # Gabungkan semua analisis kontrak
    combined_scope = []
    combined_milestones = []
    combined_requirements = []
    for doc in contract_docs:
        analysis = json.loads(doc.ai_analysis)
        combined_scope      += analysis.get("scope_of_work", [])
        combined_milestones += analysis.get("milestones", [])
        combined_requirements += analysis.get("key_requirements", [])

    # Kirim ke AI untuk compliance check
    system_prompt = """Kamu adalah auditor proyek konstruksi di Indonesia.
Analisis kepatuhan proyek berdasarkan kontrak vs kondisi aktual.
Jawab hanya dalam format JSON yang valid, tanpa markdown."""

    user_message = f"""
Proyek: {project.project_name}
Progress: {project.progress_percent}%
Status: {project.status}

=== DARI KONTRAK ===
Scope of Work: {json.dumps(combined_scope, ensure_ascii=False)}
Milestone: {json.dumps(combined_milestones, ensure_ascii=False)}
Requirements: {json.dumps(combined_requirements, ensure_ascii=False)}

=== KONDISI AKTUAL ===
Total Task: {len(tasks)}
Task yang Ada: {json.dumps(task_titles[:30], ensure_ascii=False)}
Status Task: {json.dumps(dict(list(task_statuses.items())[:20]), ensure_ascii=False)}

Berikan analisis compliance dalam format JSON:
{{
  "compliance_score": 85,
  "status": "compliant|partial|non_compliant",
  "summary": "ringkasan 2-3 kalimat",
  "missing_deliverables": ["item yang ada di kontrak tapi belum ada task-nya"],
  "completed_items": ["item yang sudah selesai"],
  "at_risk_items": ["item yang berisiko tidak terpenuhi"],
  "milestone_status": [{{"name": "nama", "status": "on_track|delayed|completed"}}],
  "recommendations": ["saran 1", "saran 2"]
}}
"""
    try:
        raw = await ai_service._chat_completion(system_prompt, user_message, route="analysis")
        cleaned = raw.strip().lstrip("```json").rstrip("```").strip()
        result = json.loads(cleaned)
    except Exception:
        result = {
            "compliance_score": 0,
            "status": "error",
            "summary": "Gagal menganalisis compliance. Coba lagi.",
            "missing_deliverables": [],
            "completed_items": [],
            "at_risk_items": [],
            "milestone_status": [],
            "recommendations": [],
        }

    return {
        "project_id":    project_id,
        "project_name":  project.project_name,
        "contracts_checked": len(contract_docs),
        "total_tasks":   len(tasks),
        **result,
    }


@router.get("/{project_id}/summary", summary="Ringkasan compliance cepat")
def compliance_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    """Ringkasan cepat tanpa AI — hanya dari data DB."""
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    docs  = db.query(Document).filter(Document.project_id == project_id).all()
    done  = sum(1 for t in tasks if t.status == "done")
    overdue = sum(1 for t in tasks if t.deadline and
                  __import__("datetime").datetime.utcnow() > t.deadline and t.status != "done")
    has_contract = any(d.file_type in [DocumentType.CONTRACT, DocumentType.TENDER] for d in docs)
    return {
        "project_id":     project_id,
        "total_tasks":    len(tasks),
        "done_tasks":     done,
        "overdue_tasks":  overdue,
        "total_documents":len(docs),
        "has_contract":   has_contract,
        "completion_pct": round(done / len(tasks) * 100) if tasks else 0,
    }
