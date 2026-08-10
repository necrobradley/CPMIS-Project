from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.database import get_db
from app.models.user import FeatureFlag, Tenant, TenantFeatureEntitlement, User, UserRole
from app.schemas.schemas import (
    CommercialEntitlementResponse,
    CommercialEntitlementUpdate,
    CommercialPlanResponse,
    CommercialReadinessResponse,
    CommercialTenantCreate,
    CommercialTenantResponse,
    CommercialTenantUpdate,
    CommercialUsageResponse,
    FeatureFlagResponse,
    FeatureFlagUpdate,
)
from app.services.audit_service import log_audit
from app.services.commercial import (
    USAGE_METRICS,
    apply_plan_limits,
    bootstrap_entitlements_for_tenant,
    commercial_readiness,
    serialize_plan,
    sync_usage_records,
    unique_slug,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/features", response_model=List[FeatureFlagResponse])
def list_feature_flags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(FeatureFlag).order_by(
        FeatureFlag.category.asc(),
        FeatureFlag.label.asc(),
    ).all()


@router.patch("/features/{feature_key}", response_model=FeatureFlagResponse)
def update_feature_flag(
    feature_key: str,
    data: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    flag = db.query(FeatureFlag).filter(FeatureFlag.feature_key == feature_key).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag tidak ditemukan")
    if flag.is_core and not data.enabled:
        raise HTTPException(status_code=409, detail="Core feature tidak boleh dinonaktifkan")

    before = {"enabled": flag.enabled}
    flag.enabled = data.enabled
    flag.updated_by = current_user.id
    flag.updated_at = datetime.utcnow()
    log_audit(
        db,
        actor_id=current_user.id,
        action="settings.feature_updated",
        entity_type="feature_flag",
        entity_id=flag.feature_key,
        project_id=None,
        summary=f"Feature flag {flag.label} diubah menjadi {'aktif' if flag.enabled else 'nonaktif'}",
        before=before,
        after={"enabled": flag.enabled},
    )
    db.commit()
    db.refresh(flag)
    return flag


@router.get("/commercial/plans", response_model=List[CommercialPlanResponse])
def list_commercial_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [
        serialize_plan("starter"),
        serialize_plan("professional"),
        serialize_plan("enterprise"),
    ]


@router.get("/commercial/readiness", response_model=CommercialReadinessResponse)
def get_commercial_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return commercial_readiness(db)


@router.get("/commercial/tenants", response_model=List[CommercialTenantResponse])
def list_commercial_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.post("/commercial/tenants", response_model=CommercialTenantResponse)
def create_commercial_tenant(
    data: CommercialTenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    tenant = Tenant(
        name=data.name,
        slug=unique_slug(db, data.name, data.slug),
        status=data.status,
        plan_key=data.plan_key,
        contact_name=data.contact_name,
        contact_email=str(data.contact_email) if data.contact_email else None,
        contact_phone=data.contact_phone,
        billing_contact_email=str(data.billing_contact_email) if data.billing_contact_email else None,
        trial_ends_at=data.trial_ends_at,
        subscription_starts_at=data.subscription_starts_at,
        subscription_ends_at=data.subscription_ends_at,
        onboarding_stage=data.onboarding_stage,
        notes=data.notes,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    apply_plan_limits(tenant)
    db.add(tenant)
    db.flush()
    bootstrap_entitlements_for_tenant(db, tenant, current_user.id)
    sync_usage_records(db, tenant)
    log_audit(
        db,
        actor_id=current_user.id,
        action="commercial.tenant_created",
        entity_type="tenant",
        entity_id=tenant.id,
        summary=f"Tenant komersial {tenant.name} dibuat dengan paket {tenant.plan_key}",
        after={"name": tenant.name, "slug": tenant.slug, "plan_key": tenant.plan_key, "status": tenant.status},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


@router.patch("/commercial/tenants/{tenant_id}", response_model=CommercialTenantResponse)
def update_commercial_tenant(
    tenant_id: int,
    data: CommercialTenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")

    before = {
        "name": tenant.name,
        "status": tenant.status,
        "plan_key": tenant.plan_key,
        "max_users": tenant.max_users,
        "active_project_limit": tenant.active_project_limit,
        "storage_limit_gb": tenant.storage_limit_gb,
        "ai_token_limit_monthly": tenant.ai_token_limit_monthly,
        "automation_run_limit_monthly": tenant.automation_run_limit_monthly,
    }
    payload = data.model_dump(exclude_unset=True)
    if "plan_key" in payload and payload["plan_key"] != tenant.plan_key:
        apply_plan_limits(tenant, payload["plan_key"])

    for field, value in payload.items():
        if field == "plan_key":
            continue
        if field in {"contact_email", "billing_contact_email"} and value is not None:
            value = str(value)
        setattr(tenant, field, value)

    tenant.updated_by = current_user.id
    tenant.updated_at = datetime.utcnow()
    bootstrap_entitlements_for_tenant(db, tenant, current_user.id)
    sync_usage_records(db, tenant)
    log_audit(
        db,
        actor_id=current_user.id,
        action="commercial.tenant_updated",
        entity_type="tenant",
        entity_id=tenant.id,
        summary=f"Tenant komersial {tenant.name} diperbarui",
        before=before,
        after={
            "name": tenant.name,
            "status": tenant.status,
            "plan_key": tenant.plan_key,
            "max_users": tenant.max_users,
            "active_project_limit": tenant.active_project_limit,
            "storage_limit_gb": tenant.storage_limit_gb,
            "ai_token_limit_monthly": tenant.ai_token_limit_monthly,
            "automation_run_limit_monthly": tenant.automation_run_limit_monthly,
        },
    )
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get(
    "/commercial/tenants/{tenant_id}/entitlements",
    response_model=List[CommercialEntitlementResponse],
)
def list_tenant_entitlements(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")

    bootstrap_entitlements_for_tenant(db, tenant, current_user.id)
    db.commit()
    flags = {flag.feature_key: flag for flag in db.query(FeatureFlag).all()}
    entitlements = db.query(TenantFeatureEntitlement).filter(
        TenantFeatureEntitlement.tenant_id == tenant.id
    ).order_by(TenantFeatureEntitlement.feature_key.asc()).all()

    response = []
    for entitlement in entitlements:
        flag = flags.get(entitlement.feature_key)
        response.append({
            "id": entitlement.id,
            "tenant_id": entitlement.tenant_id,
            "feature_key": entitlement.feature_key,
            "label": flag.label if flag else entitlement.feature_key,
            "category": flag.category if flag else "unknown",
            "enabled": entitlement.enabled,
            "is_core": flag.is_core if flag else False,
            "source": entitlement.source,
            "notes": entitlement.notes,
            "updated_by": entitlement.updated_by,
            "created_at": entitlement.created_at,
            "updated_at": entitlement.updated_at,
        })
    return response


@router.patch(
    "/commercial/tenants/{tenant_id}/entitlements/{feature_key}",
    response_model=CommercialEntitlementResponse,
)
def update_tenant_entitlement(
    tenant_id: int,
    feature_key: str,
    data: CommercialEntitlementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    flag = db.query(FeatureFlag).filter(FeatureFlag.feature_key == feature_key).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag tidak ditemukan")
    if flag.is_core and not data.enabled:
        raise HTTPException(status_code=409, detail="Core feature tidak boleh dinonaktifkan")

    bootstrap_entitlements_for_tenant(db, tenant, current_user.id)
    entitlement = db.query(TenantFeatureEntitlement).filter(
        TenantFeatureEntitlement.tenant_id == tenant.id,
        TenantFeatureEntitlement.feature_key == feature_key,
    ).first()
    if not entitlement:
        raise HTTPException(status_code=404, detail="Entitlement tidak ditemukan")

    before = {"enabled": entitlement.enabled, "source": entitlement.source, "notes": entitlement.notes}
    entitlement.enabled = data.enabled
    entitlement.notes = data.notes
    entitlement.source = "manual"
    entitlement.updated_by = current_user.id
    entitlement.updated_at = datetime.utcnow()
    log_audit(
        db,
        actor_id=current_user.id,
        action="commercial.entitlement_updated",
        entity_type="tenant_feature_entitlement",
        entity_id=entitlement.id,
        summary=f"Entitlement {flag.label} untuk tenant {tenant.name} diubah",
        before=before,
        after={"enabled": entitlement.enabled, "source": entitlement.source, "notes": entitlement.notes},
    )
    db.commit()
    db.refresh(entitlement)
    return {
        "id": entitlement.id,
        "tenant_id": entitlement.tenant_id,
        "feature_key": entitlement.feature_key,
        "label": flag.label,
        "category": flag.category,
        "enabled": entitlement.enabled,
        "is_core": flag.is_core,
        "source": entitlement.source,
        "notes": entitlement.notes,
        "updated_by": entitlement.updated_by,
        "created_at": entitlement.created_at,
        "updated_at": entitlement.updated_at,
    }


@router.get("/commercial/tenants/{tenant_id}/usage", response_model=List[CommercialUsageResponse])
def get_tenant_usage(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant tidak ditemukan")
    records = sync_usage_records(db, tenant)
    db.commit()

    response = []
    for record in records:
        config = USAGE_METRICS.get(record.metric_key, {"label": record.metric_key})
        percent_used = None
        if record.limit_value and record.limit_value > 0:
            percent_used = round((record.used_value / record.limit_value) * 100, 2)
        response.append({
            "id": record.id,
            "tenant_id": record.tenant_id,
            "metric_key": record.metric_key,
            "label": config["label"],
            "period": record.period,
            "used_value": record.used_value,
            "limit_value": record.limit_value,
            "unit": record.unit,
            "percent_used": percent_used,
            "updated_at": record.updated_at,
        })
    return response
