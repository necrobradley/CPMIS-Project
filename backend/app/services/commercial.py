import re
from datetime import datetime
from typing import Dict, Iterable, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.db.database import engine
from app.models.user import FeatureFlag, Tenant, TenantFeatureEntitlement, TenantUsageRecord


PLAN_CATALOG = {
    "starter": {
        "name": "Starter Project",
        "positioning": "Pilot dan tim proyek kecil yang mulai merapikan laporan, task, dan dokumen.",
        "monthly_base_price_min_idr": 3_000_000,
        "monthly_base_price_max_idr": 7_000_000,
        "implementation_fee_min_idr": 10_000_000,
        "implementation_fee_max_idr": 50_000_000,
        "included_users": 25,
        "active_project_limit": 2,
        "storage_limit_gb": 50,
        "ai_token_limit_monthly": 100_000,
        "automation_run_limit_monthly": 100,
        "enabled_features": {
            "dashboard", "projects", "project_tree", "tasks", "reports",
            "documents", "users", "audit", "admin_console",
        },
        "recommended_for": [
            "Kontraktor/subkontraktor kecil",
            "Pilot internal 1 proyek",
            "Tim yang baru mulai digitalisasi laporan lapangan",
        ],
    },
    "professional": {
        "name": "Professional Construction",
        "positioning": "Paket utama untuk kontraktor menengah, konsultan pengawas, dan owner proyek kecil-menengah.",
        "monthly_base_price_min_idr": 10_000_000,
        "monthly_base_price_max_idr": 30_000_000,
        "implementation_fee_min_idr": 35_000_000,
        "implementation_fee_max_idr": 100_000_000,
        "included_users": 100,
        "active_project_limit": 10,
        "storage_limit_gb": 500,
        "ai_token_limit_monthly": 1_000_000,
        "automation_run_limit_monthly": 1_000,
        "enabled_features": {
            "dashboard", "projects", "project_tree", "tasks", "controls",
            "risk", "communications", "approvals", "reports", "documents",
            "compliance", "automation", "stakeholders", "telegram", "audit",
            "ai_chat", "subcontractor", "users", "admin_console",
        },
        "recommended_for": [
            "Kontraktor menengah dengan 3-10 proyek aktif",
            "Konsultan pengawas yang butuh RFI/submittal/NCR",
            "Owner proyek yang butuh dashboard dan approval",
        ],
    },
    "enterprise": {
        "name": "Enterprise Control",
        "positioning": "Multi-project organization dengan kebutuhan SLA, integrasi, audit lanjutan, dan deployment khusus.",
        "monthly_base_price_min_idr": None,
        "monthly_base_price_max_idr": None,
        "implementation_fee_min_idr": 100_000_000,
        "implementation_fee_max_idr": 300_000_000,
        "included_users": None,
        "active_project_limit": None,
        "storage_limit_gb": None,
        "ai_token_limit_monthly": None,
        "automation_run_limit_monthly": None,
        "enabled_features": "all",
        "recommended_for": [
            "Owner/developer multi-proyek",
            "Kontraktor besar",
            "Customer yang membutuhkan SSO, API, SLA, dan private deployment",
        ],
    },
}


USAGE_METRICS = {
    "active_users": {"label": "Active users", "unit": "user", "limit_field": "max_users"},
    "active_projects": {"label": "Active projects", "unit": "project", "limit_field": "active_project_limit"},
    "storage_gb": {"label": "Storage", "unit": "GB", "limit_field": "storage_limit_gb"},
    "ai_tokens": {"label": "AI tokens", "unit": "token", "limit_field": "ai_token_limit_monthly"},
    "automation_runs": {"label": "Automation runs", "unit": "run", "limit_field": "automation_run_limit_monthly"},
}


def current_usage_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def normalize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "tenant"


