import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import (
    ApprovalStatus,
    DailyReport,
    DailyReportWorkflow,
    ReportProgressEntry,
    ReportRequirementCheck,
    ReportStatus,
    Task,
    TaskStatus,
    User,
)
from app.services.report_workflow import can_access_task


MIN_AUTO_GROUP_CONFIDENCE = 0.45


@dataclass
class TelegramReportFields:
    report_text: str
    weather: str | None = None
    manpower_count: int | None = None
    work_progress: str | None = None
    issues: str | None = None
    actual_quantity: float | None = None
    actual_unit: str | None = None
    actual_cost: float | None = None


@dataclass
class TaskMatch:
    task: Task
    confidence: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class AutoGroupingResult:
    task: Task | None
    confidence: float
    reasons: list[str]
    candidates: list[TaskMatch]
    fields: TelegramReportFields

    @property
    def is_confident(self) -> bool:
        return self.task is not None and self.confidence >= MIN_AUTO_GROUP_CONFIDENCE


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def tokenize(value: str | None) -> set[str]:
    stopwords = {
        "dan", "atau", "yang", "untuk", "dengan", "pada", "area", "zona",
        "pekerjaan", "progres", "progress", "hari", "ini", "sudah",
    }
    return {
        token for token in re.findall(r"[a-zA-Z0-9]+", normalize_text(value))
        if len(token) >= 3 and token not in stopwords
    }


