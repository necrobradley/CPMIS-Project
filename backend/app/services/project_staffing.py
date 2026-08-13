"""Project roster and deterministic assignment helpers for demo and AI tasks."""
from __future__ import annotations

import secrets
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import (
    ApprovalStatus,
    Division,
    Project,
    ProjectMembership,
    ProjectRolePolicy,
    Task,
    TaskPriority,
    TaskRequirement,
    TaskSpecification,
    TaskStatus,
    User,
    UserRole,
)
from app.services.project_role_catalog import (
    PROJECT_ROLE_BY_CODE,
    PROJECT_ROLE_CATALOG,
    role_can_be_task_pic,
)


PREFERRED_DEMO_IDENTITIES = {
    "project_sponsor": ("director", "Direktur Proyek", UserRole.DIRECTOR),
    "project_manager": ("manager", "Manajer Proyek", UserRole.MANAGER),
    "site_engineer": ("staff", "Staf Lapangan", UserRole.STAFF),
    "subcontractor": ("subcontractor", "Staf Subkontraktor", UserRole.SUBCONTRACTOR),
}

DEMO_EMAIL_KEYS = {
    # ``staff`` is already the stable legacy login for the Site Engineer demo account.
    "staff": "project_staff",
}

MANAGEMENT_PROJECT_ROLES = {
    "project_manager",
    "deputy_pm",
    "construction_manager",
    "site_manager",
    "division_lead",
    "qa_qc_manager",
    "hse_manager",
    "contract_manager",
    "finance_manager",
    "procurement_manager",
}

EXECUTIVE_PROJECT_ROLES = {"project_sponsor", "owner_rep", "client_stakeholder"}
EXTERNAL_PROJECT_ROLES = {"subcontractor", "vendor", "consultant", "authority_reviewer"}


def global_role_for_project_role(project_role: str) -> UserRole:
    if project_role in EXECUTIVE_PROJECT_ROLES:
        return UserRole.DIRECTOR
    if project_role in MANAGEMENT_PROJECT_ROLES or project_role == "project_admin":
        return UserRole.MANAGER
    if project_role in EXTERNAL_PROJECT_ROLES:
        return UserRole.SUBCONTRACTOR
    return UserRole.STAFF


def _upsert_division(
    db: Session,
    project: Project,
    name: str,
    manager_id: int,
) -> Division:
    division = db.query(Division).filter(
        Division.project_id == project.id,
        Division.division_name == name,
    ).first()
    if not division:
        division = Division(project_id=project.id, division_name=name)
        db.add(division)
    division.description = f"Divisi demo untuk fungsi {name}."
    division.manager_id = manager_id
    db.flush()
    return division


def _upsert_membership(
    db: Session,
    project: Project,
    user: User,
    division: Division,
    project_role: str,
) -> ProjectMembership:
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project.id,
        ProjectMembership.user_id == user.id,
    ).first()
    if not membership:
        membership = ProjectMembership(project_id=project.id, user_id=user.id)
        db.add(membership)
    membership.division_id = division.id
    membership.project_role = project_role
    membership.is_active = True
    user.division_id = division.id
    db.flush()
    return membership


def upsert_full_project_roster(
    db: Session,
    *,
    project: Project,
    project_slug: str,
    owner: User,
    initial_password: str,
) -> tuple[dict[str, User], dict[str, User], list[dict]]:
    """Create one login account for every project role, idempotently."""
    legacy_users: dict[str, User] = {}
    users_by_project_role: dict[str, User] = {}
    generated_accounts: list[dict] = []

    for role in PROJECT_ROLE_CATALOG:
        project_role = role["code"]
        preferred = PREFERRED_DEMO_IDENTITIES.get(project_role)
        if preferred:
            key, short_label, global_role = preferred
        else:
            key = DEMO_EMAIL_KEYS.get(project_role, project_role)
            short_label = role["label"]
            global_role = global_role_for_project_role(project_role)

        email = f"{key}.{project_slug}@cpmis.example.com"
        user = db.query(User).filter(User.email == email).first()
        created = user is None
        temporary_password = None
        if not user:
            temporary_password = initial_password or secrets.token_urlsafe(12)
            user = User(
                name=f"{short_label} - {project.project_name}"[:100],
                email=email,
                password_hash=get_password_hash(temporary_password),
                role=global_role,
                is_active=True,
            )
            db.add(user)
            db.flush()
        elif initial_password:
            user.password_hash = get_password_hash(initial_password)

        user.name = f"{short_label} - {project.project_name}"[:100]
        user.role = global_role
        user.is_active = True
        division_name = role.get("default_division") or role.get("category_label") or "Project Team"
        division = _upsert_division(db, project, str(division_name)[:100], owner.id)
        _upsert_membership(db, project, user, division, project_role)

        users_by_project_role[project_role] = user
        if preferred:
            legacy_users[key] = user
        generated_accounts.append({
            "name": user.name,
            "email": user.email,
            "role": global_role.value,
            "project_role": project_role,
            "project_role_label": role["label"],
            "can_be_task_pic": bool(role.get("can_be_task_pic")),
            "created": created,
            "temporary_password": temporary_password,
        })

    return legacy_users, users_by_project_role, generated_accounts


