from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# PostgreSQL untuk production; SQLite juga didukung untuk demo lokal tanpa
# layanan database tambahan.
engine_options = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options.update({"pool_size": 10, "max_overflow": 20})

engine = create_engine(settings.DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class untuk semua model
Base = declarative_base()


def get_db():
    """Dependency untuk mendapatkan DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Buat semua tabel di database."""
    Base.metadata.create_all(bind=engine)
    _ensure_admin_role_constraints()
    _ensure_lightweight_columns()


def _ensure_admin_role_constraints():
    """Migrate role vocabulary and enforce one owner / one project admin mapping."""
    if engine.dialect.name == "postgresql":
        # A PostgreSQL enum addition must be committed before the value is
        # referenced by another statement.
        with engine.begin() as connection:
            connection.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'OWNER'"))

    with engine.begin() as connection:
        # Legacy datasets linked the project owner as ``project_manager``.
        # Promote at most one owned project per Admin account to the new
        # one-admin/one-project relationship before creating constraints.
        candidates = connection.execute(text(
            "SELECT p.id AS project_id, p.owner_id AS user_id, MIN(pm.id) AS membership_id "
            "FROM projects p "
            "JOIN users u ON u.id = p.owner_id "
            "JOIN project_memberships pm ON pm.project_id = p.id AND pm.user_id = p.owner_id "
            "WHERE u.role = 'ADMIN' AND pm.is_active = TRUE "
            "GROUP BY p.id, p.owner_id ORDER BY p.id"
        )).mappings().all()
        assigned_users: set[int] = set()
        for candidate in candidates:
            user_id = int(candidate["user_id"])
            if user_id in assigned_users:
                continue
            existing_project_admin = connection.execute(text(
                "SELECT id FROM project_memberships "
                "WHERE project_id = :project_id AND project_role = 'project_admin' AND is_active = TRUE"
            ), {"project_id": candidate["project_id"]}).first()
            existing_admin_project = connection.execute(text(
                "SELECT id FROM project_memberships "
                "WHERE user_id = :user_id AND project_role = 'project_admin' AND is_active = TRUE"
            ), {"user_id": user_id}).first()
            if not existing_project_admin and not existing_admin_project:
                connection.execute(text(
                    "UPDATE project_memberships SET project_role = 'project_admin' WHERE id = :membership_id"
                ), {"membership_id": candidate["membership_id"]})
            assigned_users.add(user_id)

        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_single_owner "
            "ON users (role) WHERE role = 'OWNER'"
        ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_single_project_admin "
            "ON project_memberships (project_id) "
            "WHERE project_role = 'project_admin' AND is_active = TRUE"
        ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_single_admin_project "
            "ON project_memberships (user_id) "
            "WHERE project_role = 'project_admin' AND is_active = TRUE"
        ))


