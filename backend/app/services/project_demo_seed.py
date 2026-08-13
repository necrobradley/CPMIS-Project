"""Seed data presentasi lintas fitur untuk paket proyek demo opsional."""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import (
    ApprovalRequest,
    ApprovalStatus,
    ApprovalType,
    AuditLog,
    CommunicationItem,
    CommunicationMessage,
    CommunicationStatus,
    CommunicationType,
    DailyReport,
    DailyReportWorkflow,
    Document,
    DocumentType,
    EvidenceType,
    HandoverItem,
    InspectionRequest,
    MaterialApproval,
    NonConformance,
    Notification,
    ProductivityBenchmark,
    ReportEvidence,
    ReportProgressEntry,
    ReportRequirementCheck,
    ReportReview,
    ReportStatus,
    Task,
    TaskComment,
    TaskMaterialSpecification,
    TaskPriority,
    TaskRequirement,
    TaskStatus,
    User,
    VendorProfile,
    VendorRateCard,
)
from app.services import document_rag
from app.services.storage_service import storage_service


logger = logging.getLogger(__name__)

# PNG transparan 1x1 untuk bukti foto demo. Foto Telegram berikutnya tetap
# disimpan sebagai berkas asli dari pengguna.
DEMO_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _utc(value: str | None, fallback_days: int = 0) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.utcnow() + timedelta(days=fallback_days)


def _task_by_activity(tasks: dict[str, Task], activity_id: str | None) -> Task | None:
    return tasks.get(str(activity_id or ""))


def _upsert_requirements(db: Session, task: Task) -> int:
    specs = (
        ("QUALITY", "Pemeriksaan mutu", "Hasil pekerjaan sesuai spesifikasi dan checklist mutu."),
        ("HSE", "Pemeriksaan K3", "Toolbox meeting, APD, dan area kerja aman telah dikonfirmasi."),
    )
    count = 0
    for sequence, (code, title, description) in enumerate(specs, 1):
        item = db.query(TaskRequirement).filter(
            TaskRequirement.task_id == task.id,
            TaskRequirement.code == code,
        ).first()
        if not item:
            item = TaskRequirement(task_id=task.id, code=code, title=title)
            db.add(item)
        item.title = title
        item.description = description
        item.is_mandatory = True
        item.sequence = sequence
        count += 1
    return count


def _seed_documents(
    db: Session,
    project_id: int,
    owner_id: int,
    documents: list[dict[str, Any]],
) -> tuple[list[Document], list[str]]:
    seeded: list[Document] = []
    warnings: list[str] = []
    for index, item in enumerate(documents, 1):
        file_name = str(item.get("file_name") or f"Demo_Document_{index}.txt")[:255]
        content = str(item.get("content") or "Dokumen proyek demo CPMIS.").encode("utf-8")
        object_name = f"projects/{project_id}/demo/{file_name}"
        try:
            if not storage_service.file_exists(object_name):
                storage_service.upload_file(content, object_name, "text/plain")
        except Exception as exc:
            warnings.append(f"Dokumen {file_name} tidak dapat disimpan: {type(exc).__name__}")
            logger.warning("Demo document upload failed for %s: %s", file_name, exc)
            continue

        document = db.query(Document).filter(
            Document.project_id == project_id,
            Document.file_name == file_name,
        ).first()
        if not document:
            document = Document(
                project_id=project_id,
                uploaded_by=owner_id,
                file_name=file_name,
                file_path=object_name,
            )
            db.add(document)
            db.flush()
        document.file_path = object_name
        document.file_type = DocumentType.OTHER
        document.file_size = len(content)
        document.mime_type = "text/plain"
        document.version = 1
        document.ai_analysis = json.dumps(
            item.get("ai_analysis")
            or {
                "summary": "Dokumen demo telah diindeks untuk pencarian proyek.",
                "risks": ["Koordinasi lintas disiplin", "Keterlambatan material"],
                "source": "demo_dataset",
            },
            ensure_ascii=False,
        )
        db.flush()
        document_rag.index_document(db, document, content, file_name)
        seeded.append(document)
    return seeded, warnings