def telegram_field(text: str, label: str) -> str | None:
    labels = "Cuaca|Pekerja|Manpower|Progress|Progres|Kendala|Issue"
    match = re.search(
        rf"(?:^|[\n.;,])\s*{re.escape(label)}\s*:\s*(.*?)(?=(?:[\n.;,]\s*(?:{labels})\s*:)|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip(" \t\r\n.;,") if match else None


def _parse_decimal(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(".", "").replace(",", ".") if "," in value else value)
    except ValueError:
        return None


def parse_quantity(text: str) -> tuple[float | None, str | None]:
    unit_pattern = (
        r"m2|m²|meter\s+persegi|sqm|m3|m³|meter\s+kubik|"
        r"meter|m\b|kg|ton|unit|buah|set|lembar|batang"
    )
    match = re.search(
        rf"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>{unit_pattern})",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None, None
    unit = normalize_text(match.group("unit"))
    unit = {
        "m²": "m2",
        "meter persegi": "m2",
        "sqm": "m2",
        "m³": "m3",
        "meter kubik": "m3",
        "meter": "m",
    }.get(unit, unit)
    return _parse_decimal(match.group("qty")), unit


def parse_manpower(text: str, labelled_value: str | None = None) -> int | None:
    manpower_match = re.search(r"\d+", labelled_value or "")
    if manpower_match:
        return int(manpower_match.group())
    match = re.search(
        r"(?P<count>\d+)\s*(?:orang|pekerja|tukang|mandor|crew|personel)\b",
        text,
        re.IGNORECASE,
    )
    return int(match.group("count")) if match else None


def parse_weather(text: str) -> str | None:
    labelled = telegram_field(text, "Cuaca")
    if labelled:
        return labelled
    lowered = normalize_text(text)
    for keyword in ("hujan", "cerah", "mendung", "panas", "gerimis", "berawan"):
        if keyword in lowered:
            return keyword
    return None


def parse_issues(text: str) -> str | None:
    labelled = telegram_field(text, "Kendala") or telegram_field(text, "Issue")
    if labelled:
        return labelled
    match = re.search(r"(?:kendala|hambatan|issue|masalah)\s*[:\-]?\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip(" .;,") if match else None


def parse_report_fields(text: str) -> TelegramReportFields:
    manpower_text = telegram_field(text, "Pekerja") or telegram_field(text, "Manpower")
    progress = telegram_field(text, "Progress") or telegram_field(text, "Progres")
    quantity, unit = parse_quantity(text)
    return TelegramReportFields(
        report_text=text.strip(),
        weather=parse_weather(text),
        manpower_count=parse_manpower(text, manpower_text),
        work_progress=progress or text.strip(),
        issues=parse_issues(text),
        actual_quantity=quantity,
        actual_unit=unit,
    )


def merge_ai_report_fields(base: TelegramReportFields, payload: dict | None) -> TelegramReportFields:
    if not payload:
        return base
    quantity = payload.get("actual_quantity") or payload.get("quantity") or base.actual_quantity
    cost = payload.get("actual_cost") or payload.get("cost") or base.actual_cost
    return TelegramReportFields(
        report_text=(payload.get("report_text") or base.report_text or "").strip(),
        weather=payload.get("weather") or base.weather,
        manpower_count=payload.get("manpower_count") or base.manpower_count,
        work_progress=payload.get("work_progress") or base.work_progress,
        issues=payload.get("issues") or base.issues,
        actual_quantity=float(quantity) if quantity not in (None, "") else None,
        actual_unit=payload.get("actual_unit") or payload.get("unit") or base.actual_unit,
        actual_cost=float(cost) if cost not in (None, "") else None,
    )


def accessible_open_tasks(db: Session, user: User) -> list[Task]:
    query = db.query(Task).filter(
        Task.status != TaskStatus.DONE,
        Task.assigned_to == user.id,
        or_(
            Task.approval_status == ApprovalStatus.APPROVED.value,
            Task.approval_status.is_(None),
        ),
    )
    tasks = query.all()
    return [task for task in tasks if can_access_task(user, task)]


def task_search_text(task: Task) -> str:
    parts: list[str] = [
        task.title,
        task.description,
        task.project.project_name if task.project else "",
        task.division.division_name if task.division else "",
    ]
    if task.specification:
        parts.extend([
            task.specification.wbs_code,
            task.specification.work_package,
            task.specification.location,
            task.specification.acceptance_criteria,
            task.specification.reporting_instructions,
        ])
    if task.control:
        parts.extend([task.control.location, task.control.unit, task.control.revision_note])
    parts.extend(requirement.code for requirement in task.requirements)
    parts.extend(requirement.title for requirement in task.requirements)
    parts.extend(material.material_name for material in task.materials)
    parts.extend(material.material_code or "" for material in task.materials)
    return " ".join(part for part in parts if part)


def score_task(task: Task, message: str, user: User, total_accessible: int) -> TaskMatch:
    text = normalize_text(message)
    message_tokens = tokenize(message)
    task_tokens = tokenize(task_search_text(task))
    reasons: list[str] = []
    score = 0.0

    if total_accessible == 1:
        score += 0.35
        reasons.append("hanya ada satu task aktif yang dapat diakses")

    if task.assigned_to == user.id:
        score += 0.12
        reasons.append("task ditugaskan ke pelapor")

    if task.division_id and user.division_id and task.division_id == user.division_id:
        score += 0.08
        reasons.append("task berada di divisi pelapor")

    specification = task.specification
    if specification and specification.wbs_code:
        wbs = normalize_text(specification.wbs_code)
        if wbs and wbs in text:
            score += 0.40
            reasons.append(f"WBS cocok: {specification.wbs_code}")

    if specification and specification.location:
        location = normalize_text(specification.location)
        if location and location in text:
            score += 0.18
            reasons.append(f"lokasi cocok: {specification.location}")

    title_tokens = tokenize(task.title)
    title_overlap = len(message_tokens & title_tokens)
    if title_tokens:
        ratio = title_overlap / max(len(title_tokens), 1)
        if ratio:
            score += min(0.25, ratio * 0.25)
            reasons.append("judul task cocok sebagian")

    overlap = len(message_tokens & task_tokens)
    if message_tokens:
        ratio = overlap / max(len(message_tokens), 1)
        if ratio:
            score += min(0.25, ratio * 0.30)
            reasons.append("keyword laporan cocok dengan detail task")

    return TaskMatch(task=task, confidence=round(min(score, 0.98), 2), reasons=reasons)


def auto_group_message(db: Session, user: User, message: str) -> AutoGroupingResult:
    fields = parse_report_fields(message)
    tasks = accessible_open_tasks(db, user)
    matches = sorted(
        (score_task(task, message, user, len(tasks)) for task in tasks),
        key=lambda item: item.confidence,
        reverse=True,
    )
    best = matches[0] if matches else None
    return AutoGroupingResult(
        task=best.task if best else None,
        confidence=best.confidence if best else 0.0,
        reasons=best.reasons if best else [],
        candidates=matches[:3],
        fields=fields,
    )


def create_report_draft(
    db: Session,
    user: User,
    task: Task,
    fields: TelegramReportFields,
    telegram_message_id: str | None = None,
) -> DailyReport:
    if task.assigned_to != user.id:
        raise ValueError("Laporan Telegram hanya dapat dibuat untuk task yang ditugaskan kepada pengguna")
    report = DailyReport(
        project_id=task.project_id,
        user_id=user.id,
        report_text=fields.report_text,
        weather=fields.weather,
        manpower_count=fields.manpower_count,
        work_progress=fields.work_progress,
        issues=fields.issues,
        telegram_message_id=telegram_message_id,
    )
    db.add(report)
    db.flush()
    report.workflow = DailyReportWorkflow(task_id=task.id, status=ReportStatus.DRAFT)
    if fields.actual_quantity is not None or fields.actual_cost is not None:
        report.progress_entry = ReportProgressEntry(
            task_id=task.id,
            quantity_this_report=fields.actual_quantity or 0,
            cost_this_report=fields.actual_cost or 0,
        )

    lowered = normalize_text(fields.report_text)
    for requirement in task.requirements:
        pattern = rf"{re.escape(requirement.code.lower())}\s*:\s*(ya|yes|sesuai|ok)"
        db.add(ReportRequirementCheck(
            report_id=report.id,
            requirement_id=requirement.id,
            confirmed=bool(re.search(pattern, lowered)),
            note="Auto grouping Telegram",
        ))
    db.commit()
    db.refresh(report)
    return report


def open_report_draft(
    db: Session,
    user: User,
    task: Task,
    telegram_message_id: str | None = None,
) -> DailyReport:
    """Persist the Telegram task selection before the next webhook update arrives."""
    if task.assigned_to != user.id:
        raise ValueError("Task bukan assignment langsung pengguna")
    existing = db.query(DailyReport).join(DailyReportWorkflow).filter(
        DailyReport.user_id == user.id,
        DailyReportWorkflow.task_id == task.id,
        DailyReportWorkflow.status.in_((ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION)),
    ).order_by(DailyReport.created_at.desc(), DailyReport.id.desc()).first()
    if existing and not (existing.report_text or "").strip() and not existing.evidence:
        # Selecting a task is a persisted workflow action. Touch the workflow so
        # the next Telegram webhook can recover the same active draft even when
        # Vercel routes it to a different serverless instance.
        existing.workflow.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    # A report that already contains narrative or evidence belongs to the
    # previous reporting cycle. Preserve it and open a clean report so evidence
    # counters start from zero after the user selects /report again.
    return create_report_draft(
        db=db,
        user=user,
        task=task,
        fields=TelegramReportFields(report_text="", work_progress=""),
        telegram_message_id=telegram_message_id,
    )


def update_report_draft(
    db: Session,
    report: DailyReport,
    fields: TelegramReportFields,
    telegram_message_id: str | None = None,
) -> DailyReport:
    """Fill the draft selected earlier without changing its task relationship."""
    if not report.workflow or report.workflow.status not in (
        ReportStatus.DRAFT,
        ReportStatus.NEEDS_REVISION,
    ):
        raise ValueError("Draft laporan tidak dapat diperbarui")
    report.report_text = fields.report_text
    report.weather = fields.weather
    report.manpower_count = fields.manpower_count
    report.work_progress = fields.work_progress
    report.issues = fields.issues
    report.telegram_message_id = telegram_message_id or report.telegram_message_id

    if fields.actual_quantity is not None or fields.actual_cost is not None:
        if not report.progress_entry:
            report.progress_entry = ReportProgressEntry(task_id=report.workflow.task_id)
        report.progress_entry.quantity_this_report = fields.actual_quantity or 0
        report.progress_entry.cost_this_report = fields.actual_cost or 0

    lowered = normalize_text(fields.report_text)
    checks_by_requirement = {
        check.requirement_id: check for check in report.requirement_checks
    }
    for requirement in report.workflow.task.requirements:
        check = checks_by_requirement.get(requirement.id)
        if not check:
            check = ReportRequirementCheck(
                report_id=report.id,
                requirement_id=requirement.id,
                note="Auto grouping Telegram",
            )
            db.add(check)
        pattern = rf"{re.escape(requirement.code.lower())}\s*:\s*(ya|yes|sesuai|ok)"
        check.confirmed = bool(re.search(pattern, lowered))

    db.commit()
    db.refresh(report)
    return report


def format_grouping_confirmation(report: DailyReport, result: AutoGroupingResult) -> str:
    task = result.task
    specification = task.specification if task else None
    wbs = specification.wbs_code if specification else f"Task #{task.id if task else '-'}"
    reasons = ", ".join(result.reasons[:3]) or "akses user dan keyword laporan"
    required_photos = specification.required_photo_count if specification else 0
    required_documents = specification.required_document_count if specification else 0
    quantity_line = (
        f"Volume terdeteksi: {result.fields.actual_quantity:g} {result.fields.actual_unit or ''}.\n"
        if result.fields.actual_quantity is not None else ""
    )
    return (
        f"Draft laporan #{report.id} dibuat otomatis.\n\n"
        f"Project: {task.project.project_name if task and task.project else '-'}\n"
        f"Task: {wbs} - {task.title if task else '-'}\n"
        f"Confidence: {round(result.confidence * 100)}%\n"
        f"Alasan: {reasons}\n\n"
        f"{quantity_line}"
        f"Bukti wajib: {required_photos} foto, {required_documents} dokumen.\n"
        "Kirim foto/dokumen tambahan bila ada, lalu jalankan /submit."
    )


def format_clarification(result: AutoGroupingResult) -> str:
    if not result.candidates:
        return (
            "Saya belum menemukan task aktif yang cocok untuk laporan ini.\n"
            "Gunakan /report untuk memilih WBS, atau tambahkan kode WBS/lokasi di caption."
        )
    lines = [
        "Saya belum yakin laporan ini masuk task mana.",
        "Gunakan /report untuk memilih task, atau kirim ulang dengan kode WBS/lokasi.",
        "",
        "Kandidat terdekat:",
    ]
    for index, match in enumerate(result.candidates, 1):
        specification = match.task.specification
        wbs = specification.wbs_code if specification else f"Task #{match.task.id}"
        lines.append(f"{index}. {wbs} - {match.task.title} ({round(match.confidence * 100)}%)")
    return "\n".join(lines)