def seed_ai_role_coverage_tasks(
    db: Session,
    *,
    project: Project,
    owner: User,
    users_by_project_role: dict[str, User],
    data_date: datetime | None = None,
) -> tuple[int, dict[str, int]]:
    """Seed one clearly assigned demo-AI task for every role eligible as PIC."""
    base_date = data_date or datetime.utcnow()
    assignment_counts: Counter[str] = Counter()
    task_count = 0

    for sequence, role in enumerate(
        (item for item in PROJECT_ROLE_CATALOG if item.get("can_be_task_pic")),
        start=1,
    ):
        project_role = role["code"]
        user = users_by_project_role[project_role]
        membership = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == project.id,
            ProjectMembership.user_id == user.id,
            ProjectMembership.project_role == project_role,
            ProjectMembership.is_active == True,
        ).first()
        if not membership:
            division_name = role.get("default_division") or role.get("category_label") or "Project Team"
            division = _upsert_division(db, project, str(division_name)[:100], owner.id)
            membership = _upsert_membership(db, project, user, division, project_role)
        wbs_code = f"AI-ROLE-{sequence:02d}"
        task = db.query(Task).join(TaskSpecification).filter(
            Task.project_id == project.id,
            TaskSpecification.wbs_code == wbs_code,
        ).first()
        if not task:
            task = Task(
                title=f"AI Demo - {role['label']}",
                project_id=project.id,
                created_by=owner.id,
            )
            db.add(task)
            db.flush()
            task.specification = TaskSpecification(wbs_code=wbs_code)

        task.title = f"AI Demo - {role['label']}"
        task.description = (
            f"Task dummy untuk memperlihatkan pembagian pekerjaan kepada {role['label']}. "
            f"Tanggung jawab: {role['responsibility']}"
        )
        task.division_id = membership.division_id
        task.assigned_to = user.id
        task.created_by = owner.id
        task.priority = (
            TaskPriority.HIGH
            if role["category"] in {"management", "quality_safety"}
            else TaskPriority.MEDIUM
        )
        task.status = TaskStatus.IN_PROGRESS if sequence % 4 == 0 else TaskStatus.TODO
        task.deadline = base_date + timedelta(days=14 + sequence)
        task.progress_percent = 20.0 if task.status == TaskStatus.IN_PROGRESS else 0.0
        task.approval_status = ApprovalStatus.APPROVED.value
        task.ai_generated = True
        task.ai_source = "Demo AI simulation - role coverage"

        specification = task.specification
        specification.wbs_code = wbs_code
        specification.work_package = role["category_label"]
        specification.acceptance_criteria = (
            f"Output {role['label']} telah diunggah, ditinjau, dan memenuhi prosedur proyek."
        )
        specification.reporting_instructions = (
            "Perbarui progres, uraikan hasil kerja, kendala, dan unggah sedikitnya satu bukti. "
            "Update dapat dilakukan dari website; role lapangan juga dapat memakai Telegram."
        )
        specification.required_photo_count = 1 if role["category"] in {"field", "engineering", "quality_safety"} else 0
        specification.required_document_count = 1 if role["category"] in {"controls", "commercial"} else 0
        specification.template_name = "Demo Assignment per Role"
        specification.template_version = "1.0"

        if not task.requirements:
            task.requirements.append(TaskRequirement(
                code=f"{wbs_code}-OUTPUT",
                title="Output pekerjaan tersedia",
                description="PIC mengunggah hasil kerja atau evidence yang dapat diverifikasi.",
                requirement_type="checklist",
                validation_rule="manual_confirmation",
                is_mandatory=True,
                sequence=1,
            ))
        assignment_counts[project_role] += 1
        task_count += 1

    db.flush()
    return task_count, dict(assignment_counts)


