from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# PostgreSQL engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # cek koneksi sebelum digunakan
    pool_size=10,             # jumlah koneksi di pool
    max_overflow=20,          # koneksi tambahan saat pool penuh
)

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
    _ensure_lightweight_columns()


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
    with engine.begin() as connection:
        if "avatar_url" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
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


def bootstrap_feature_flags():
    """Seed default feature/menu flags used by the admin console."""
    from app.services.feature_flags import bootstrap_feature_flags as seed_flags

    db = SessionLocal()
    try:
        seed_flags(db)
    finally:
        db.close()
