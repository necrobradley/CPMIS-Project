"""
System readiness endpoint for dashboards and external monitors.
"""
from fastapi import APIRouter
import httpx

from app.core.config import settings
from app.services.ai_service import AIService

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/status")
def system_status():
    """Public operational status used by the realtime frontend panels."""
    try:
        n8n_online = httpx.get("http://n8n:5678/healthz", timeout=1.5).status_code == 200
    except Exception:
        n8n_online = False
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "services": {
            "api": True,
            "database": True,
            "scheduler": True,
            "telegram": settings.TELEGRAM_BOT_ENABLED and bool(settings.TELEGRAM_BOT_TOKEN),
            "n8n": n8n_online,
            "ai": AIService.is_configured(),
            "rag": settings.RAG_ENABLED,
            "ai_safety": settings.AI_SAFETY_ENABLED,
            "ai_gateway": settings.AI_GATEWAY_ENABLED,
            "ai_gateway_policy": settings.AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY,
            "ai_local": AIService.local_status(),
        },
        "workflows": [
            {
                "id": "daily-report",
                "name": "Daily report validation and notification",
                "schedule": "Realtime webhook",
                "status": "ready" if n8n_online else "offline",
            },
            {
                "id": "tender-analysis",
                "name": "Tender analysis and task generation",
                "schedule": "On document upload",
                "status": "ready" if n8n_online else "offline",
            },
            {
                "id": "deadline-alert",
                "name": "Deadline reminder",
                "schedule": "Daily 08:00 WIB",
                "status": "ready" if n8n_online else "offline",
            },
            {
                "id": "approval-routing",
                "name": "Approval routing and escalation",
                "schedule": "On approval request",
                "status": "backend-only",
            },
            {
                "id": "weekly-summary",
                "name": "Weekly executive summary",
                "schedule": "Friday 17:00 WIB",
                "status": "ready" if n8n_online else "offline",
            },
        ],
    }
