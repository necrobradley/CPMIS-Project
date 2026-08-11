from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, projects, tasks, reports,
    ai, n8n_webhooks, documents, notifications, compliance, system,
    approvals, audit, research, communications, controls, settings, digital_twin
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(reports.router)
api_router.include_router(ai.router)
api_router.include_router(n8n_webhooks.router)
api_router.include_router(documents.router)
api_router.include_router(notifications.router)
api_router.include_router(compliance.router)
api_router.include_router(system.router)
api_router.include_router(approvals.router)
api_router.include_router(audit.router)
api_router.include_router(research.router)
api_router.include_router(communications.router)
api_router.include_router(controls.router)
api_router.include_router(settings.router)
api_router.include_router(digital_twin.router)
