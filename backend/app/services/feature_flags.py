from sqlalchemy.orm import Session

from app.models.user import FeatureFlag


DEFAULT_FEATURE_FLAGS = [
    {
        "feature_key": "dashboard",
        "label": "Dashboard",
        "category": "core",
        "description": "Ringkasan operasional utama.",
        "enabled": True,
        "is_core": True,
    },
    {
        "feature_key": "projects",
        "label": "Proyek",
        "category": "project",
        "description": "Daftar dan detail proyek.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "project_tree",
        "label": "Tree View",
        "category": "project",
        "description": "Struktur proyek, WBS, task, dan dokumen.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "tasks",
        "label": "Tasks",
        "category": "execution",
        "description": "Task lapangan, assignment, status, dan detail pekerjaan.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "controls",
        "label": "Project Controls",
        "category": "execution",
        "description": "Lookahead, QA/QC, progress, cost, dan handover controls.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "risk",
        "label": "Risk Intelligence",
        "category": "management",
        "description": "Risiko keterlambatan, blocker, overdue, dan critical task.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "communications",
        "label": "Communication Hub",
        "category": "communication",
        "description": "RFI, issue, escalation, thread, mention, dan attachment komunikasi.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "approvals",
        "label": "Approvals",
        "category": "communication",
        "description": "Permintaan dan keputusan approval.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "reports",
        "label": "Laporan Harian",
        "category": "execution",
        "description": "Laporan staff, evidence, validasi, review, dan approval.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "documents",
        "label": "Dokumen",
        "category": "document",
        "description": "Document control, QA dokumen, dan sinkronisasi dokumen.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "compliance",
        "label": "Compliance AI",
        "category": "advanced",
        "description": "Analisis compliance berbasis dokumen dan deliverable.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "automation",
        "label": "n8n Automation",
        "category": "integration",
        "description": "Monitoring workflow automation.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "stakeholders",
        "label": "Stakeholders",
        "category": "communication",
        "description": "Stakeholder, kontak, dan channel koordinasi.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "telegram",
        "label": "Telegram Center",
        "category": "integration",
        "description": "Monitoring kesiapan Telegram dan event notifikasi.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "audit",
        "label": "Audit Trail",
        "category": "governance",
        "description": "Jejak perubahan untuk integritas komunikasi dan data.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "research",
        "label": "Research Export",
        "category": "governance",
        "description": "Export dataset riset/tesis.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "ai_chat",
        "label": "AI Assistant",
        "category": "advanced",
        "description": "Chat AI berbasis konteks proyek dan dokumen.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "subcontractor",
        "label": "Portal Subkon",
        "category": "execution",
        "description": "Portal khusus subcontractor.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "users",
        "label": "Pengguna",
        "category": "admin",
        "description": "Manajemen user, role, dan kontak.",
        "enabled": True,
        "is_core": False,
    },
    {
        "feature_key": "admin_console",
        "label": "Admin Console",
        "category": "admin",
        "description": "Kontrol fitur menu dan governance sistem.",
        "enabled": True,
        "is_core": True,
    },
]


def bootstrap_feature_flags(db: Session) -> None:
    existing = {
        item.feature_key: item
        for item in db.query(FeatureFlag).all()
    }
    for config in DEFAULT_FEATURE_FLAGS:
        item = existing.get(config["feature_key"])
        if item:
            item.label = config["label"]
            item.category = config["category"]
            item.description = config["description"]
            item.is_core = config["is_core"]
            continue
        db.add(FeatureFlag(**config))
    db.commit()
