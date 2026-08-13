from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from app.db.database import get_db
from app.models.user import (
    AuditLog, DailyReport, Division, Project, ProjectMembership, ProjectRolePolicy, ProjectStatus, Task, User,
    UserRole,
)
from app.schemas.schemas import (
    DivisionCreate, DivisionResponse, DivisionUpdate, ProjectCreate,
    ProjectMemberCreate, ProjectMemberResponse, ProjectMemberUpdate,
    ProjectMemberRoleCatalogResponse, ProjectResponse, ProjectRolePolicyResponse,
    ProjectRolePolicyUpdate, ProjectUpdate,
)
from app.core.security import get_current_user, require_roles
from app.services.audit_service import log_audit
from app.services.project_role_catalog import (
    PROJECT_ROLE_CATALOG,
    is_financial_project_role,
    is_valid_project_role,
    project_role_label,
    role_requires_division,
)
from app.services.report_workflow import ensure_project_access
from app.services.feature_flags import bootstrap_project_feature_entitlements
from app.services.project_dataset import sync_dataset_task_divisions

router = APIRouter(prefix="/projects", tags=["Projects"])
FINANCIAL_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)
PROJECT_ADMIN_ROLES = {"project_admin"}


def _can_view_project_financials(project: Project, user: User) -> bool:
    if user.role in FINANCIAL_ROLES:
        return True
    membership = next((
        item for item in project.memberships
        if item.user_id == user.id and item.is_active
    ), None)
    return bool(membership and is_financial_project_role(membership.project_role))


def _project_response(project: Project, user: User) -> dict:
    return {
        "id": project.id,
        "project_name": project.project_name,
        "description": project.description,
        "location": project.location,
        "contract_value": project.contract_value if _can_view_project_financials(project, user) else None,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "status": project.status,
        "plan_key": project.plan_key,
        "owner_id": project.owner_id,
        "progress_percent": project.progress_percent,
        "created_at": project.created_at,
    }


def _membership_response(membership: ProjectMembership, user: User) -> dict:
    member = membership.user
    expose_contact = user.role in FINANCIAL_ROLES or member.id == user.id
    return {
        "id": membership.id,
        "project_id": membership.project_id,
        "user_id": membership.user_id,
        "division_id": membership.division_id,
        "project_role": membership.project_role,
        "is_active": membership.is_active,
        "joined_at": membership.joined_at,
        "user": {
            "id": member.id, "name": member.name,
            "email": member.email if expose_contact else None,
            "role": member.role, "phone": member.phone if expose_contact else None,
            "division_id": member.division_id,
            "telegram_id": member.telegram_id if expose_contact else None,
            "is_active": member.is_active, "created_at": member.created_at,
        },
        "division": membership.division,
    }


def _ensure_project_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Hanya Admin Proyek yang dapat mengubah struktur role proyek")


def _ensure_project_admin_assignment_allowed(
    user: User,
    current_role: Optional[str],
    next_role: Optional[str],
) -> None:
    current_is_project_admin = bool(current_role and current_role in PROJECT_ADMIN_ROLES)
    next_is_project_admin = bool(next_role and next_role in PROJECT_ADMIN_ROLES)
    if (current_is_project_admin or next_is_project_admin) and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Pembuatan atau perubahan role admin proyek hanya boleh dilakukan oleh Admin Proyek",
        )


def _role_policy_response(project_id: int, role: dict, policy: Optional[ProjectRolePolicy]) -> dict:
    return {
        **role,
        "project_id": project_id,
        "enabled": policy.enabled if policy else True,
        "updated_by": policy.updated_by if policy else None,
        "created_at": policy.created_at if policy else None,
        "updated_at": policy.updated_at if policy else None,
    }


def _sync_project_role_policies(db: Session, project_id: int) -> List[ProjectRolePolicy]:
    existing = {
        policy.role_code: policy
        for policy in db.query(ProjectRolePolicy).filter(ProjectRolePolicy.project_id == project_id).all()
    }
    for role in PROJECT_ROLE_CATALOG:
        if role["code"] not in existing:
            policy = ProjectRolePolicy(project_id=project_id, role_code=role["code"], enabled=True)
            db.add(policy)
            existing[role["code"]] = policy
    db.flush()
    return [existing[role["code"]] for role in PROJECT_ROLE_CATALOG]


def _is_project_role_enabled(db: Session, project_id: int, role_code: str) -> bool:
    policy = db.query(ProjectRolePolicy).filter(
        ProjectRolePolicy.project_id == project_id,
        ProjectRolePolicy.role_code == role_code,
    ).first()
    return True if policy is None else policy.enabled


