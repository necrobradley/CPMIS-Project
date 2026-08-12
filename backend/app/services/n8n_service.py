"""
N8N Webhook Service - AI CPMIS
Menerima event dari N8N dan memicunya ke backend.
"""
import httpx
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class N8NService:
    """
    Mengirim event ke N8N Webhook.
    N8N bertindak sebagai orchestrator alur otomasi.
    """

    def __init__(self):
        self.base_url = settings.N8N_WEBHOOK_URL
        self.timeout = 10.0

    async def trigger(self, workflow: str, payload: dict) -> bool:
        """
        Kirim payload ke N8N webhook URL.
        workflow: nama workflow (daily_report, tender_analysis, dll)
        """
        url = f"{self.base_url}/{workflow}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.info(f"N8N trigger '{workflow}' sukses: {resp.status_code}")
                return True
        except httpx.ConnectError:
            logger.warning(f"N8N tidak dapat dihubungi ({url}). Lanjutkan tanpa N8N.")
            return False
        except Exception as e:
            logger.error(f"N8N trigger '{workflow}' gagal: {e}")
            return False

    # ─── Workflow 1: Daily Report ────────────────────────────────
    async def trigger_daily_report(
        self,
        report_id: int,
        project_id: int,
        project_name: str,
        reporter_name: str,
        reporter_telegram_id: Optional[str],
        manager_telegram_ids: list[str],
        report_text: str,
        ai_summary: Optional[str],
        ai_risks: Optional[str],
        severity: str = "low",
    ) -> bool:
        """
        Workflow 1 — Daily Report Flow:
        Telegram Upload → N8N Trigger → Save DB → AI Analysis
        → Generate Summary → Send to Manager
        """
        payload = {
            "event":               "daily_report_submitted",
            "report_id":           report_id,
            "project_id":          project_id,
            "project_name":        project_name,
            "reporter_name":       reporter_name,
            "reporter_telegram_id": reporter_telegram_id,
            "manager_telegram_ids": manager_telegram_ids,
            "report_text":         report_text,
            "ai_summary":          ai_summary,
            "ai_risks":            ai_risks,
            "severity":            severity,
            # N8N akan routing berdasarkan severity:
            # high/critical → langsung kirim ke manager
            # low/medium    → batch ke summary harian
        }
        return await self.trigger("daily-report", payload)

    # ─── Workflow 2: Tender Analysis ────────────────────────────
    async def trigger_tender_analysis(
        self,
        document_id: int,
        project_id: int,
        project_name: str,
        file_name: str,
        uploader_name: str,
        analysis_result: dict,
        generated_tasks_count: int,
        manager_telegram_ids: list[str],
    ) -> bool:
        """
        Workflow 2 — Tender Analysis Flow:
        Upload PDF → OCR → AI NLP Analysis
        → Task Extraction → Assign Divisions → Send Notifications
        """
        payload = {
            "event":                "tender_analyzed",
            "document_id":         document_id,
            "project_id":          project_id,
            "project_name":        project_name,
            "file_name":           file_name,
            "uploader_name":       uploader_name,
            "scope_of_work":       analysis_result.get("scope_of_work", []),
            "milestones":          analysis_result.get("milestones", []),
            "risks":               analysis_result.get("risks", []),
            "divisions_needed":    analysis_result.get("divisions_needed", []),
            "generated_tasks":     generated_tasks_count,
            "contract_value":      analysis_result.get("contract_value"),
            "start_date":          analysis_result.get("start_date"),
            "end_date":            analysis_result.get("end_date"),
            "manager_telegram_ids": manager_telegram_ids,
        }
        return await self.trigger("tender-analysis", payload)

    # ─── Workflow 3: Task Deadline Alert ────────────────────────
    async def trigger_deadline_alert(
        self,
        task_id: int,
        task_title: str,
        project_name: str,
        assignee_name: str,
        assignee_telegram_id: Optional[str],
        deadline: str,
        days_remaining: int,
    ) -> bool:
        """
        Workflow 3 — Deadline Reminder:
        Scheduler → N8N → Cek overdue tasks → Kirim notif Telegram
        """
        payload = {
            "event":                "task_deadline_alert",
            "task_id":             task_id,
            "task_title":          task_title,
            "project_name":        project_name,
            "assignee_name":       assignee_name,
            "assignee_telegram_id": assignee_telegram_id,
            "deadline":            deadline,
            "days_remaining":      days_remaining,
            "urgency":             "critical" if days_remaining <= 1 else "high" if days_remaining <= 3 else "medium",
        }
        return await self.trigger("deadline-alert", payload)

    async def trigger_approval_request(
        self,
        approval_id: int,
        project_id: int,
        title: str,
        approval_type: str,
        requester_name: str,
        approver_telegram_id: Optional[str],
        due_date: Optional[str],
    ) -> bool:
        """Trigger N8N approval routing workflow."""
        payload = {
            "event": "approval_requested",
            "approval_id": approval_id,
            "project_id": project_id,
            "title": title,
            "approval_type": approval_type,
            "requester_name": requester_name,
            "approver_telegram_id": approver_telegram_id,
            "due_date": due_date,
        }
        return await self.trigger("approval-request", payload)

    # ─── Workflow 4: User Registration ──────────────────────────
    async def trigger_user_registered(
        self,
        user_id: int,
        user_name: str,
        user_email: str,
        role: str,
        admin_telegram_ids: list[str],
    ) -> bool:
        """
        Workflow 4 — New User:
        Register → N8N → Kirim welcome email + notif admin
        """
        payload = {
            "event":              "user_registered",
            "user_id":            user_id,
            "user_name":          user_name,
            "user_email":         user_email,
            "role":               role,
            "admin_telegram_ids": admin_telegram_ids,
        }
        return await self.trigger("user-registered", payload)

    # ─── Workflow 5: Weekly Summary ─────────────────────────────
    async def trigger_weekly_summary(
        self,
        project_id: int,
        project_name: str,
        week_stats: dict,
        director_telegram_ids: list[str],
    ) -> bool:
        """
        Workflow 5 — Weekly Report:
        N8N Cron (setiap Jumat 17:00) → Kumpul data → AI summary
        → Kirim ke Director/Owner
        """
        payload = {
            "event":                  "weekly_summary",
            "project_id":             project_id,
            "project_name":           project_name,
            "total_tasks":            week_stats.get("total_tasks", 0),
            "completed_tasks":        week_stats.get("completed_tasks", 0),
            "overdue_tasks":          week_stats.get("overdue_tasks", 0),
            "reports_submitted":      week_stats.get("reports_submitted", 0),
            "progress_percent":       week_stats.get("progress_percent", 0),
            "director_telegram_ids":  director_telegram_ids,
        }
        return await self.trigger("weekly-summary", payload)


# Singleton instance
n8n_service = N8NService()
