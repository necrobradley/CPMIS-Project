"""
Background Scheduler - AI CPMIS
Cron jobs: deadline alerts harian, weekly summary Jumat.
Dijalankan saat startup FastAPI.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.models.user import User, Task, Project, TaskStatus
from app.services.communication_service import run_sla_escalations
from app.services.n8n_service import n8n_service
from app.services.reminder_automation import prepare_task_reminders

logger = logging.getLogger(__name__)


async def check_deadlines():
    """Cek task yang mendekati deadline atau overdue → trigger N8N."""
    db = SessionLocal()
    try:
        result = prepare_task_reminders(db, horizon_days=3, include_stalled=True)
        logger.info(
            "Task reminders prepared: %s notifications created, %s telegram payload(s)",
            result["summary"]["notifications_created"],
            result["summary"]["telegram_messages"],
        )
        escalated = run_sla_escalations(db)
        if escalated:
            logger.info("Communication SLA auto-escalated for %s item(s)", escalated)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"check_deadlines error: {e}")
    finally:
        db.close()


async def send_weekly_summary():
    """Kirim ringkasan mingguan ke director/owner → trigger N8N."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        projects = db.query(Project).filter(Project.status == "active").all()
        directors = db.query(User).filter(
            User.role.in_(["director", "admin"]),
            User.telegram_id != None,
        ).all()
        director_tg_ids = [d.telegram_id for d in directors if d.telegram_id]

        for project in projects:
            done_tasks  = db.query(Task).filter(Task.project_id == project.id, Task.status == TaskStatus.DONE).count()
            total_tasks = db.query(Task).filter(Task.project_id == project.id).count()
            overdue     = db.query(Task).filter(
                Task.project_id == project.id,
                Task.deadline < now,
                Task.status != TaskStatus.DONE,
            ).count()

            from app.models.user import DailyReport
            reports_this_week = db.query(DailyReport).filter(
                DailyReport.project_id == project.id,
                DailyReport.report_date >= week_ago,
            ).count()

            await n8n_service.trigger_weekly_summary(
                project_id=project.id,
                project_name=project.project_name,
                week_stats={
                    "total_tasks": total_tasks,
                    "completed_tasks": done_tasks,
                    "overdue_tasks": overdue,
                    "reports_submitted": reports_this_week,
                    "progress_percent": project.progress_percent,
                },
                director_telegram_ids=director_tg_ids,
            )

    except Exception as e:
        logger.error(f"send_weekly_summary error: {e}")
    finally:
        db.close()


async def run_scheduler():
    """Main scheduler loop — cek deadline tiap hari jam 08:00, weekly summary tiap Jumat 17:00."""
    logger.info("⏰ Background scheduler started")
    while True:
        try:
            now = datetime.utcnow()
            # Jakarta = UTC+7
            local_hour    = (now.hour + 7) % 24
            local_weekday = now.weekday()  # 4 = Jumat

            # Deadline alert harian jam 08:00 WIB
            if local_hour == 1:  # 01:00 UTC = 08:00 WIB
                logger.info("⏰ Running daily deadline check...")
                await check_deadlines()

            # Weekly summary Jumat 17:00 WIB
            if local_weekday == 4 and local_hour == 10:  # 10:00 UTC = 17:00 WIB
                logger.info("⏰ Running weekly summary...")
                await send_weekly_summary()

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        # Cek setiap jam
        await asyncio.sleep(3600)