def active_pic_roles(db: Session, project_id: int) -> list[dict]:
    disabled_roles = {
        row.role_code for row in db.query(ProjectRolePolicy).filter(
            ProjectRolePolicy.project_id == project_id,
            ProjectRolePolicy.enabled == False,
        ).all()
    }
    memberships = db.query(ProjectMembership).join(User).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.is_active == True,
        User.is_active == True,
    ).all()
    role_codes = sorted({
        item.project_role
        for item in memberships
        if role_can_be_task_pic(item.project_role) and item.project_role not in disabled_roles
    })
    return [PROJECT_ROLE_BY_CODE[code] for code in role_codes if code in PROJECT_ROLE_BY_CODE]


ROLE_KEYWORDS = (
    ("hse_officer", ("hse", "safety", "k3", "keselamatan")),
    ("qa_qc_engineer", ("qa/qc", "quality", "mutu", "inspection", "inspeksi")),
    ("planning_engineer", ("schedule", "jadwal", "planning", "lookahead", "delay")),
    ("cost_controller", ("cost", "biaya", "budget", "cashflow")),
    ("quantity_surveyor", ("quantity", "volume", "boq", "progress claim")),
    ("procurement_officer", ("procurement", "pengadaan", "purchase", "vendor", "material")),
    ("doc_controller", ("document", "dokumen", "as-built", "transmittal", "revision")),
    ("bim_modeler", ("bim", "clash", "model koordinasi")),
    ("structural_engineer", ("struktur", "structural", "beton", "baja")),
    ("mep_engineer", ("mep", "electrical", "mekanikal", "plumbing", "hvac")),
    ("architect_engineer", ("arsitektur", "architect", "finishing", "fasad")),
    ("surveyor", ("survey", "setting out", "elevasi", "pengukuran")),
    ("warehouse_keeper", ("warehouse", "gudang", "stok")),
    ("logistics_coord", ("logistik", "delivery", "pengiriman")),
    ("project_accountant", ("invoice", "akuntansi", "pembayaran", "pajak")),
    ("contract_manager", ("kontrak", "contract", "claim", "klaim", "variation order")),
    ("supervisor", ("supervisor", "pelaksanaan", "tenaga kerja", "lapangan")),
)


def resolve_task_project_role(task_payload: dict, allowed_role_codes: set[str]) -> str | None:
    requested = str(task_payload.get("project_role") or "").strip().lower()
    if requested in allowed_role_codes and role_can_be_task_pic(requested):
        return requested
    searchable = " ".join(str(task_payload.get(key) or "") for key in (
        "title", "description", "division", "work_package", "reporting_instructions"
    )).lower()
    for role_code, keywords in ROLE_KEYWORDS:
        if role_code in allowed_role_codes and any(keyword in searchable for keyword in keywords):
            return role_code
    return next(
        (role for role in ("site_engineer", "staff", "project_manager") if role in allowed_role_codes),
        next(iter(sorted(allowed_role_codes)), None),
    )


def select_task_pic(
    db: Session,
    *,
    project_id: int,
    requested_project_role: str | None,
) -> ProjectMembership | None:
    """Select the least-loaded active member of the requested PIC role."""
    if not role_can_be_task_pic(requested_project_role):
        return None
    disabled = db.query(ProjectRolePolicy).filter(
        ProjectRolePolicy.project_id == project_id,
        ProjectRolePolicy.role_code == requested_project_role,
        ProjectRolePolicy.enabled == False,
    ).first()
    if disabled:
        return None
    candidates = db.query(ProjectMembership).join(User).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.project_role == requested_project_role,
        ProjectMembership.is_active == True,
        User.is_active == True,
    ).all()
    if not candidates:
        return None

    counts = Counter(item[0] for item in db.query(Task.assigned_to).filter(
        Task.project_id == project_id,
        Task.assigned_to.in_([item.user_id for item in candidates]),
        Task.status != TaskStatus.DONE,
    ).all())
    return min(candidates, key=lambda item: (counts[item.user_id], item.user_id))