def _seed_vendors(db: Session, project_id: int, now: datetime) -> tuple[int, int]:
    vendor_specs = (
        {
            "vendor_name": "PT Beton Prima Nusantara",
            "specialty": "Struktur Beton",
            "location": "Jakarta",
            "rating": 88,
            "rate": ("Pekerjaan Beton", "beton,kolom,balok,slab", "m3", 1_350_000),
        },
        {
            "vendor_name": "PT Mekanikal Energi Mandiri",
            "specialty": "MEP dan Commissioning",
            "location": "Tangerang",
            "rating": 84,
            "rate": ("Instalasi MEP", "instalasi,ducting,kabel,panel,pipa", "ls", 165_000_000),
        },
    )
    vendor_count = 0
    rate_count = 0
    for spec in vendor_specs:
        vendor = db.query(VendorProfile).filter(
            VendorProfile.project_id == project_id,
            VendorProfile.vendor_name == spec["vendor_name"],
        ).first()
        if not vendor:
            vendor = VendorProfile(
                project_id=project_id,
                vendor_name=spec["vendor_name"],
                specialty=spec["specialty"],
            )
            db.add(vendor)
            db.flush()
        vendor.specialty = spec["specialty"]
        vendor.location = spec["location"]
        vendor.contact_name = "Koordinator Demo"
        vendor.contact_phone = "+62-21-555-0100"
        vendor.rating = spec["rating"]
        vendor.quality_score = spec["rating"] + 2
        vendor.delivery_score = spec["rating"] - 3
        vendor.safety_score = spec["rating"] + 1
        vendor.capacity_score = spec["rating"]
        vendor.notes = "Vendor dummy untuk simulasi make-or-buy CPMIS."
        category, keywords, unit, price = spec["rate"]
        rate = db.query(VendorRateCard).filter(
            VendorRateCard.vendor_id == vendor.id,
            VendorRateCard.work_category == category,
            VendorRateCard.unit == unit,
        ).first()
        if not rate:
            rate = VendorRateCard(
                vendor_id=vendor.id,
                work_category=category,
                unit=unit,
                unit_price=price,
            )
            db.add(rate)
        rate.work_keywords = keywords
        rate.unit_price = price
        rate.mobilization_cost = 12_500_000
        rate.lead_time_days = 10
        rate.valid_from = now - timedelta(days=30)
        rate.valid_until = now + timedelta(days=365)
        vendor_count += 1
        rate_count += 1
    return vendor_count, rate_count


def _seed_productivity(db: Session, project_id: int) -> int:
    specs = (
        ("Pekerjaan Beton", "beton,kolom,balok,slab", "m3", 18.0, 12, 7_800_000, 2_400_000, 925_000),
        ("Instalasi MEP", "instalasi,panel,kabel,pipa,ducting", "ls", 0.08, 8, 6_200_000, 1_500_000, 42_000_000),
    )
    for category, keywords, unit, output, crew, labor, equipment, material in specs:
        row = db.query(ProductivityBenchmark).filter(
            ProductivityBenchmark.project_id == project_id,
            ProductivityBenchmark.work_category == category,
            ProductivityBenchmark.unit == unit,
            ProductivityBenchmark.crew_size == crew,
            ProductivityBenchmark.source_label == "dataset_demo",
        ).first()
        if not row:
            row = ProductivityBenchmark(
                project_id=project_id,
                work_category=category,
                unit=unit,
                crew_size=crew,
                source_label="dataset_demo",
            )
            db.add(row)
        row.work_keywords = keywords
        row.output_per_day = output
        row.labor_cost_per_day = labor
        row.equipment_cost_per_day = equipment
        row.material_cost_per_unit = material
        row.confidence_score = 86
        row.notes = "Benchmark dummy untuk simulasi produktivitas dan make-or-buy."
    return len(specs)