def _staff_accessible_division_ids(db: Session, project_id: int, user: User) -> set[int]:
    membership_division_ids = {
        row[0] for row in db.query(ProjectMembership.division_id).filter(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
            ProjectMembership.is_active == True,
            ProjectMembership.division_id.isnot(None),
        ).all()
    }
    if user.division_id is not None:
        profile_division = db.query(Division.id).filter(
            Division.id == user.division_id,
            Division.project_id == project_id,
        ).first()
        if profile_division:
            membership_division_ids.add(user.division_id)
    return membership_division_ids


@router.get("/member-roles", response_model=List[ProjectMemberRoleCatalogResponse])
def list_project_member_roles(
    current_user: User = Depends(get_current_user),
):
    return PROJECT_ROLE_CATALOG


# ─────────────────────────────────────────────
# PROJECTS
# ─────────────────────────────────────────────

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil daftar proyek berdasarkan role user."""
    query = db.query(Project)

    # Hanya Owner dan Director yang melihat seluruh proyek; role operasional dibatasi relasinya.
    if current_user.role not in [UserRole.OWNER, UserRole.DIRECTOR]:
        project_ids = set()

        if current_user.role != UserRole.ADMIN:
            project_ids.update(
                p.id for p in db.query(Project).filter(Project.owner_id == current_user.id).all()
            )

        membership_query = db.query(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id,
            ProjectMembership.is_active == True,
        )
        if current_user.role == UserRole.ADMIN:
            membership_query = membership_query.filter(ProjectMembership.project_role == "project_admin")
        memberships = membership_query.all()
        project_ids.update(item.project_id for item in memberships)

        if current_user.role != UserRole.ADMIN:
            managed_divisions = db.query(Division).filter(Division.manager_id == current_user.id).all()
            project_ids.update(d.project_id for d in managed_divisions)

            assigned_tasks = db.query(Task).filter(
                (Task.assigned_to == current_user.id) |
                (Task.created_by == current_user.id) |
                (Task.division_id == current_user.division_id)
            ).all()
            project_ids.update(t.project_id for t in assigned_tasks)

            own_reports = db.query(DailyReport).filter(DailyReport.user_id == current_user.id).all()
            project_ids.update(r.project_id for r in own_reports)

        if not project_ids:
            return []
        query = query.filter(Project.id.in_(project_ids))

    if status:
        query = query.filter(Project.status == status)

    projects = query.order_by(Project.created_at.desc()).all()
    return [_project_response(project, current_user) for project in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    """Buat proyek baru."""
    existing_admin_project = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == current_user.id,
        ProjectMembership.project_role == "project_admin",
        ProjectMembership.is_active == True,
    ).first()
    if existing_admin_project:
        raise HTTPException(status_code=409, detail="Satu Admin Proyek hanya dapat mewakili satu proyek")
    project = Project(**data.model_dump(), owner_id=current_user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMembership(
        project_id=project.id,
        user_id=current_user.id,
        project_role="project_admin",
        is_active=True,
    ))
    bootstrap_project_feature_entitlements(db, project, current_user.id)
    log_audit(
        db,
        actor_id=current_user.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        summary=f"Proyek dibuat: {project.project_name}",
        after=data.model_dump(),
    )
    db.commit()
    db.refresh(project)
    return _project_response(project, current_user)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil detail satu proyek."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    return _project_response(project, current_user)


@router.get("/{project_id}/role-policy", response_model=List[ProjectRolePolicyResponse])
def list_project_role_policy(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    policies = {policy.role_code: policy for policy in _sync_project_role_policies(db, project_id)}
    db.commit()
    return [
        _role_policy_response(project_id, role, policies.get(role["code"]))
        for role in PROJECT_ROLE_CATALOG
    ]


@router.patch("/{project_id}/role-policy/{role_code}", response_model=ProjectRolePolicyResponse)
def update_project_role_policy(
    project_id: int,
    role_code: str,
    data: ProjectRolePolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    _ensure_project_admin(current_user)
    ensure_project_access(current_user, project)
    if not is_valid_project_role(role_code):
        raise HTTPException(status_code=400, detail="Peran proyek tidak valid")
    if role_code == "project_admin" and not data.enabled:
        raise HTTPException(status_code=409, detail="Admin Proyek tidak boleh dinonaktifkan")

    _sync_project_role_policies(db, project_id)
    policy = db.query(ProjectRolePolicy).filter(
        ProjectRolePolicy.project_id == project_id,
        ProjectRolePolicy.role_code == role_code,
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy role tidak ditemukan")

    before = {"enabled": policy.enabled}
    policy.enabled = data.enabled
    policy.updated_by = current_user.id
    policy.updated_at = datetime.utcnow()
    role = next(item for item in PROJECT_ROLE_CATALOG if item["code"] == role_code)
    log_audit(
        db,
        actor_id=current_user.id,
        action="project.role_policy_updated",
        entity_type="project_role_policy",
        entity_id=policy.id,
        project_id=project_id,
        summary=f"Policy role {role['label']} diubah menjadi {'aktif' if policy.enabled else 'nonaktif'}",
        before=before,
        after={"enabled": policy.enabled},
    )
    db.commit()
    db.refresh(policy)
    return _role_policy_response(project_id, role, policy)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER))
):
    """Update data proyek."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)

    before = {
        "project_name": project.project_name,
        "status": project.status.value if project.status else None,
        "progress_percent": project.progress_percent,
    }
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(project, field, value)

    log_audit(
        db,
        actor_id=current_user.id,
        action="project.updated",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        summary=f"Proyek diupdate: {project.project_name}",
        before=before,
        after=changes,
    )
    db.commit()
    db.refresh(project)
    return _project_response(project, current_user)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR))
):
    """Hapus proyek (Admin & Director saja)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)

    db.query(AuditLog).filter(AuditLog.project_id == project.id).update(
        {AuditLog.project_id: None}, synchronize_session=False,
    )
    log_audit(
        db,
        actor_id=current_user.id,
        action="project.deleted",
        entity_type="project",
        entity_id=project.id,
        project_id=None,
        summary=f"Proyek dihapus: {project.project_name}",
        before={"project_name": project.project_name, "status": project.status.value if project.status else None},
    )
    db.delete(project)
    db.commit()


# ─────────────────────────────────────────────
# DIVISIONS (nested under project)
# ─────────────────────────────────────────────

@router.get("/{project_id}/divisions", response_model=List[DivisionResponse])
def list_divisions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ambil semua divisi dalam proyek."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    division_sync = sync_dataset_task_divisions(db, project_id)
    if division_sync["tasks_updated"] or division_sync["divisions_created"]:
        db.commit()
    query = db.query(Division).filter(Division.project_id == project_id)
    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        division_ids = _staff_accessible_division_ids(db, project_id, current_user)
        if not division_ids:
            return []
        query = query.filter(Division.id.in_(division_ids))
    return query.all()


@router.post("/{project_id}/divisions", response_model=DivisionResponse, status_code=201)
def create_division(
    project_id: int,
    data: DivisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER))
):
    """Tambah divisi ke proyek."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)

    existing = db.query(Division).filter(
        Division.project_id == project_id,
        Division.division_name.ilike(data.division_name.strip()),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Nama divisi sudah digunakan pada proyek ini")

    division = Division(**data.model_dump(), project_id=project_id)
    db.add(division)
    db.flush()
    log_audit(
        db,
        actor_id=current_user.id,
        action="division.created",
        entity_type="division",
        entity_id=division.id,
        project_id=project_id,
        summary=f"Divisi dibuat: {division.division_name}",
        after=data.model_dump(),
    )
    db.commit()
    db.refresh(division)
    return division


@router.put("/{project_id}/divisions/{division_id}", response_model=DivisionResponse)
def update_division(
    project_id: int,
    division_id: int,
    data: DivisionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    division = db.query(Division).filter(
        Division.id == division_id,
        Division.project_id == project_id,
    ).first()
    if not division:
        raise HTTPException(status_code=404, detail="Divisi tidak ditemukan")
    before = {"division_name": division.division_name, "description": division.description}
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(division, field, value)
    log_audit(
        db, actor_id=current_user.id, action="division.updated",
        entity_type="division", entity_id=division.id, project_id=project_id,
        summary=f"Divisi diperbarui: {division.division_name}", before=before,
        after=data.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(division)
    return division


@router.delete("/{project_id}/divisions/{division_id}", status_code=204)
def delete_division(
    project_id: int,
    division_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    division = db.query(Division).filter(
        Division.id == division_id,
        Division.project_id == project_id,
    ).first()
    if not division:
        raise HTTPException(status_code=404, detail="Divisi tidak ditemukan")
    if db.query(Task).filter(Task.division_id == division.id).first():
        raise HTTPException(status_code=409, detail="Pindahkan task dari divisi ini sebelum menghapusnya")
    if db.query(ProjectMembership).filter(
        ProjectMembership.division_id == division.id,
        ProjectMembership.is_active == True,
    ).first():
        raise HTTPException(status_code=409, detail="Pindahkan anggota divisi sebelum menghapusnya")
    log_audit(
        db, actor_id=current_user.id, action="division.deleted",
        entity_type="division", entity_id=division.id, project_id=project_id,
        summary=f"Divisi dihapus: {division.division_name}",
        before={"division_name": division.division_name},
    )
    db.delete(division)
    db.commit()


def _validate_member_data(
    db: Session,
    project_id: int,
    user_id: int,
    division_id: Optional[int],
    project_role: str,
    current_role: Optional[str] = None,
):
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User aktif tidak ditemukan")
    if user.role == UserRole.OWNER:
        raise HTTPException(status_code=400, detail="Admin Owner tidak dapat menjadi anggota proyek")
    if project_role == "project_admin":
        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=400, detail="Role Admin Proyek hanya dapat diberikan kepada akun Admin Proyek")
        other_project_admin = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id != user_id,
            ProjectMembership.project_role == "project_admin",
            ProjectMembership.is_active == True,
        ).first()
        if other_project_admin:
            raise HTTPException(status_code=409, detail="Proyek sudah memiliki Admin Proyek")
        other_admin_project = db.query(ProjectMembership).filter(
            ProjectMembership.user_id == user_id,
            ProjectMembership.project_id != project_id,
            ProjectMembership.project_role == "project_admin",
            ProjectMembership.is_active == True,
        ).first()
        if other_admin_project:
            raise HTTPException(status_code=409, detail="Akun Admin Proyek sudah mewakili proyek lain")
    if not is_valid_project_role(project_role):
        raise HTTPException(status_code=400, detail="Peran proyek tidak valid")
    if project_role != current_role and not _is_project_role_enabled(db, project_id, project_role):
        raise HTTPException(status_code=409, detail=f"{project_role_label(project_role)} sedang dinonaktifkan untuk proyek ini")
    if role_requires_division(project_role) and division_id is None:
        raise HTTPException(status_code=400, detail=f"{project_role_label(project_role)} wajib ditempatkan pada divisi")
    if division_id is not None:
        division = db.query(Division).filter(
            Division.id == division_id,
            Division.project_id == project_id,
        ).first()
        if not division:
            raise HTTPException(status_code=400, detail="Divisi tidak berasal dari proyek ini")


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
def list_project_members(
    project_id: int,
    division_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    query = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.is_active == True,
    )
    if division_id is not None:
        query = query.filter(ProjectMembership.division_id == division_id)
    if current_user.role in (UserRole.STAFF, UserRole.SUBCONTRACTOR):
        division_ids = _staff_accessible_division_ids(db, project_id, current_user)
        staff_filters = [ProjectMembership.user_id == current_user.id]
        if division_ids:
            staff_filters.append(ProjectMembership.division_id.in_(division_ids))
        query = query.filter(or_(*staff_filters))
    memberships = query.join(User).order_by(User.name).all()
    return [_membership_response(item, current_user) for item in memberships]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=201)
def add_project_member(
    project_id: int,
    data: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == data.user_id,
    ).first()
    _ensure_project_admin_assignment_allowed(
        current_user,
        membership.project_role if membership else None,
        data.project_role,
    )
    _validate_member_data(
        db,
        project_id,
        data.user_id,
        data.division_id,
        data.project_role,
        current_role=membership.project_role if membership else None,
    )
    if membership:
        membership.division_id = data.division_id
        membership.project_role = data.project_role
        membership.is_active = True
    else:
        membership = ProjectMembership(project_id=project_id, **data.model_dump())
        db.add(membership)
    db.flush()
    log_audit(
        db, actor_id=current_user.id, action="project.member_assigned",
        entity_type="project_membership", entity_id=membership.id,
        project_id=project_id, summary=f"Anggota proyek ditempatkan: user #{data.user_id}",
        after=data.model_dump(),
    )
    db.commit()
    db.refresh(membership)
    return membership


@router.put("/{project_id}/members/{membership_id}", response_model=ProjectMemberResponse)
def update_project_member(
    project_id: int,
    membership_id: int,
    data: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.id == membership_id,
        ProjectMembership.project_id == project_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Anggota proyek tidak ditemukan")
    next_division = data.division_id if "division_id" in data.model_fields_set else membership.division_id
    next_role = data.project_role if data.project_role is not None else membership.project_role
    if membership.project_role == "project_admin" and next_role != "project_admin":
        raise HTTPException(status_code=409, detail="Proyek wajib memiliki tepat satu Admin Proyek")
    _ensure_project_admin_assignment_allowed(current_user, membership.project_role, next_role)
    _validate_member_data(db, project_id, membership.user_id, next_division, next_role, current_role=membership.project_role)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(membership, field, value)
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/{project_id}/members/{membership_id}", status_code=204)
def remove_project_member(
    project_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.MANAGER)),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    ensure_project_access(current_user, project)
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.id == membership_id,
        ProjectMembership.project_id == project_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Anggota proyek tidak ditemukan")
    if membership.project_role == "project_admin":
        raise HTTPException(status_code=409, detail="Admin Proyek utama tidak dapat dikeluarkan dari proyek")
    _ensure_project_admin_assignment_allowed(current_user, membership.project_role, None)
    if db.query(Task).filter(
        Task.project_id == project_id,
        Task.assigned_to == membership.user_id,
        Task.status.notin_(["done"]),
    ).first():
        raise HTTPException(status_code=409, detail="Alihkan task aktif staff ini sebelum mengeluarkannya")
    membership.is_active = False
    db.commit()
