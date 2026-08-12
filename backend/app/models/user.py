"""
Database Models - AI CPMIS
Semua model SQLAlchemy ada di sini.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Enum, Float, UniqueConstraint
)
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DIRECTOR = "director"
    MANAGER = "manager"
    STAFF = "staff"
    SUBCONTRACTOR = "subcontractor"


class ProjectStatus(str, enum.Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentType(str, enum.Enum):
    TENDER = "tender"
    CONTRACT = "contract"
    DAILY_REPORT = "daily_report"
    PHOTO = "photo"
    DRAWING = "drawing"
    OTHER = "other"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalType(str, enum.Enum):
    DOCUMENT = "document"
    TASK = "task"
    INSTRUCTION = "instruction"
    SCOPE_CHANGE = "scope_change"
    OTHER = "other"


class CommunicationType(str, enum.Enum):
    RFI = "rfi"
    SUBMITTAL = "submittal"
    SITE_INSTRUCTION = "site_instruction"
    ISSUE = "issue"
    ESCALATION = "escalation"
    MEETING_ACTION = "meeting_action"


class CommunicationStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    IN_REVIEW = "in_review"
    ANSWERED = "answered"
    CLOSED = "closed"
    VOID = "void"


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    NEEDS_REVISION = "needs_revision"
    READY_FOR_REVIEW = "ready_for_review"
    VERIFIED = "verified"
    APPROVED = "approved"


class EvidenceType(str, enum.Enum):
    PHOTO = "photo"
    DOCUMENT = "document"


class DocumentSyncStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"


class DigitalTwinNodeType(str, enum.Enum):
    PROJECT = "project"
    CONTRACT = "contract"
    STAKEHOLDER = "stakeholder"
    WBS = "wbs"
    BOQ = "boq"
    ACTIVITY = "activity"
    MILESTONE = "milestone"
    RESOURCE = "resource"
    CREW = "crew"
    LABOR = "labor"
    EQUIPMENT = "equipment"
    MATERIAL = "material"
    SUPPLIER = "supplier"
    PROCUREMENT = "procurement"
    DOCUMENT = "document"
    DRAWING = "drawing"
    INSPECTION = "inspection"
    RISK = "risk"
    ISSUE = "issue"
    REPORT = "report"
    WEATHER = "weather"
    CASH_FLOW = "cash_flow"
    PAYMENT = "payment"
    RULE = "rule"
    HISTORICAL_PROJECT = "historical_project"


class DigitalTwinRuleCategory(str, enum.Enum):
    GENERAL = "general"
    SCHEDULING = "scheduling"
    RESOURCE = "resource"
    PROCUREMENT = "procurement"
    QUALITY = "quality"
    HSE = "hse"
    COST = "cost"
    RISK = "risk"


# ─────────────────────────────────────────────
# USER MODEL
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STAFF, nullable=False)
    telegram_id = Column(String(50), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    division = relationship("Division", back_populates="members", foreign_keys=[division_id])
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to")
    created_tasks = relationship("Task", back_populates="creator", foreign_keys="Task.created_by")
    uploaded_documents = relationship("Document", back_populates="uploader")
    daily_reports = relationship("DailyReport", back_populates="reporter")
    project_memberships = relationship("ProjectMembership", back_populates="user", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# PROJECT MODEL
# ─────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    contract_value = Column(Float, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    progress_percent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    divisions = relationship("Division", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    daily_reports = relationship("DailyReport", back_populates="project", cascade="all, delete-orphan")
    communications = relationship("CommunicationItem", back_populates="project", cascade="all, delete-orphan")
    memberships = relationship("ProjectMembership", back_populates="project", cascade="all, delete-orphan")
    role_policies = relationship("ProjectRolePolicy", back_populates="project", cascade="all, delete-orphan")
    vendor_profiles = relationship("VendorProfile", back_populates="project", cascade="all, delete-orphan")
    productivity_benchmarks = relationship(
        "ProductivityBenchmark", back_populates="project", cascade="all, delete-orphan"
    )
    digital_twin_nodes = relationship(
        "DigitalTwinNode", back_populates="project", cascade="all, delete-orphan"
    )
    digital_twin_relationships = relationship(
        "DigitalTwinRelationship", back_populates="project", cascade="all, delete-orphan"
    )
    digital_twin_rules = relationship(
        "DigitalTwinRule", back_populates="project", cascade="all, delete-orphan"
    )
    digital_twin_reasoning_examples = relationship(
        "DigitalTwinReasoningExample", back_populates="project", cascade="all, delete-orphan"
    )
    digital_twin_validation_issues = relationship(
        "DigitalTwinValidationIssue", back_populates="project", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────
# DIVISION MODEL
# ─────────────────────────────────────────────

class Division(Base):
    __tablename__ = "divisions"

    id = Column(Integer, primary_key=True, index=True)
    division_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="divisions")
    manager = relationship("User", foreign_keys=[manager_id])
    members = relationship("User", back_populates="division", foreign_keys="User.division_id")
    tasks = relationship("Task", back_populates="division")
    project_memberships = relationship("ProjectMembership", back_populates="division")


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True, index=True)
    project_role = Column(String(30), default="staff", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="memberships")
    user = relationship("User", back_populates="project_memberships")
    division = relationship("Division", back_populates="project_memberships")


# ─────────────────────────────────────────────
class ProjectRolePolicy(Base):
    __tablename__ = "project_role_policies"
    __table_args__ = (
        UniqueConstraint("project_id", "role_code", name="uq_project_role_policy"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    role_code = Column(String(40), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="role_policies")
    updater = relationship("User", foreign_keys=[updated_by])


# TASK MODEL
# ─────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO)
    deadline = Column(DateTime, nullable=True)
    progress_percent = Column(Float, default=0.0)
    approval_status = Column(String(30), default=ApprovalStatus.APPROVED.value, nullable=False)
    approval_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_note = Column(Text, nullable=True)
    ai_generated = Column(Boolean, default=False)   # apakah dibuat oleh AI
    ai_source = Column(String(100), nullable=True)  # dari tender/contract mana
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="tasks")
    division = relationship("Division", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to])
    creator = relationship("User", back_populates="created_tasks", foreign_keys=[created_by])
    approval = relationship("ApprovalRequest", foreign_keys=[approval_id])
    approver = relationship("User", foreign_keys=[approved_by])
    subtasks = relationship("Task", backref="parent", remote_side=[id])
    specification = relationship(
        "TaskSpecification", back_populates="task", uselist=False,
        cascade="all, delete-orphan"
    )
    requirements = relationship(
        "TaskRequirement", back_populates="task", cascade="all, delete-orphan",
        order_by="TaskRequirement.sequence"
    )
    materials = relationship(
        "TaskMaterialSpecification", back_populates="task", cascade="all, delete-orphan",
        order_by="TaskMaterialSpecification.sequence"
    )
    control = relationship(
        "TaskControl", back_populates="task", uselist=False, cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────
# DOCUMENT MODEL
# ─────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # path di MinIO/S3
    file_type = Column(Enum(DocumentType), default=DocumentType.OTHER)
    file_size = Column(Integer, nullable=True)  # bytes
    mime_type = Column(String(100), nullable=True)
    version = Column(Integer, default=1)
    ai_analysis = Column(Text, nullable=True)   # hasil analisis AI (JSON string)
    telegram_message_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="documents")
    uploader = relationship("User", back_populates="uploaded_documents")
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=False)
    token_estimate = Column(Integer, default=0, nullable=False)
    source_page = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")
    project = relationship("Project", foreign_keys=[project_id])


# ─────────────────────────────────────────────
# DAILY REPORT MODEL
# ─────────────────────────────────────────────

class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_date = Column(DateTime, default=datetime.utcnow)
    report_text = Column(Text, nullable=False)
    weather = Column(String(50), nullable=True)
    manpower_count = Column(Integer, nullable=True)
    work_progress = Column(Text, nullable=True)
    issues = Column(Text, nullable=True)
    photo_paths = Column(Text, nullable=True)   # JSON string list of paths
    ai_summary = Column(Text, nullable=True)    # ringkasan dari AI
    ai_risks = Column(Text, nullable=True)      # deteksi risiko dari AI
    telegram_message_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="daily_reports")
    reporter = relationship("User", back_populates="daily_reports")
    workflow = relationship(
        "DailyReportWorkflow", back_populates="report", uselist=False,
        cascade="all, delete-orphan"
    )
    evidence = relationship(
        "ReportEvidence", back_populates="report", cascade="all, delete-orphan",
        order_by="ReportEvidence.created_at"
    )
    reviews = relationship(
        "ReportReview", back_populates="report", cascade="all, delete-orphan",
        order_by="ReportReview.created_at"
    )
    requirement_checks = relationship(
        "ReportRequirementCheck", back_populates="report", cascade="all, delete-orphan",
        order_by="ReportRequirementCheck.id"
    )
    progress_entry = relationship(
        "ReportProgressEntry", foreign_keys="ReportProgressEntry.report_id",
        back_populates="report", uselist=False, cascade="all, delete-orphan"
    )


class TaskSpecification(Base):
    __tablename__ = "task_specifications"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), unique=True, nullable=False)
    wbs_code = Column(String(80), nullable=False)
    work_package = Column(String(200), nullable=True)
    location = Column(String(200), nullable=True)
    acceptance_criteria = Column(Text, nullable=False)
    reporting_instructions = Column(Text, nullable=True)
    required_photo_count = Column(Integer, default=0, nullable=False)
    required_document_count = Column(Integer, default=0, nullable=False)
    template_name = Column(String(160), default="Laporan Harian Lapangan", nullable=False)
    template_version = Column(String(30), default="1.0", nullable=False)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="specification")
    source_document = relationship("Document", foreign_keys=[source_document_id])


class TaskRequirement(Base):
    __tablename__ = "task_requirements"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    code = Column(String(80), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    requirement_type = Column(String(50), default="checklist", nullable=False)
    validation_rule = Column(String(80), default="manual_confirmation", nullable=False)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    sequence = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="requirements")


class TaskMaterialSpecification(Base):
    __tablename__ = "task_material_specifications"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    material_code = Column(String(80), nullable=True, index=True)
    material_name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    technical_specification = Column(Text, nullable=True)
    standard_reference = Column(String(200), nullable=True)
    grade = Column(String(100), nullable=True)
    approved_manufacturer = Column(String(200), nullable=True)
    dimensions = Column(String(160), nullable=True)
    unit = Column(String(30), nullable=True)
    planned_quantity = Column(Float, nullable=True)
    certificate_required = Column(Boolean, default=False, nullable=False)
    test_required = Column(Boolean, default=False, nullable=False)
    approval_required = Column(Boolean, default=True, nullable=False)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    source_page = Column(String(40), nullable=True)
    revision = Column(String(40), nullable=True)
    sequence = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="materials")
    source_document = relationship("Document", foreign_keys=[source_document_id])


class TaskControl(Base):
    __tablename__ = "task_controls"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), unique=True, nullable=False, index=True)
    planned_start = Column(DateTime, nullable=True)
    planned_finish = Column(DateTime, nullable=True)
    location = Column(String(200), nullable=True)
    unit = Column(String(30), nullable=True)
    planned_quantity = Column(Float, nullable=True)
    actual_quantity = Column(Float, default=0.0, nullable=False)
    weight_percent = Column(Float, nullable=True)
    boq_value = Column(Float, default=0.0, nullable=False)
    budget_cost = Column(Float, default=0.0, nullable=False)
    actual_cost = Column(Float, default=0.0, nullable=False)
    internal_material_cost = Column(Float, default=0.0, nullable=False)
    internal_labor_cost = Column(Float, default=0.0, nullable=False)
    internal_equipment_cost = Column(Float, default=0.0, nullable=False)
    internal_overhead_cost = Column(Float, default=0.0, nullable=False)
    internal_risk_cost = Column(Float, default=0.0, nullable=False)
    planned_manpower = Column(Integer, nullable=True)
    planned_equipment = Column(Text, nullable=True)
    revision_attention_required = Column(Boolean, default=False, nullable=False)
    revision_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="control", foreign_keys=[task_id])


class VendorProfile(Base):
    __tablename__ = "vendor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    vendor_name = Column(String(200), nullable=False)
    specialty = Column(String(120), nullable=False, index=True)
    location = Column(String(200), nullable=True)
    contact_name = Column(String(120), nullable=True)
    contact_phone = Column(String(40), nullable=True)
    is_approved = Column(Boolean, default=True, nullable=False)
    rating = Column(Float, default=80.0, nullable=False)
    quality_score = Column(Float, default=80.0, nullable=False)
    delivery_score = Column(Float, default=80.0, nullable=False)
    safety_score = Column(Float, default=80.0, nullable=False)
    capacity_score = Column(Float, default=80.0, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="vendor_profiles", foreign_keys=[project_id])
    rate_cards = relationship(
        "VendorRateCard", back_populates="vendor", cascade="all, delete-orphan",
        order_by="VendorRateCard.unit_price",
    )


class VendorRateCard(Base):
    __tablename__ = "vendor_rate_cards"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendor_profiles.id"), nullable=False, index=True)
    work_category = Column(String(120), nullable=False, index=True)
    work_keywords = Column(Text, nullable=True)
    unit = Column(String(30), nullable=False)
    unit_price = Column(Float, nullable=False)
    currency = Column(String(10), default="IDR", nullable=False)
    min_quantity = Column(Float, nullable=True)
    mobilization_cost = Column(Float, default=0.0, nullable=False)
    lead_time_days = Column(Integer, default=7, nullable=False)
    includes_material = Column(Boolean, default=True, nullable=False)
    includes_labor = Column(Boolean, default=True, nullable=False)
    includes_equipment = Column(Boolean, default=False, nullable=False)
    risk_multiplier = Column(Float, default=1.0, nullable=False)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship("VendorProfile", back_populates="rate_cards", foreign_keys=[vendor_id])


class ProductivityBenchmark(Base):
    __tablename__ = "productivity_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "work_category", "unit", "crew_size", "source_label",
            name="uq_productivity_benchmark_scope",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    work_category = Column(String(120), nullable=False, index=True)
    work_keywords = Column(Text, nullable=True)
    unit = Column(String(30), nullable=False)
    output_per_day = Column(Float, nullable=False)
    crew_size = Column(Integer, default=1, nullable=False)
    labor_cost_per_day = Column(Float, default=0.0, nullable=False)
    equipment_cost_per_day = Column(Float, default=0.0, nullable=False)
    material_cost_per_unit = Column(Float, default=0.0, nullable=False)
    overhead_percent = Column(Float, default=8.0, nullable=False)
    risk_percent = Column(Float, default=5.0, nullable=False)
    confidence_score = Column(Float, default=75.0, nullable=False)
    source_label = Column(String(120), default="manual", nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="productivity_benchmarks", foreign_keys=[project_id])


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    depends_on_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    dependency_type = Column(String(30), default="finish_to_start", nullable=False)
    lag_days = Column(Integer, default=0, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", foreign_keys=[task_id])
    predecessor = relationship("Task", foreign_keys=[depends_on_task_id])


class MaterialApproval(Base):
    __tablename__ = "material_approvals"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(
        Integer, ForeignKey("task_material_specifications.id"), unique=True,
        nullable=False, index=True,
    )
    status = Column(String(30), default="pending", nullable=False, index=True)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    material = relationship("TaskMaterialSpecification", foreign_keys=[material_id])
    submitter = relationship("User", foreign_keys=[submitted_by])
    decision_maker = relationship("User", foreign_keys=[decided_by])


class InspectionRequest(Base):
    __tablename__ = "inspection_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    inspection_type = Column(String(50), default="work_inspection", nullable=False)
    title = Column(String(220), nullable=False)
    status = Column(String(30), default="pending", nullable=False, index=True)
    is_required = Column(Boolean, default=True, nullable=False)
    due_date = Column(DateTime, nullable=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    inspected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    inspected_at = Column(DateTime, nullable=True)
    result_note = Column(Text, nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", foreign_keys=[project_id])
    task = relationship("Task", foreign_keys=[task_id])
    requester = relationship("User", foreign_keys=[requested_by])
    inspector = relationship("User", foreign_keys=[inspected_by])
    document = relationship("Document", foreign_keys=[document_id])


class NonConformance(Base):
    __tablename__ = "non_conformances"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    inspection_id = Column(Integer, ForeignKey("inspection_requests.id"), nullable=True, index=True)
    ncr_number = Column(String(80), nullable=False, index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(30), default="major", nullable=False)
    status = Column(String(40), default="open", nullable=False, index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    corrective_action = Column(Text, nullable=True)
    closed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", foreign_keys=[project_id])
    task = relationship("Task", foreign_keys=[task_id])
    inspection = relationship("InspectionRequest", foreign_keys=[inspection_id])
    assignee = relationship("User", foreign_keys=[assigned_to])
    closer = relationship("User", foreign_keys=[closed_by])


class ReportProgressEntry(Base):
    __tablename__ = "report_progress_entries"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("daily_reports.id"), unique=True, nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    quantity_this_report = Column(Float, default=0.0, nullable=False)
    cost_this_report = Column(Float, default=0.0, nullable=False)
    cumulative_quantity = Column(Float, default=0.0, nullable=False)
    progress_after_approval = Column(Float, default=0.0, nullable=False)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    report = relationship("DailyReport", back_populates="progress_entry", foreign_keys=[report_id])
    task = relationship("Task", foreign_keys=[task_id])


class HandoverItem(Base):
    __tablename__ = "handover_items"
    __table_args__ = (
        UniqueConstraint("project_id", "source_type", "source_id", name="uq_handover_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    category = Column(String(60), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(30), default="collected", nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    source_type = Column(String(50), nullable=False)
    source_id = Column(Integer, nullable=False)
    auto_collected = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", foreign_keys=[project_id])
    task = relationship("Task", foreign_keys=[task_id])
    document = relationship("Document", foreign_keys=[document_id])


class DailyReportWorkflow(Base):
    __tablename__ = "daily_report_workflows"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("daily_reports.id"), unique=True, nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    status = Column(Enum(ReportStatus), default=ReportStatus.DRAFT, nullable=False)
    validation_passed = Column(Boolean, default=False, nullable=False)
    validation_score = Column(Float, default=0.0, nullable=False)
    validation_result = Column(Text, nullable=True)
    revision_note = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    report = relationship("DailyReport", back_populates="workflow")
    task = relationship("Task", foreign_keys=[task_id])
    verifier = relationship("User", foreign_keys=[verified_by])
    approver = relationship("User", foreign_keys=[approved_by])


class ReportEvidence(Base):
    __tablename__ = "report_evidence"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("daily_reports.id"), nullable=False, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    evidence_type = Column(Enum(EvidenceType), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    caption = Column(Text, nullable=True)
    telegram_message_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    report = relationship("DailyReport", back_populates="evidence")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class ReportReview(Base):
    __tablename__ = "report_reviews"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("daily_reports.id"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_status = Column(String(50), nullable=False)
    to_status = Column(String(50), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    report = relationship("DailyReport", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class ReportRequirementCheck(Base):
    __tablename__ = "report_requirement_checks"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("daily_reports.id"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("task_requirements.id"), nullable=False)
    confirmed = Column(Boolean, default=False, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    report = relationship("DailyReport", back_populates="requirement_checks")
    requirement = relationship("TaskRequirement", foreign_keys=[requirement_id])


# ─────────────────────────────────────────────
# NOTIFICATION MODEL
# ─────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info")   # info, warning, alert, deadline
    is_read = Column(Boolean, default=False)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    related_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    sent_to_telegram = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    feature_key = Column(String(80), unique=True, nullable=False, index=True)
    label = Column(String(120), nullable=False)
    category = Column(String(60), default="menu", nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    is_core = Column(Boolean, default=False, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updater = relationship("User", foreign_keys=[updated_by])


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    status = Column(String(30), default="trial", nullable=False, index=True)
    plan_key = Column(String(40), default="professional", nullable=False, index=True)
    contact_name = Column(String(120), nullable=True)
    contact_email = Column(String(120), nullable=True)
    contact_phone = Column(String(40), nullable=True)
    billing_contact_email = Column(String(120), nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_starts_at = Column(DateTime, nullable=True)
    subscription_ends_at = Column(DateTime, nullable=True)
    max_users = Column(Integer, nullable=True)
    active_project_limit = Column(Integer, nullable=True)
    storage_limit_gb = Column(Float, nullable=True)
    ai_token_limit_monthly = Column(Integer, nullable=True)
    automation_run_limit_monthly = Column(Integer, nullable=True)
    onboarding_stage = Column(String(50), default="discovery", nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    entitlements = relationship(
        "TenantFeatureEntitlement", back_populates="tenant", cascade="all, delete-orphan"
    )
    usage_records = relationship(
        "TenantUsageRecord", back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantFeatureEntitlement(Base):
    __tablename__ = "tenant_feature_entitlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "feature_key", name="uq_tenant_feature_entitlement"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    feature_key = Column(String(80), ForeignKey("feature_flags.feature_key"), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    source = Column(String(30), default="plan", nullable=False)
    notes = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="entitlements")
    feature = relationship("FeatureFlag", foreign_keys=[feature_key])
    updater = relationship("User", foreign_keys=[updated_by])


class TenantUsageRecord(Base):
    __tablename__ = "tenant_usage_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric_key", "period", name="uq_tenant_usage_period"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    metric_key = Column(String(60), nullable=False, index=True)
    period = Column(String(7), nullable=False, index=True)
    used_value = Column(Float, default=0, nullable=False)
    limit_value = Column(Float, nullable=True)
    unit = Column(String(30), default="count", nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="usage_records")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    approval_type = Column(Enum(ApprovalType), default=ApprovalType.OTHER, nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(Integer, nullable=True)
    due_date = Column(DateTime, nullable=True)
    decision_note = Column(Text, nullable=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", foreign_keys=[project_id])
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approver_id])
    decision_maker = relationship("User", foreign_keys=[decided_by])


class DocumentSyncSession(Base):
    __tablename__ = "document_sync_sessions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=True)
    status = Column(Enum(DocumentSyncStatus), default=DocumentSyncStatus.DRAFT, nullable=False, index=True)
    plan_json = Column(Text, nullable=False)
    selected_change_ids = Column(Text, nullable=True)
    generated_with_ai = Column(Boolean, default=False, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    applied_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    requested_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", foreign_keys=[document_id])
    project = relationship("Project", foreign_keys=[project_id])
    creator = relationship("User", foreign_keys=[created_by])
    approval = relationship("ApprovalRequest", foreign_keys=[approval_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    applier = relationship("User", foreign_keys=[applied_by])


class CommunicationItem(Base):
    __tablename__ = "communication_items"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    communication_type = Column(Enum(CommunicationType), default=CommunicationType.ISSUE, nullable=False)
    status = Column(Enum(CommunicationStatus), default=CommunicationStatus.OPEN, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    subject = Column(String(220), nullable=False)
    description = Column(Text, nullable=True)
    question = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    discipline = Column(String(120), nullable=True)
    location = Column(String(160), nullable=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    related_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    due_date = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="communications")
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    related_task = relationship("Task", foreign_keys=[related_task_id])
    related_document = relationship("Document", foreign_keys=[related_document_id])
    messages = relationship(
        "CommunicationMessage", back_populates="communication", cascade="all, delete-orphan",
        order_by="CommunicationMessage.created_at"
    )
    attachments = relationship(
        "CommunicationAttachment", back_populates="communication", cascade="all, delete-orphan",
        order_by="CommunicationAttachment.created_at"
    )
    mentions = relationship(
        "CommunicationMention", back_populates="communication", cascade="all, delete-orphan"
    )
    read_receipts = relationship(
        "CommunicationReadReceipt", back_populates="communication", cascade="all, delete-orphan"
    )
    links = relationship(
        "CommunicationLink", back_populates="communication", cascade="all, delete-orphan"
    )


class CommunicationMessage(Base):
    __tablename__ = "communication_messages"

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communication_items.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message_type = Column(String(40), default="comment", nullable=False, index=True)
    message = Column(Text, nullable=False)
    telegram_message_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    communication = relationship("CommunicationItem", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id])
    attachments = relationship(
        "CommunicationAttachment", back_populates="message", cascade="all, delete-orphan"
    )
    mentions = relationship(
        "CommunicationMention", back_populates="message", cascade="all, delete-orphan"
    )


class CommunicationAttachment(Base):
    __tablename__ = "communication_attachments"

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communication_items.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("communication_messages.id"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    caption = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    communication = relationship("CommunicationItem", back_populates="attachments")
    message = relationship("CommunicationMessage", back_populates="attachments")
    document = relationship("Document", foreign_keys=[document_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])


class CommunicationMention(Base):
    __tablename__ = "communication_mentions"
    __table_args__ = (
        UniqueConstraint("message_id", "mentioned_user_id", name="uq_communication_message_mention_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communication_items.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("communication_messages.id"), nullable=False, index=True)
    mentioned_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    communication = relationship("CommunicationItem", back_populates="mentions")
    message = relationship("CommunicationMessage", back_populates="mentions")
    mentioned_user = relationship("User", foreign_keys=[mentioned_user_id])
    creator = relationship("User", foreign_keys=[created_by])


class CommunicationReadReceipt(Base):
    __tablename__ = "communication_read_receipts"
    __table_args__ = (
        UniqueConstraint("communication_id", "user_id", name="uq_communication_read_receipt_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communication_items.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    last_read_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    communication = relationship("CommunicationItem", back_populates="read_receipts")
    user = relationship("User", foreign_keys=[user_id])


class CommunicationLink(Base):
    __tablename__ = "communication_links"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_communication_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communication_items.id"), nullable=False, index=True)
    source_type = Column(String(60), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    label = Column(String(220), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    communication = relationship("CommunicationItem", back_populates="links")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", foreign_keys=[task_id])
    user = relationship("User", foreign_keys=[user_id])


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", foreign_keys=[task_id])
    document = relationship("Document", foreign_keys=[document_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(String(80), nullable=True)
    summary = Column(Text, nullable=True)
    before_data = Column(Text, nullable=True)
    after_data = Column(Text, nullable=True)
    channel = Column(String(30), default="web")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    actor = relationship("User", foreign_keys=[actor_id])
    project = relationship("Project", foreign_keys=[project_id])


# -----------------------------------------------------------------------------
# DIGITAL TWIN DATASET
# -----------------------------------------------------------------------------

class DigitalTwinNode(Base):
    __tablename__ = "digital_twin_nodes"
    __table_args__ = (
        UniqueConstraint("project_id", "uid", name="uq_digital_twin_node_project_uid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    uid = Column(String(120), nullable=False, index=True)
    node_type = Column(Enum(DigitalTwinNodeType), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(120), nullable=True, index=True)
    description = Column(Text, nullable=True)
    source_table = Column(String(120), nullable=True)
    source_id = Column(String(120), nullable=True)
    discipline = Column(String(120), nullable=True)
    zone = Column(String(120), nullable=True)
    floor = Column(String(80), nullable=True)
    revision = Column(String(80), nullable=True)
    status = Column(String(80), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="digital_twin_nodes")
    outgoing_relationships = relationship(
        "DigitalTwinRelationship",
        foreign_keys="DigitalTwinRelationship.from_node_id",
        back_populates="from_node",
        cascade="all, delete-orphan",
    )
    incoming_relationships = relationship(
        "DigitalTwinRelationship",
        foreign_keys="DigitalTwinRelationship.to_node_id",
        back_populates="to_node",
        cascade="all, delete-orphan",
    )
    reasoning_examples = relationship(
        "DigitalTwinReasoningExample",
        back_populates="related_node",
    )
    validation_issues = relationship(
        "DigitalTwinValidationIssue",
        back_populates="node",
    )


class DigitalTwinRelationship(Base):
    __tablename__ = "digital_twin_relationships"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "relationship_uid",
            name="uq_digital_twin_relationship_project_uid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    relationship_uid = Column(String(255), nullable=False, index=True)
    from_node_id = Column(Integer, ForeignKey("digital_twin_nodes.id"), nullable=False, index=True)
    to_node_id = Column(Integer, ForeignKey("digital_twin_nodes.id"), nullable=False, index=True)
    relationship_type = Column(String(80), nullable=False, index=True)
    relationship_name = Column(String(160), nullable=False)
    reason = Column(Text, nullable=True)
    rule_reference = Column(String(160), nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="digital_twin_relationships")
    from_node = relationship(
        "DigitalTwinNode",
        foreign_keys=[from_node_id],
        back_populates="outgoing_relationships",
    )
    to_node = relationship(
        "DigitalTwinNode",
        foreign_keys=[to_node_id],
        back_populates="incoming_relationships",
    )
    validation_issues = relationship(
        "DigitalTwinValidationIssue",
        back_populates="relationship",
    )


class DigitalTwinRule(Base):
    __tablename__ = "digital_twin_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "rule_uid", name="uq_digital_twin_rule_project_uid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    rule_uid = Column(String(120), nullable=False, index=True)
    category = Column(
        Enum(DigitalTwinRuleCategory),
        default=DigitalTwinRuleCategory.GENERAL,
        nullable=False,
    )
    title = Column(String(255), nullable=False)
    condition_text = Column(Text, nullable=False)
    action_text = Column(Text, nullable=False)
    machine_condition_json = Column(Text, nullable=True)
    reference = Column(String(255), nullable=True)
    severity = Column(String(30), default="medium", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="digital_twin_rules")


class DigitalTwinReasoningExample(Base):
    __tablename__ = "digital_twin_reasoning_examples"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "example_uid",
            name="uq_digital_twin_reasoning_project_uid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    example_uid = Column(String(120), nullable=False, index=True)
    question = Column(Text, nullable=False)
    context = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    reference = Column(String(255), nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    related_node_id = Column(Integer, ForeignKey("digital_twin_nodes.id"), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="digital_twin_reasoning_examples")
    related_node = relationship("DigitalTwinNode", back_populates="reasoning_examples")


class DigitalTwinValidationIssue(Base):
    __tablename__ = "digital_twin_validation_issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("digital_twin_nodes.id"), nullable=True, index=True)
    relationship_id = Column(
        Integer,
        ForeignKey("digital_twin_relationships.id"),
        nullable=True,
        index=True,
    )
    code = Column(String(120), nullable=False, index=True)
    severity = Column(String(30), nullable=False, index=True)
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="digital_twin_validation_issues")
    node = relationship("DigitalTwinNode", back_populates="validation_issues")
    relationship = relationship(
        "DigitalTwinRelationship",
        back_populates="validation_issues",
    )