def _seed_quality_controls(
    db: Session,
    project_id: int,
    tasks: list[Task],
    users: dict[str, User],
    now: datetime,
) -> dict[str, int]:
    materials = [material for task in tasks for material in task.materials][:3]
    for index, material in enumerate(materials):
        approval = db.query(MaterialApproval).filter(
            MaterialApproval.material_id == material.id,
        ).first()
        if not approval:
            approval = MaterialApproval(material_id=material.id)
            db.add(approval)
        approval.status = "approved" if index == 0 else "pending"
        approval.submitted_by = users["staff"].id
        approval.submitted_at = now - timedelta(days=2)
        if approval.status == "approved":
            approval.decided_by = users["manager"].id
            approval.decided_at = now - timedelta(days=1)
            approval.note = "Sertifikat dan sampel material sesuai."

    inspections: list[InspectionRequest] = []
    for index, task in enumerate(tasks[:2]):
        title = f"Inspeksi demo - {task.title[:140]}"
        inspection = db.query(InspectionRequest).filter(
            InspectionRequest.project_id == project_id,
            InspectionRequest.task_id == task.id,
            InspectionRequest.title == title,
        ).first()
        if not inspection:
            inspection = InspectionRequest(
                project_id=project_id,
                task_id=task.id,
                title=title,
                requested_by=users["staff"].id,
            )
            db.add(inspection)
        inspection.inspection_type = "work_inspection"
        inspection.status = "passed" if index == 0 else "pending"
        inspection.due_date = now + timedelta(days=index + 1)
        if inspection.status == "passed":
            inspection.inspected_by = users["manager"].id
            inspection.inspected_at = now - timedelta(hours=8)
            inspection.result_note = "Dimensi, elevasi, dan mutu visual memenuhi checklist."
        inspections.append(inspection)
    db.flush()

    ncr_task = tasks[2] if len(tasks) > 2 else tasks[0]
    ncr = db.query(NonConformance).filter(
        NonConformance.project_id == project_id,
        NonConformance.ncr_number == f"NCR-DEMO-{project_id:03d}-001",
    ).first()
    if not ncr:
        ncr = NonConformance(
            project_id=project_id,
            task_id=ncr_task.id,
            ncr_number=f"NCR-DEMO-{project_id:03d}-001",
            title="Perbaikan hasil pengecoran area mock-up",
        )
        db.add(ncr)
    ncr.inspection_id = inspections[-1].id
    ncr.description = "Ditemukan honeycomb lokal pada area mock-up; perlu metode perbaikan dan inspeksi ulang."
    ncr.severity = "major"
    ncr.status = "open"
    ncr.assigned_to = users["subcontractor"].id
    ncr.due_date = now + timedelta(days=3)
    ncr.corrective_action = "Chipping, grouting non-shrink, curing, kemudian inspeksi ulang."
    return {
        "material_approvals": len(materials),
        "inspections": len(inspections),
        "ncrs": 1,
    }