def unique_slug(db: Session, name: str, requested_slug: Optional[str] = None) -> str:
    base_slug = normalize_slug(requested_slug or name)
    slug = base_slug
    suffix = 2
    while db.query(Tenant).filter(Tenant.slug == slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def get_plan(plan_key: str) -> Dict:
    return PLAN_CATALOG.get(plan_key, PLAN_CATALOG["professional"])


def plan_feature_enabled(plan_key: str, feature_key: str, is_core: bool = False) -> bool:
    if is_core:
        return True
    enabled_features = get_plan(plan_key)["enabled_features"]
    return enabled_features == "all" or feature_key in enabled_features


def apply_plan_limits(tenant: Tenant, plan_key: Optional[str] = None) -> None:
    plan = get_plan(plan_key or tenant.plan_key)
    tenant.plan_key = plan_key or tenant.plan_key
    tenant.max_users = plan["included_users"]
    tenant.active_project_limit = plan["active_project_limit"]
    tenant.storage_limit_gb = plan["storage_limit_gb"]
    tenant.ai_token_limit_monthly = plan["ai_token_limit_monthly"]
    tenant.automation_run_limit_monthly = plan["automation_run_limit_monthly"]


def bootstrap_entitlements_for_tenant(db: Session, tenant: Tenant, updated_by: Optional[int] = None) -> None:
    flags = db.query(FeatureFlag).order_by(FeatureFlag.category.asc(), FeatureFlag.label.asc()).all()
    existing = {
        entitlement.feature_key: entitlement
        for entitlement in db.query(TenantFeatureEntitlement)
        .filter(TenantFeatureEntitlement.tenant_id == tenant.id)
        .all()
    }

    for flag in flags:
        entitlement = existing.get(flag.feature_key)
        default_enabled = plan_feature_enabled(tenant.plan_key, flag.feature_key, flag.is_core)
        if entitlement:
            if entitlement.source == "plan":
                entitlement.enabled = default_enabled
                entitlement.updated_by = updated_by
            continue
        db.add(TenantFeatureEntitlement(
            tenant_id=tenant.id,
            feature_key=flag.feature_key,
            enabled=default_enabled,
            source="plan",
            updated_by=updated_by,
        ))


def sync_usage_records(db: Session, tenant: Tenant, period: Optional[str] = None) -> Iterable[TenantUsageRecord]:
    usage_period = period or current_usage_period()
    existing = {
        record.metric_key: record
        for record in db.query(TenantUsageRecord)
        .filter(TenantUsageRecord.tenant_id == tenant.id, TenantUsageRecord.period == usage_period)
        .all()
    }

    records = []
    for metric_key, config in USAGE_METRICS.items():
        limit_value = getattr(tenant, config["limit_field"], None)
        record = existing.get(metric_key)
        if not record:
            record = TenantUsageRecord(
                tenant_id=tenant.id,
                metric_key=metric_key,
                period=usage_period,
                used_value=0,
                limit_value=limit_value,
                unit=config["unit"],
            )
            db.add(record)
        else:
            record.limit_value = limit_value
            record.unit = config["unit"]
        records.append(record)
    return records


def serialize_plan(plan_key: str) -> Dict:
    plan = get_plan(plan_key)
    return {
        "plan_key": plan_key,
        "name": plan["name"],
        "positioning": plan["positioning"],
        "monthly_base_price_min_idr": plan["monthly_base_price_min_idr"],
        "monthly_base_price_max_idr": plan["monthly_base_price_max_idr"],
        "implementation_fee_min_idr": plan["implementation_fee_min_idr"],
        "implementation_fee_max_idr": plan["implementation_fee_max_idr"],
        "included_users": plan["included_users"],
        "active_project_limit": plan["active_project_limit"],
        "storage_limit_gb": plan["storage_limit_gb"],
        "ai_token_limit_monthly": plan["ai_token_limit_monthly"],
        "automation_run_limit_monthly": plan["automation_run_limit_monthly"],
        "enabled_features": sorted(plan["enabled_features"]) if plan["enabled_features"] != "all" else ["all"],
        "recommended_for": plan["recommended_for"],
    }


def commercial_readiness(db: Session) -> Dict:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    commercial_tables = {"tenants", "tenant_feature_entitlements", "tenant_usage_records"}
    tenant_columns = [
        (table_name, column["name"])
        for table_name in tables
        for column in inspector.get_columns(table_name)
        if column["name"] == "tenant_id" and table_name not in commercial_tables
    ]
    tenant_count = db.query(Tenant).count() if "tenants" in tables else 0
    entitlement_count = (
        db.query(TenantFeatureEntitlement).count()
        if "tenant_feature_entitlements" in tables
        else 0
    )

    checks = [
        {
            "key": "commercial_plan_catalog",
            "title": "Paket komersial",
            "status": "done",
            "detail": "Starter, Professional, dan Enterprise sudah tersedia sebagai katalog paket.",
            "action": "Validasi harga dengan 3-5 calon pelanggan.",
        },
        {
            "key": "control_plane",
            "title": "Control Plane tenant",
            "status": "partial" if tenant_count == 0 else "done",
            "detail": f"Model tenant tersedia; tenant terdaftar saat ini: {tenant_count}.",
            "action": "Buat tenant pilot pertama dari Admin Console.",
        },
        {
            "key": "feature_entitlement",
            "title": "Entitlement fitur",
            "status": "partial" if entitlement_count == 0 else "done",
            "detail": f"Entitlement per tenant tersedia; rule tersimpan saat ini: {entitlement_count}.",
            "action": "Hubungkan entitlement ke middleware backend sebelum SaaS publik.",
        },
        {
            "key": "usage_metering",
            "title": "Usage metering",
            "status": "partial",
            "detail": "Limit user, project, storage, AI, dan automation sudah dimodelkan; event metering belum terhubung ke seluruh workflow.",
            "action": "Tambahkan pencatatan usage pada upload, AI call, automation run, dan provisioning user.",
        },
        {
            "key": "tenant_isolation",
            "title": "Tenant isolation",
            "status": "todo" if len(tenant_columns) == 0 else "partial",
            "detail": f"Kolom tenant_id terdeteksi pada {len(tenant_columns)} tabel. Enforcement lintas endpoint belum boleh dianggap selesai.",
            "action": "Migrasikan semua tabel operasional ke tenant_id dan tambahkan test kebocoran lintas tenant.",
        },
        {
            "key": "production_operations",
            "title": "Production operations",
            "status": "todo",
            "detail": "Backup otomatis, monitoring production, incident SOP, dan legal pack belum menjadi fitur/runtime teruji.",
            "action": "Siapkan staging, backup/restore drill, monitoring, privacy policy, terms, dan SLA support.",
        },
    ]

    return {
        "summary": {
            "plans": len(PLAN_CATALOG),
            "tenants": tenant_count,
            "entitlement_rules": entitlement_count,
            "tenant_id_columns": len(tenant_columns),
        },
        "checks": checks,
    }
