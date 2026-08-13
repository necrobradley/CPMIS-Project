"""
Telegram Bot Service - AI CPMIS (Lengkap)
Semua command: /start /help /tasks /laporan /report /upload /summary /status /ai
"""
import logging
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import (
    User, DailyReport, DailyReportWorkflow, EvidenceType, Project, ReportEvidence,
    ReportRequirementCheck, ReportReview, ReportStatus, Task, TaskStatus,
)
from app.services.ai_service import AIService
from app.services.n8n_service import n8n_service
from app.services.report_workflow import apply_validation, can_access_task, validate_report
from app.services.storage_service import storage_service
from app.services.telegram_auto_grouping import (
    accessible_open_tasks,
    auto_group_message,
    create_report_draft,
    format_clarification,
    format_grouping_confirmation,
    merge_ai_report_fields,
    open_report_draft,
    parse_report_fields,
    update_report_draft,
)

logger = logging.getLogger(__name__)
ai_service = AIService()


def get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def get_user_by_telegram(telegram_id: str, db: Session):
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


# ─── /start ─────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    db.close()

    if user:
        text = (
            f"👋 Halo, *{user.name}*!\n\n"
            f"Role: `{user.role}`\n\n"
            "📋 *Perintah Tersedia:*\n"
            "/tasks — Lihat task saya\n"
            "/report — Buat laporan berdasarkan task/WBS\n"
            "/submit — Periksa dan kirim draft aktif\n"
            "/status — Status proyek aktif\n"
            "/summary — Ringkasan minggu ini\n"
            "/ai [pertanyaan] — Tanya AI\n"
            "/help — Bantuan lengkap\n\n"
            "Gunakan /report agar laporan, task, dan evidence selalu terhubung."
        )
    else:
        text = (
            "👋 Selamat datang di *Rencanix Bot*!\n\n"
            "Akun Telegram Anda belum terdaftar.\n"
            f"Telegram ID Anda: `{telegram_id}`\n\n"
            "Kirim Telegram ID ini ke administrator untuk menghubungkan akun."
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /help ──────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Panduan Rencanix Bot*\n\n"
        "*/start* — Menu utama\n"
        "*/tasks* — Daftar task Anda\n"
        "*/laporan* — Panduan buat laporan harian\n"
        "*/report* — Buat laporan harian interaktif\n"
        "*/submit* — Validasi dan kirim draft aktif\n"
        "*/status* — Status semua proyek aktif\n"
        "*/summary* — Ringkasan mingguan AI\n"
        "*/ai [tanya]* — Tanya AI konstruksi\n\n"
        "📸 *Kirim foto* → Evidence draft aktif\n"
        "📎 *Kirim dokumen* → Evidence draft aktif"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /tasks ─────────────────────────────────────────────────────
async def my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("❌ Akun belum terdaftar.")
        db.close()
        return

    tasks = db.query(Task).filter(
        Task.assigned_to == user.id,
        Task.status != TaskStatus.DONE
    ).order_by(Task.deadline.asc()).limit(10).all()
    db.close()

    if not tasks:
        await update.message.reply_text("✅ Tidak ada task pending!")
        return

    lines = ["📋 *Task Anda:*\n"]
    status_emoji = {"todo": "⬜", "in_progress": "🔄", "review": "👀", "blocked": "🚫"}
    priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    for i, t in enumerate(tasks, 1):
        dl = t.deadline.strftime("%d/%m/%Y") if t.deadline else "—"
        overdue = t.deadline and t.deadline < datetime.utcnow() and t.status != "done"
        lines.append(
            f"{i}. {status_emoji.get(t.status,'⬜')} {priority_emoji.get(t.priority,'🟡')} "
            f"*{t.title}*\n"
            f"   Deadline: {dl}{' ⚠️' if overdue else ''}\n"
        )
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_tasks")]]
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─── /status ────────────────────────────────────────────────────
async def project_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("❌ Akun belum terdaftar.")
        db.close()
        return

    projects = db.query(Project).filter(Project.status == "active").limit(5).all()
    db.close()

    if not projects:
        await update.message.reply_text("ℹ️ Tidak ada proyek aktif saat ini.")
        return

    status_bar = lambda p: "█" * int(p / 10) + "░" * (10 - int(p / 10))
    lines = ["📊 *Status Proyek Aktif:*\n"]
    for p in projects:
        lines.append(
            f"🏗️ *{p.project_name}*\n"
            f"`{status_bar(p.progress_percent)}` {p.progress_percent}%\n"
            f"📍 {p.location or '—'}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── /laporan ───────────────────────────────────────────────────
async def laporan_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📝 *Panduan Laporan Harian*\n\n"
        "Kirim laporan dalam format bebas, contoh:\n\n"
        "```\n"
        "Laporan 14 Mei 2025\n"
        "Cuaca: Cerah\n"
        "Pekerja: 30 orang\n"
        "Progress: Pengecoran lantai 3 selesai 80%\n"
        "Kendala: Material besi terlambat datang\n"
        "```\n\n"
        "AI akan otomatis memproses & mengirim ringkasan ke supervisor.\n\n"
        "Atau gunakan /report untuk panduan interaktif."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /report (interaktif) ────────────────────────────────────────
async def report_interactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("❌ Akun belum terdaftar.")
        db.close()
        return
    tasks = sorted(
        accessible_open_tasks(db, user),
        key=lambda task: (task.deadline is None, task.deadline, task.id),
    )[:10]
    if not tasks:
        db.close()
        await update.message.reply_text("Tidak ada task aktif yang dapat Anda laporkan.")
        return

    keyboard = [[InlineKeyboardButton(
        f"{task.specification.wbs_code if task.specification else task.id} - {task.title[:28]}",
        callback_data=f"select_task_{task.id}",
    )] for task in tasks]
    db.close()
    await update.message.reply_text(
        "Pilih task/WBS yang akan dilaporkan:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── /summary ───────────────────────────────────────────────────
async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("❌ Akun belum terdaftar.")
        db.close()
        return

    await update.message.reply_text("⏳ Membuat ringkasan mingguan dengan AI...")

    # Ambil data minggu ini
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    tasks_done = db.query(Task).filter(
        Task.assigned_to == user.id,
        Task.status == "done",
    ).count()
    tasks_total = db.query(Task).filter(Task.assigned_to == user.id).count()
    reports_this_week = db.query(DailyReport).filter(
        DailyReport.user_id == user.id,
        DailyReport.report_date >= week_ago,
    ).count()
    db.close()

    try:
        summary = await ai_service.chat(
            message=f"Buat ringkasan kinerja mingguan singkat untuk {user.name} (role: {user.role}) "
                    f"yang menyelesaikan {tasks_done} dari {tasks_total} task dan "
                    f"mengirim {reports_this_week} laporan minggu ini. "
                    f"Berikan apresiasi dan motivasi dalam 3-4 kalimat.",
        )
        text = (
            f"📊 *Ringkasan Mingguan — {user.name}*\n\n"
            f"✅ Task selesai: {tasks_done}/{tasks_total}\n"
            f"📝 Laporan dikirim: {reports_this_week}\n\n"
            f"🤖 *AI Insight:*\n{summary}"
        )
    except Exception:
        text = (
            f"📊 *Ringkasan Mingguan — {user.name}*\n\n"
            f"✅ Task selesai: {tasks_done}/{tasks_total}\n"
            f"📝 Laporan dikirim: {reports_this_week}"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /ai [pertanyaan] ───────────────────────────────────────────
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Contoh: `/ai Bagaimana cara mengelola risiko keterlambatan?`",
            parse_mode="Markdown"
        )
        return
    question = " ".join(context.args)
    await update.message.reply_text("🤔 Sedang berpikir...")
    try:
        response = await ai_service.chat(message=question)
        await update.message.reply_text(f"🤖 {response}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ─── Handle teks bebas → draft laporan terstruktur ──────────────
def _telegram_field(text: str, label: str) -> str | None:
    match = re.search(rf"^{re.escape(label)}\s*:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


async def _enrich_fields_with_ai(text: str, user: User, fields):
    if not settings.TELEGRAM_AI_PARSE_ENABLED:
        return fields
    try:
        payload = await ai_service.parse_telegram_report(text, user.name)
        return merge_ai_report_fields(fields, payload)
    except Exception as exc:
        logger.warning("Telegram AI parse fallback to local parser: %s", exc)
        return fields


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)

    if not user:
        await update.message.reply_text("❌ Akun belum terdaftar. Hubungi administrator.")
        db.close()
        return

    active_report = _get_active_report(user, context, db)
    task_id = (
        active_report.workflow.task_id
        if active_report and active_report.workflow
        else context.user_data.get("selected_task_id")
    )
    if not task_id:
        text = update.message.text.strip()
        result = auto_group_message(db, user, text)
        if not result.is_confident:
            await update.message.reply_text(format_clarification(result))
            db.close()
            return
        result.fields = await _enrich_fields_with_ai(text, user, result.fields)

        report = create_report_draft(
            db=db,
            user=user,
            task=result.task,
            fields=result.fields,
            telegram_message_id=str(update.message.message_id),
        )
        context.user_data["active_report_id"] = report.id
        context.user_data["selected_task_id"] = result.task.id
        await update.message.reply_text(format_grouping_confirmation(report, result))
        db.close()
        return

    task = db.query(Task).filter(Task.id == int(task_id)).first()
    if not task or not can_access_task(user, task):
        await update.message.reply_text("Task tidak tersedia. Jalankan /report kembali.")
        db.close()
        return

    text = update.message.text.strip()
    if len(text) < 20:
        await update.message.reply_text(
            "💬 Pesan terlalu pendek.\n"
            "Gunakan /help untuk melihat perintah yang tersedia."
        )
        db.close()
        return

    try:
        fields = await _enrich_fields_with_ai(text, user, parse_report_fields(text))
        report = (
            update_report_draft(
                db=db,
                report=active_report,
                fields=fields,
                telegram_message_id=str(update.message.message_id),
            )
            if active_report
            else create_report_draft(
                db=db,
                user=user,
                task=task,
                fields=fields,
                telegram_message_id=str(update.message.message_id),
            )
        )
        context.user_data["active_report_id"] = report.id

        specification = task.specification
        reply = (
            f"Draft laporan #{report.id} tersimpan untuk *{task.title}*.\n\n"
            f"Bukti wajib: {specification.required_photo_count if specification else 0} foto, "
            f"{specification.required_document_count if specification else 0} dokumen.\n"
            "Kirim bukti sekarang, lalu jalankan /submit."
        )
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing report: {e}")
        await update.message.reply_text("Gagal menyimpan draft. Coba lagi atau hubungi admin.")
    finally:
        db.close()


# ─── Handle foto ────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    db.close()

    if not user:
        await update.message.reply_text("❌ Akun belum terdaftar.")
        return

    caption = update.message.caption or "Foto lapangan"
    # Download foto terbesar
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    await update.message.reply_text(
        f"📸 *Foto diterima!*\n"
        f"Caption: {caption}\n"
        f"File ID: `{photo.file_id}`\n\n"
        f"_Foto sedang disimpan ke penyimpanan proyek..._",
        parse_mode="Markdown"
    )


def _get_active_report(user: User, context: ContextTypes.DEFAULT_TYPE, db: Session):
    report_id = context.user_data.get("active_report_id")
    active_statuses = (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION)
    query = db.query(DailyReport).join(DailyReportWorkflow).filter(
        DailyReport.user_id == user.id,
        DailyReportWorkflow.status.in_(active_statuses),
    )
    if report_id:
        report = query.filter(DailyReport.id == int(report_id)).first()
        if report:
            return report

    # Vercel dapat memproses update berikutnya pada instance lain sehingga
    # context.user_data tidak selalu tersedia. Database menjadi sumber status
    # draft yang persisten untuk foto, dokumen, dan perintah /submit.
    return query.order_by(
        DailyReportWorkflow.updated_at.desc(),
        DailyReport.id.desc(),
    ).first()


async def handle_structured_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("Akun belum terdaftar.")
        db.close()
        return
    report = _get_active_report(user, context, db)
    if not report or not report.workflow:
        await update.message.reply_text(
            "Foto belum disimpan. Jalankan /report dan pilih task terlebih dahulu, "
            "lalu kirim foto untuk draft yang baru dibuka."
        )
        db.close()
        return
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        await update.message.reply_text("Laporan sedang direview; evidence sudah dikunci.")
        db.close()
        return

    photo = update.message.photo[-1]
    telegram_file = await context.bot.get_file(photo.file_id)
    content = bytes(await telegram_file.download_as_bytearray())
    object_name = (
        f"projects/{report.project_id}/tasks/{report.workflow.task_id}/"
        f"reports/{report.id}/photos/{uuid.uuid4()}.jpg"
    )
    storage_service.upload_file(content, object_name, "image/jpeg")
    db.add(ReportEvidence(
        report_id=report.id,
        uploaded_by=user.id,
        evidence_type=EvidenceType.PHOTO,
        file_name=f"telegram-photo-{update.message.message_id}.jpg",
        file_path=object_name,
        file_size=len(content),
        mime_type="image/jpeg",
        caption=update.message.caption or "Foto lapangan",
        telegram_message_id=str(update.message.message_id),
    ))
    db.commit()
    photo_count = db.query(ReportEvidence).filter(
        ReportEvidence.report_id == report.id,
        ReportEvidence.evidence_type == EvidenceType.PHOTO,
    ).count()
    specification = report.workflow.task.specification
    required = specification.required_photo_count if specification else 0
    report_id = report.id
    db.close()
    await update.message.reply_text(
        f"Foto tersimpan ke laporan #{report_id}. Progress bukti foto: {photo_count}/{required}."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("Akun belum terdaftar.")
        db.close()
        return
    report = _get_active_report(user, context, db)
    if not report or not report.workflow:
        await update.message.reply_text(
            "Dokumen belum disimpan. Jalankan /report dan pilih task terlebih dahulu, "
            "lalu kirim dokumen untuk draft yang baru dibuka."
        )
        db.close()
        return
    if report.workflow.status not in (ReportStatus.DRAFT, ReportStatus.NEEDS_REVISION):
        await update.message.reply_text("Laporan sedang direview; evidence sudah dikunci.")
        db.close()
        return

    document = update.message.document
    telegram_file = await context.bot.get_file(document.file_id)
    content = bytes(await telegram_file.download_as_bytearray())
    extension = Path(document.file_name or "evidence.bin").suffix.lower() or ".bin"
    object_name = (
        f"projects/{report.project_id}/tasks/{report.workflow.task_id}/"
        f"reports/{report.id}/documents/{uuid.uuid4()}{extension}"
    )
    mime_type = document.mime_type or "application/octet-stream"
    storage_service.upload_file(content, object_name, mime_type)
    db.add(ReportEvidence(
        report_id=report.id,
        uploaded_by=user.id,
        evidence_type=EvidenceType.DOCUMENT,
        file_name=document.file_name or f"telegram-document{extension}",
        file_path=object_name,
        file_size=len(content),
        mime_type=mime_type,
        caption=update.message.caption,
        telegram_message_id=str(update.message.message_id),
    ))
    db.commit()
    document_count = db.query(ReportEvidence).filter(
        ReportEvidence.report_id == report.id,
        ReportEvidence.evidence_type == EvidenceType.DOCUMENT,
    ).count()
    specification = report.workflow.task.specification
    required = specification.required_document_count if specification else 0
    report_id = report.id
    db.close()
    await update.message.reply_text(
        f"Dokumen tersimpan ke laporan #{report_id}. Progress dokumen: {document_count}/{required}."
    )


async def submit_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    db = get_db()
    user = get_user_by_telegram(telegram_id, db)
    if not user:
        await update.message.reply_text("Akun belum terdaftar.")
        db.close()
        return
    report = _get_active_report(user, context, db)
    if not report or not report.workflow:
        await update.message.reply_text("Belum ada draft aktif.")
        db.close()
        return

    before_status = report.workflow.status.value
    result = validate_report(report)
    apply_validation(report.workflow, result)
    db.add(ReportReview(
        report_id=report.id,
        reviewer_id=user.id,
        from_status=before_status,
        to_status=report.workflow.status.value,
        note=result["summary"],
    ))
    db.commit()
    report_id = report.id
    if result["passed"]:
        context.user_data.pop("active_report_id", None)
        context.user_data.pop("selected_task_id", None)
        message = f"Laporan #{report_id} lolos pemeriksaan dan masuk antrean review atasan."
    else:
        missing = [
            f"- {item['label']}: {item['message']}"
            for item in result["items"] if not item["passed"]
        ]
        message = (
            f"Laporan #{report_id} perlu dilengkapi ({result['score']}%).\n"
            + "\n".join(missing[:8])
            + "\n\nPerbaiki melalui web atau buat ulang sesi /report."
        )
    db.close()
    await update.message.reply_text(message)


# ─── Callback query ─────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "refresh_tasks":
        await my_tasks(query, context)
    elif query.data.startswith("select_task_"):
        task_id = int(query.data.replace("select_task_", ""))
        db = get_db()
        telegram_id = str(update.effective_user.id)
        user = get_user_by_telegram(telegram_id, db)
        task = db.query(Task).filter(Task.id == task_id).first()
        if (
            not user
            or not task
            or task.status == TaskStatus.DONE
            or not can_access_task(user, task)
            or task.assigned_to != user.id
        ):
            db.close()
            await query.edit_message_text(
                "Task bukan assignment Anda atau sudah tidak tersedia. Jalankan /report kembali."
            )
            return
        report = open_report_draft(
            db=db,
            user=user,
            task=task,
            telegram_message_id=str(query.id) if getattr(query, "id", None) else None,
        )
        context.user_data["selected_task_id"] = task_id
        context.user_data["active_report_id"] = report.id
        requirements = list(task.requirements) if task else []
        checklist_template = "\n".join(
            f"{item.code}: ya/tidak - {item.title}"
            f"{' (wajib)' if item.is_mandatory else ' (opsional)'}"
            for item in requirements
        )
        specification = task.specification
        control = task.control
        target_line = (
            f"Target volume: {control.planned_quantity:g} {control.unit or 'unit'}\n"
            f"Progress awal: {control.actual_quantity:g}/{control.planned_quantity:g} {control.unit or 'unit'}"
            if control and control.planned_quantity is not None
            else "Target volume: belum ditetapkan di detail task"
        )
        material_lines = "\n".join(
            f"- {item.material_name}"
            f"{f' ({item.planned_quantity:g} {item.unit or "unit"})' if item.planned_quantity is not None else ''}"
            for item in list(task.materials)[:5]
        )
        required_photos = specification.required_photo_count if specification else 0
        required_documents = specification.required_document_count if specification else 0
        planned_people = control.planned_manpower if control and control.planned_manpower is not None else 0
        prompt = (
            f"Draft laporan #{report.id} dibuka dari detail task.\n\n"
            "Sesi bukti baru aktif; foto/dokumen dari laporan sebelumnya tidak ikut dihitung.\n\n"
            f"Project: {task.project.project_name}\n"
            f"WBS: {specification.wbs_code if specification else '-'}\n"
            f"Task: {task.title}\n"
            f"Divisi: {task.division.division_name if task.division else '-'}\n"
            f"Work package: {specification.work_package if specification else '-'}\n"
            f"Lokasi: {(specification.location if specification else None) or (control.location if control else None) or '-'}\n"
            f"{target_line}\n"
            f"Acceptance criteria: {specification.acceptance_criteria if specification else '-'}\n"
            f"Instruksi laporan: {(specification.reporting_instructions if specification else None) or '-'}\n"
            f"Bukti wajib: {required_photos} foto, {required_documents} dokumen\n"
            f"Material utama:\n{material_lines or '- Belum ada material terdaftar'}\n\n"
            "Kirim laporan berdasarkan target di atas:\n"
            "Cuaca: cerah/hujan\n"
            f"Pekerja: {planned_people}\n"
            "Progress: uraikan volume aktual dan hasil pekerjaan\n"
            "Kendala: tidak ada / jelaskan kendala\n"
            f"{checklist_template}\n\n"
            "Setelah isi laporan tersimpan, kirim foto/dokumen lalu /submit."
        )
        db.close()
        await query.edit_message_text(prompt)


# ─── App builder ────────────────────────────────────────────────
def create_bot_app() -> Application:
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("help",    help_command))
    app.add_handler(CommandHandler("tasks",   my_tasks))
    app.add_handler(CommandHandler("status",  project_status))
    app.add_handler(CommandHandler("laporan", laporan_guide))
    app.add_handler(CommandHandler("report",  report_interactive))
    app.add_handler(CommandHandler("submit",  submit_report_command))
    app.add_handler(CommandHandler("summary", weekly_summary))
    app.add_handler(CommandHandler("ai",      ai_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_structured_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    return app


async def run_bot_polling():
    import asyncio
    bot_app = create_bot_app()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    logger.info("✅ Telegram bot started (polling)")