def _ensure_lightweight_columns():
    """Tambahkan kolom kecil untuk DB lama tanpa menunggu migration runner."""
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    task_columns = (
        {column["name"] for column in inspector.get_columns("tasks")}
        if inspector.has_table("tasks")
        else set()
    )
    control_columns = (
        {column["name"] for column in inspector.get_columns("task_controls")}
        if inspector.has_table("task_controls")
        else set()
    )
    dependency_columns = (
        {column["name"] for column in inspector.get_columns("task_dependencies")}
        if inspector.has_table("task_dependencies")
        else set()
    )
    project_columns = (
        {column["name"] for column in inspector.get_columns("projects")}
        if inspector.has_table("projects")
        else set()
    )
    with engine.begin() as connection:
        if "avatar_url" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
        if "email_verified_at" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP"))
            connection.execute(text("UPDATE users SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
        if "email_verification_required" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email_verification_required BOOLEAN NOT NULL DEFAULT FALSE"))
        if "must_set_password" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN must_set_password BOOLEAN NOT NULL DEFAULT FALSE"))
        if "auth_version" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 1"))
        if "approval_status" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN approval_status VARCHAR(30) NOT NULL DEFAULT 'approved'"))
        if "approval_id" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN approval_id INTEGER"))
        if "approved_by" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN approved_by INTEGER"))
        if "approved_at" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN approved_at TIMESTAMP"))
        if "approval_note" not in task_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN approval_note TEXT"))
        if "boq_value" not in control_columns:
            connection.execute(text("ALTER TABLE task_controls ADD COLUMN boq_value FLOAT NOT NULL DEFAULT 0"))
        if "internal_material_cost" not in control_columns:
            connection.execute(text("ALTER TABLE task_controls ADD COLUMN internal_material_cost FLOAT NOT NULL DEFAULT 0"))
        if "internal_labor_cost" not in control_columns:
            connection.execute(text("ALTER TABLE task_controls ADD COLUMN internal_labor_cost FLOAT NOT NULL DEFAULT 0"))
        if "internal_equipment_cost" not in control_columns:
            connection.execute(text("ALTER TABLE task_controls ADD COLUMN internal_equipment_cost FLOAT NOT NULL DEFAULT 0"))
        if "internal_overhead_cost" not in control_columns:
            connection.execute(text("ALTER TABLE task_controls ADD COLUMN internal_overhead_cost FLOAT NOT NULL DEFAULT 0"))
        if "internal_risk_cost" not in control_columns:
            connection.execute(text("ALTER TABLE task_controls ADD COLUMN internal_risk_cost FLOAT NOT NULL DEFAULT 0"))
        if "reason" not in dependency_columns:
            connection.execute(text("ALTER TABLE task_dependencies ADD COLUMN reason TEXT"))
        if "plan_key" not in project_columns:
            connection.execute(text("ALTER TABLE projects ADD COLUMN plan_key VARCHAR(40)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_plan_key ON projects (plan_key)"))


def bootstrap_project_memberships():
    """Backfill keanggotaan proyek dari owner, divisi lama, dan assignment task."""
    from app.models.user import Division, Project, ProjectMembership, Task, User

    db = SessionLocal()
    try:
        existing = {
            (item.project_id, item.user_id): item
            for item in db.query(ProjectMembership).all()
        }

        def upsert(project_id, user_id, division_id=None, project_role="staff"):
            if not user_id:
                return
            key = (project_id, user_id)
            membership = existing.get(key)
            if membership:
                membership.is_active = True
                if membership.division_id is None and division_id is not None:
                    membership.division_id = division_id
                if membership.project_role == "staff" and project_role != "staff":
                    membership.project_role = project_role
                return
            membership = ProjectMembership(
                project_id=project_id,
                user_id=user_id,
                division_id=division_id,
                project_role=project_role,
            )
            db.add(membership)
            existing[key] = membership

        for project in db.query(Project).all():
            upsert(project.id, project.owner_id, project_role="project_manager")
        for division in db.query(Division).all():
            upsert(division.project_id, division.manager_id, division.id, "division_lead")
        for user in db.query(User).filter(User.division_id.isnot(None)).all():
            upsert(user.division.project_id, user.id, user.division_id)
        for task in db.query(Task).filter(Task.assigned_to.isnot(None)).all():
            upsert(task.project_id, task.assigned_to, task.division_id)
        db.commit()
    finally:
        db.close()


def bootstrap_dataset_task_divisions():
    """Pindahkan task impor lama dari divisi bawaan ke divisi disiplin WBS."""
    from app.services.project_dataset import sync_dataset_task_divisions

    db = SessionLocal()
    try:
        result = sync_dataset_task_divisions(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def bootstrap_feature_flags():
    """Seed default feature/menu flags used by the admin console."""
    from app.services.feature_flags import bootstrap_feature_flags as seed_flags

    db = SessionLocal()
    try:
        seed_flags(db)
    finally:
        db.close()