def _seed_reports(
    db: Session,
    project_id: int,
    tasks: list[Task],
    users: dict[str, User],
    now: datetime,
) -> tuple[list[DailyReport], int]:
    report_tasks = [task for task in tasks if task.assigned_to == users["staff"].id]
    if len(report_tasks) < 3:
        report_tasks = tasks[:3]
    statuses = (ReportStatus.APPROVED, ReportStatus.READY_FOR_REVIEW, ReportStatus.NEEDS_REVISION)
    reports: list[DailyReport] = []
    evidence_count = 0
    for index, (task, status) in enumerate(zip(report_tasks[:3], statuses), 1):
        marker = f"demo-report-{project_id}-{index}"
        report = db.query(DailyReport).filter(
            DailyReport.project_id == project_id,
            DailyReport.telegram_message_id == marker,
        ).first()
        if not report:
            report = DailyReport(
                project_id=project_id,
                user_id=users["staff"].id,
                report_text=f"Laporan dummy untuk {task.title}. Pekerjaan berjalan sesuai koordinasi harian.",
                telegram_message_id=marker,
            )
            db.add(report)
            db.flush()
        report.report_date = now - timedelta(days=3 - index)
        report.weather = ("Cerah", "Berawan", "Hujan ringan")[index - 1]
        report.manpower_count = 14 + index * 3
        report.work_progress = f"Update volume dan progres WBS {task.specification.wbs_code if task.specification else task.id}."
        report.issues = "Tidak ada kendala utama." if index == 1 else "Koordinasi akses material dan area kerja."
        report.ai_summary = f"AI demo: progres {task.title} tercatat dan membutuhkan pemantauan harian."
        report.ai_risks = (
            "Risiko rendah; pertahankan inspeksi mutu."
            if index == 1 else
            "Risiko keterlambatan material dan konflik akses kerja terdeteksi."
        )
        workflow = report.workflow
        if not workflow:
            workflow = DailyReportWorkflow(report_id=report.id, task_id=task.id)
            db.add(workflow)
        workflow.task_id = task.id
        workflow.status = status
        workflow.validation_passed = status != ReportStatus.NEEDS_REVISION
        workflow.validation_score = 100 if workflow.validation_passed else 62.5
        workflow.validation_result = json.dumps(
            {"passed": workflow.validation_passed, "source": "demo_dataset"},
            ensure_ascii=False,
        )
        workflow.submitted_at = report.report_date
        if status in (ReportStatus.APPROVED, ReportStatus.VERIFIED):
            workflow.verified_by = users["manager"].id
            workflow.verified_at = report.report_date + timedelta(hours=4)
        if status == ReportStatus.APPROVED:
            workflow.approved_by = users["director"].id
            workflow.approved_at = report.report_date + timedelta(hours=8)

        quantity = max(1.0, float(task.control.planned_quantity or 10) * 0.05) if task.control else 1.0
        progress = report.progress_entry
        if not progress:
            progress = ReportProgressEntry(report_id=report.id, task_id=task.id)
            db.add(progress)
        progress.task_id = task.id
        progress.quantity_this_report = quantity
        progress.cost_this_report = float(task.control.budget_cost or 0) * 0.05 if task.control else 0
        progress.cumulative_quantity = float(task.control.actual_quantity or 0) if task.control else quantity
        progress.progress_after_approval = float(task.progress_percent or 0)
        if status == ReportStatus.APPROVED:
            progress.applied_at = workflow.approved_at

        for requirement in task.requirements:
            check = db.query(ReportRequirementCheck).filter(
                ReportRequirementCheck.report_id == report.id,
                ReportRequirementCheck.requirement_id == requirement.id,
            ).first()
            if not check:
                check = ReportRequirementCheck(
                    report_id=report.id,
                    requirement_id=requirement.id,
                )
                db.add(check)
            check.confirmed = status != ReportStatus.NEEDS_REVISION
            check.note = "Dikonfirmasi pada data demo." if check.confirmed else "Perlu dilengkapi."

        photo_path = f"projects/{project_id}/demo/evidence/report-{index}.png"
        try:
            if not storage_service.file_exists(photo_path):
                storage_service.upload_file(DEMO_PNG, photo_path, "image/png")
            evidence = db.query(ReportEvidence).filter(
                ReportEvidence.report_id == report.id,
                ReportEvidence.file_path == photo_path,
            ).first()
            if not evidence:
                evidence = ReportEvidence(
                    report_id=report.id,
                    uploaded_by=users["staff"].id,
                    evidence_type=EvidenceType.PHOTO,
                    file_name=f"foto-progres-demo-{index}.png",
                    file_path=photo_path,
                )
                db.add(evidence)
            evidence.file_size = len(DEMO_PNG)
            evidence.mime_type = "image/png"
            evidence.caption = f"Bukti foto dummy WBS {task.specification.wbs_code if task.specification else task.id}"
            evidence.telegram_message_id = f"demo-evidence-{project_id}-{index}"
            evidence_count += 1
        except Exception as exc:
            logger.warning("Demo report evidence upload failed: %s", exc)

        from_status = ReportStatus.DRAFT.value
        review = db.query(ReportReview).filter(
            ReportReview.report_id == report.id,
            ReportReview.to_status == status.value,
        ).first()
        if not review:
            db.add(ReportReview(
                report_id=report.id,
                reviewer_id=(users["director"].id if status == ReportStatus.APPROVED else users["manager"].id),
                from_status=from_status,
                to_status=status.value,
                note="Histori workflow dummy untuk presentasi.",
            ))
        reports.append(report)
    return reports, evidence_count


def _seed_approvals(
    db: Session,
    project_id: int,
    tasks: list[Task],
    users: dict[str, User],
    now: datetime,
) -> int:
    specs = (
        ("Persetujuan metode kerja struktur", ApprovalType.DOCUMENT, ApprovalStatus.PENDING, 0),
        ("Persetujuan mobilisasi tim MEP", ApprovalType.TASK, ApprovalStatus.APPROVED, 1),
        ("Evaluasi perubahan urutan kerja", ApprovalType.SCOPE_CHANGE, ApprovalStatus.REJECTED, 2),
    )
    for title, approval_type, status, task_index in specs:
        row = db.query(ApprovalRequest).filter(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.title == title,
        ).first()
        if not row:
            row = ApprovalRequest(
                project_id=project_id,
                requested_by=users["staff"].id,
                title=title,
            )
            db.add(row)
        row.description = "Data approval dummy untuk demonstrasi routing dan audit keputusan."
        row.approval_type = approval_type
        row.status = status
        row.approver_id = users["manager"].id
        row.related_entity_type = "task"
        row.related_entity_id = tasks[min(task_index, len(tasks) - 1)].id
        row.due_date = now + timedelta(days=task_index + 2)
        if status != ApprovalStatus.PENDING:
            row.decided_by = users["manager"].id
            row.decided_at = now - timedelta(days=1)
            row.decision_note = "Keputusan dummy untuk histori presentasi."
    return len(specs)


def _seed_communications(
    db: Session,
    project_id: int,
    tasks: list[Task],
    users: dict[str, User],
    now: datetime,
) -> int:
    specs = (
        (
            "RFI akses pemasangan ducting lantai 3",
            CommunicationType.RFI,
            CommunicationStatus.OPEN,
            TaskPriority.HIGH,
            now - timedelta(days=2),
        ),
        (
            "Instruksi perlindungan area finishing",
            CommunicationType.SITE_INSTRUCTION,
            CommunicationStatus.ANSWERED,
            TaskPriority.MEDIUM,
            now + timedelta(days=2),
        ),
        (
            "Koordinasi pengiriman panel utama",
            CommunicationType.ISSUE,
            CommunicationStatus.IN_REVIEW,
            TaskPriority.CRITICAL,
            now + timedelta(days=1),
        ),
    )
    for index, (subject, kind, status, priority, due_date) in enumerate(specs):
        row = db.query(CommunicationItem).filter(
            CommunicationItem.project_id == project_id,
            CommunicationItem.subject == subject,
        ).first()
        if not row:
            row = CommunicationItem(
                project_id=project_id,
                created_by=users["staff"].id,
                subject=subject,
            )
            db.add(row)
            db.flush()
        row.assigned_to = users["manager"].id
        row.communication_type = kind
        row.status = status
        row.priority = priority
        row.description = "Koordinasi dummy yang terhubung dengan task proyek."
        row.question = "Mohon arahan dan konfirmasi tindak lanjut."
        row.response = "Ditindaklanjuti sesuai koordinasi proyek." if status == CommunicationStatus.ANSWERED else None
        row.discipline = ("MEP", "Arsitektur", "Elektrikal")[index]
        row.location = "Gedung Inovasi - Zona Demo"
        row.related_task_id = tasks[min(index, len(tasks) - 1)].id
        row.due_date = due_date
        if status == CommunicationStatus.ANSWERED:
            row.answered_at = now - timedelta(hours=6)
        message_text = f"Thread awal untuk {subject}."
        message = db.query(CommunicationMessage).filter(
            CommunicationMessage.communication_id == row.id,
            CommunicationMessage.message == message_text,
        ).first()
        if not message:
            db.add(CommunicationMessage(
                communication_id=row.id,
                user_id=users["staff"].id,
                message_type="comment",
                message=message_text,
                telegram_message_id=f"demo-communication-{project_id}-{index + 1}",
            ))
    return len(specs)


def _seed_notifications(
    db: Session,
    project_id: int,
    tasks: list[Task],
    users: dict[str, User],
) -> int:
    specs = (
        (users["staff"], "Task lapangan siap diperbarui", "Kirim progres melalui website atau Telegram.", "info", tasks[0]),
        (users["manager"], "Laporan menunggu review", "Satu laporan dummy siap diperiksa.", "warning", tasks[1]),
        (users["director"], "Risiko jadwal terdeteksi", "Task critical membutuhkan keputusan mitigasi.", "alert", tasks[2]),
        (users["subcontractor"], "NCR memerlukan tindakan", "Perbaikan mock-up harus diselesaikan sesuai due date.", "deadline", tasks[2]),
    )
    for user, title, message, kind, task in specs:
        row = db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.related_project_id == project_id,
            Notification.title == title,
        ).first()
        if not row:
            row = Notification(user_id=user.id, title=title, message=message)
            db.add(row)
        row.message = message
        row.type = kind
        row.is_read = False
        row.related_task_id = task.id
        row.related_project_id = project_id
        row.sent_to_telegram = bool(user.telegram_id)
    return len(specs)


def _seed_handover_and_comments(
    db: Session,
    project_id: int,
    tasks: list[Task],
    users: dict[str, User],
) -> tuple[int, int]:
    handover_count = 0
    comment_count = 0
    for index, task in enumerate(tasks[:3], 1):
        item = db.query(HandoverItem).filter(
            HandoverItem.project_id == project_id,
            HandoverItem.source_type == "demo_task",
            HandoverItem.source_id == task.id,
        ).first()
        if not item:
            item = HandoverItem(
                project_id=project_id,
                task_id=task.id,
                category="quality_record",
                title=f"Dossier dummy - {task.title[:180]}",
                source_type="demo_task",
                source_id=task.id,
            )
            db.add(item)
        item.status = "collected" if index < 3 else "pending"
        item.auto_collected = True
        handover_count += 1

        text = "Catatan demo: koordinasi lapangan dan bukti progres telah diperiksa."
        comment = db.query(TaskComment).filter(
            TaskComment.task_id == task.id,
            TaskComment.comment == text,
        ).first()
        if not comment:
            db.add(TaskComment(task_id=task.id, user_id=users["manager"].id, comment=text))
        comment_count += 1
    return handover_count, comment_count


def seed_project_demo(
    db: Session,
    *,
    project_id: int,
    owner: User,
    role_users: dict[str, User],
    tasks_by_activity: dict[str, Task],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Seed fitur demo bila manifest ``enabled`` bernilai true."""
    if not manifest.get("enabled"):
        return {"demo_features_seeded": False}

    now = _utc(manifest.get("data_date"))
    tasks = list(dict.fromkeys(tasks_by_activity.values()))
    if not tasks:
        raise ValueError("Paket demo tidak memiliki task untuk mengisi fitur")

    users = {**role_users, "admin": owner}
    for activity_id in manifest.get("blocked_activity_ids") or []:
        task = _task_by_activity(tasks_by_activity, activity_id)
        if task:
            task.status = TaskStatus.BLOCKED
            task.priority = TaskPriority.CRITICAL
            task.deadline = now - timedelta(days=3)
    for activity_id in manifest.get("critical_activity_ids") or []:
        task = _task_by_activity(tasks_by_activity, activity_id)
        if task:
            task.priority = TaskPriority.CRITICAL

    requirement_count = sum(_upsert_requirements(db, task) for task in tasks[:8])
    db.flush()
    documents, document_warnings = _seed_documents(
        db,
        project_id,
        owner.id,
        list(manifest.get("documents") or []),
    )
    vendor_count, rate_count = _seed_vendors(db, project_id, now)
    productivity_count = _seed_productivity(db, project_id)
    quality_counts = _seed_quality_controls(db, project_id, tasks, users, now)
    reports, evidence_count = _seed_reports(db, project_id, tasks, users, now)
    approval_count = _seed_approvals(db, project_id, tasks, users, now)
    communication_count = _seed_communications(db, project_id, tasks, users, now)
    notification_count = _seed_notifications(db, project_id, tasks, users)
    handover_count, comment_count = _seed_handover_and_comments(
        db, project_id, tasks, users
    )

    db.add(AuditLog(
        actor_id=owner.id,
        project_id=project_id,
        action="system.demo_features_seeded",
        entity_type="project",
        entity_id=str(project_id),
        summary="Data dummy lintas fitur dibuat dari paket demo proyek.",
        channel="web",
    ))
    db.commit()
    return {
        "demo_features_seeded": True,
        "demo_documents": len(documents),
        "demo_document_warnings": document_warnings,
        "demo_requirements": requirement_count,
        "demo_reports": len(reports),
        "demo_evidence": evidence_count,
        "demo_approvals": approval_count,
        "demo_communications": communication_count,
        "demo_notifications": notification_count,
        "demo_vendors": vendor_count,
        "demo_vendor_rates": rate_count,
        "demo_productivity_benchmarks": productivity_count,
        "demo_handover_items": handover_count,
        "demo_task_comments": comment_count,
        **quality_counts,
    }
