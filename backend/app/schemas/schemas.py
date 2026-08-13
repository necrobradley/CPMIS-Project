"""
Pydantic Schemas - AI CPMIS
Validasi request & response untuk semua endpoint.
"""
from datetime import datetime
from typing import Any, Dict, Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.user import (
    UserRole, ProjectStatus, TaskStatus, TaskPriority, DocumentType,
    ApprovalStatus, ApprovalType, CommunicationType, CommunicationStatus,
    ReportStatus, EvidenceType, DocumentSyncStatus,
    DigitalTwinNodeType, DigitalTwinRuleCategory,
)


# ─────────────────────────────────────────────
# AUTH SCHEMAS
# ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    # Login is also used by built-in demo accounts such as
    # admin.project@demo.local. EmailStr intentionally rejects the reserved
    # .local suffix even though it is a valid internal account identifier.
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        email = value.strip().lower()
        if email.count("@") != 1 or any(character.isspace() for character in email):
            raise ValueError("Format email tidak valid")
        local_part, domain = email.split("@", 1)
        if not local_part or not domain or "." not in domain:
            raise ValueError("Format email tidak valid")
        return email


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_min_length(cls, v):
        if len(v) < 10:
            raise ValueError("Password baru minimal 10 karakter")
        if not any(character.isupper() for character in v) or not any(character.islower() for character in v) or not any(character.isdigit() for character in v):
            raise ValueError("Password wajib memiliki huruf besar, huruf kecil, dan angka")
        return v


class EmailRequest(BaseModel):
    email: EmailStr


class EmailTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class PasswordTokenRequest(EmailTokenRequest):
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(character.isupper() for character in value):
            raise ValueError("Password wajib memiliki huruf besar")
        if not any(character.islower() for character in value):
            raise ValueError("Password wajib memiliki huruf kecil")
        if not any(character.isdigit() for character in value):
            raise ValueError("Password wajib memiliki angka")
        return value


# ─────────────────────────────────────────────
# USER SCHEMAS
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    role: UserRole = UserRole.STAFF
    phone: Optional[str] = None
    division_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError("Password minimal 8 karakter")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    division_id: Optional[int] = None
    telegram_id: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    role: UserRole
    phone: Optional[str]
    division_id: Optional[int]
    telegram_id: Optional[str]
    avatar_url: Optional[str] = None
    is_active: bool
    email_verified_at: Optional[datetime] = None
    email_verification_required: bool = False
    must_set_password: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class UserProjectSetupCreate(UserCreate):
    telegram_id: Optional[str] = None
    project_id: Optional[int] = None
    project_division_id: Optional[int] = None
    project_role: str = "staff"


class UserProjectSetupUpdate(BaseModel):
    role: Optional[UserRole] = None
    phone: Optional[str] = None
    telegram_id: Optional[str] = None
    is_active: Optional[bool] = None
    project_id: Optional[int] = None
    project_division_id: Optional[int] = None
    project_role: Optional[str] = None


class UserSummaryResponse(BaseModel):
    id: int
    name: str
    role: UserRole
    division_id: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# DIGITAL TWIN DATASET SCHEMAS
# ─────────────────────────────────────────────

class DigitalTwinNodeBase(BaseModel):
    uid: str = Field(..., min_length=2, max_length=120)
    node_type: DigitalTwinNodeType
    name: str = Field(..., min_length=2, max_length=255)
    code: Optional[str] = None
    description: Optional[str] = None
    source_table: Optional[str] = None
    source_id: Optional[str] = None
    discipline: Optional[str] = None
    zone: Optional[str] = None
    floor: Optional[str] = None
    revision: Optional[str] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DigitalTwinNodeCreate(DigitalTwinNodeBase):
    pass


class DigitalTwinNodeResponse(DigitalTwinNodeBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DigitalTwinRelationshipCreate(BaseModel):
    relationship_uid: Optional[str] = None
    from_uid: str
    to_uid: str
    relationship_type: str = Field(..., min_length=2, max_length=80)
    relationship_name: str = Field(..., min_length=2, max_length=160)
    reason: Optional[str] = None
    rule_reference: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DigitalTwinRelationshipResponse(BaseModel):
    id: int
    relationship_uid: str
    project_id: int
    from_node_id: int
    to_node_id: int
    from_uid: str
    to_uid: str
    relationship_type: str
    relationship_name: str
    reason: Optional[str]
    rule_reference: Optional[str]
    confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime]


class DigitalTwinRuleCreate(BaseModel):
    rule_uid: str = Field(..., min_length=2, max_length=120)
    category: DigitalTwinRuleCategory = DigitalTwinRuleCategory.GENERAL
    title: str = Field(..., min_length=2, max_length=255)
    condition_text: str
    action_text: str
    machine_condition: Dict[str, Any] = Field(default_factory=dict)
    reference: Optional[str] = None
    severity: str = "medium"
    is_active: bool = True


class DigitalTwinRuleResponse(DigitalTwinRuleCreate):
    id: int
    project_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DigitalTwinReasoningExampleCreate(BaseModel):
    example_uid: str = Field(..., min_length=2, max_length=120)
    question: str
    context: str
    reasoning: str
    answer: str
    reference: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    related_node_uid: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DigitalTwinReasoningExampleResponse(DigitalTwinReasoningExampleCreate):
    id: int
    project_id: int
    related_node_id: Optional[int]
    created_at: datetime


class DigitalTwinDatasetImport(BaseModel):
    nodes: List[DigitalTwinNodeCreate] = Field(default_factory=list)
    relationships: List[DigitalTwinRelationshipCreate] = Field(default_factory=list)
    rules: List[DigitalTwinRuleCreate] = Field(default_factory=list)
    reasoning_examples: List[DigitalTwinReasoningExampleCreate] = Field(default_factory=list)


class DigitalTwinImportSummary(BaseModel):
    project_id: int
    nodes_upserted: int
    relationships_upserted: int
    rules_upserted: int
    reasoning_examples_upserted: int


class DigitalTwinValidationIssueResponse(BaseModel):
    code: str
    severity: str
    message: str
    node_uid: Optional[str] = None
    relationship_uid: Optional[str] = None


class DigitalTwinValidationSummary(BaseModel):
    project_id: int
    passed: bool
    issue_count: int
    issues: List[DigitalTwinValidationIssueResponse]


class DigitalTwinGraphResponse(BaseModel):
    project_id: int
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]
    reasoning_examples: List[Dict[str, Any]]


# ─────────────────────────────────────────────
# PROJECT SCHEMAS
# ─────────────────────────────────────────────

class ProjectCreate(BaseModel):
    project_name: str
    description: Optional[str] = None
    location: Optional[str] = None
    contract_value: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    contract_value: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[ProjectStatus] = None
    progress_percent: Optional[float] = None


class ProjectResponse(BaseModel):
    id: int
    project_name: str
    description: Optional[str]
    location: Optional[str]
    contract_value: Optional[float]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: ProjectStatus
    owner_id: int
    progress_percent: float
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# DIVISION SCHEMAS
# ─────────────────────────────────────────────

class DivisionCreate(BaseModel):
    division_name: str
    description: Optional[str] = None
    manager_id: Optional[int] = None


class DivisionUpdate(BaseModel):
    division_name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[int] = None


class DivisionResponse(BaseModel):
    id: int
    division_name: str
    description: Optional[str]
    project_id: int
    manager_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectMemberCreate(BaseModel):
    user_id: int
    division_id: Optional[int] = None
    project_role: str = "staff"


class ProjectMemberUpdate(BaseModel):
    division_id: Optional[int] = None
    project_role: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectMemberResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    division_id: Optional[int]
    project_role: str
    is_active: bool
    joined_at: datetime
    user: UserResponse
    division: Optional[DivisionResponse] = None

    class Config:
        from_attributes = True


class UserProjectSetupResponse(BaseModel):
    user: UserResponse
    membership: Optional[ProjectMemberResponse] = None
    invitation_sent: bool = False
    invitation_message: Optional[str] = None


class ProjectMemberRoleCatalogResponse(BaseModel):
    code: str
    label: str
    category: str
    category_label: str
    default_division: str
    responsibility: str
    access_hint: str
    can_be_task_pic: bool
    requires_division: bool


# ─────────────────────────────────────────────
# TASK SCHEMAS
# ─────────────────────────────────────────────

class ProjectRolePolicyUpdate(BaseModel):
    enabled: bool


class ProjectRolePolicyResponse(ProjectMemberRoleCatalogResponse):
    project_id: int
    enabled: bool
    updated_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TaskRequirementCreate(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    requirement_type: str = "checklist"
    validation_rule: str = "manual_confirmation"
    is_mandatory: bool = True
    sequence: int = 0


class TaskRequirementResponse(TaskRequirementCreate):
    id: int
    task_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TaskMaterialCreate(BaseModel):
    material_code: Optional[str] = None
    material_name: str
    category: Optional[str] = None
    technical_specification: Optional[str] = None
    standard_reference: Optional[str] = None
    grade: Optional[str] = None
    approved_manufacturer: Optional[str] = None
    dimensions: Optional[str] = None
    unit: Optional[str] = None
    planned_quantity: Optional[float] = None
    certificate_required: bool = False
    test_required: bool = False
    approval_required: bool = True
    source_document_id: Optional[int] = None
    source_page: Optional[str] = None
    revision: Optional[str] = None
    sequence: int = 0


class TaskMaterialUpdate(BaseModel):
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    category: Optional[str] = None
    technical_specification: Optional[str] = None
    standard_reference: Optional[str] = None
    grade: Optional[str] = None
    approved_manufacturer: Optional[str] = None
    dimensions: Optional[str] = None
    unit: Optional[str] = None
    planned_quantity: Optional[float] = None
    certificate_required: Optional[bool] = None
    test_required: Optional[bool] = None
    approval_required: Optional[bool] = None
    source_document_id: Optional[int] = None
    source_page: Optional[str] = None
    revision: Optional[str] = None
    sequence: Optional[int] = None


class TaskMaterialResponse(TaskMaterialCreate):
    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskSpecificationInput(BaseModel):
    wbs_code: str
    work_package: Optional[str] = None
    location: Optional[str] = None
    acceptance_criteria: str
    reporting_instructions: Optional[str] = None
    required_photo_count: int = 0
    required_document_count: int = 0
    template_name: str = "Laporan Harian Lapangan"
    template_version: str = "1.0"
    source_document_id: Optional[int] = None


class TaskSpecificationResponse(TaskSpecificationInput):
    id: int
    task_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: int
    division_id: Optional[int] = None
    assigned_to: Optional[int] = None
    parent_task_id: Optional[int] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: Optional[datetime] = None
    approval_approver_id: Optional[int] = None
    specification: Optional[TaskSpecificationInput] = None
    requirements: List[TaskRequirementCreate] = Field(default_factory=list)
    materials: List[TaskMaterialCreate] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    division_id: Optional[int] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    deadline: Optional[datetime] = None
    progress_percent: Optional[float] = None
    specification: Optional[TaskSpecificationInput] = None
    requirements: Optional[List[TaskRequirementCreate]] = None
    materials: Optional[List[TaskMaterialCreate]] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    project_id: int
    division_id: Optional[int]
    division: Optional[DivisionResponse] = None
    assigned_to: Optional[int]
    assignee: Optional[UserSummaryResponse] = None
    created_by: int
    priority: TaskPriority
    status: TaskStatus
    deadline: Optional[datetime]
    progress_percent: float
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    approval_id: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    approval_note: Optional[str] = None
    ai_generated: bool
    ai_source: Optional[str] = None
    parent_task_id: Optional[int] = None
    specification: Optional[TaskSpecificationResponse] = None
    requirements: List[TaskRequirementResponse] = Field(default_factory=list)
    materials: List[TaskMaterialResponse] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class TaskControlUpsert(BaseModel):
    planned_start: Optional[datetime] = None
    planned_finish: Optional[datetime] = None
    location: Optional[str] = None
    unit: Optional[str] = None
    planned_quantity: Optional[float] = Field(default=None, ge=0)
    weight_percent: Optional[float] = Field(default=None, ge=0, le=100)
    boq_value: Optional[float] = Field(default=None, ge=0)
    budget_cost: Optional[float] = Field(default=None, ge=0)
    internal_material_cost: Optional[float] = Field(default=None, ge=0)
    internal_labor_cost: Optional[float] = Field(default=None, ge=0)
    internal_equipment_cost: Optional[float] = Field(default=None, ge=0)
    internal_overhead_cost: Optional[float] = Field(default=None, ge=0)
    internal_risk_cost: Optional[float] = Field(default=None, ge=0)
    planned_manpower: Optional[int] = Field(default=None, ge=0)
    planned_equipment: Optional[str] = None
    revision_attention_required: Optional[bool] = None
    revision_note: Optional[str] = None


class TaskControlResponse(BaseModel):
    id: int
    task_id: int
    planned_start: Optional[datetime]
    planned_finish: Optional[datetime]
    location: Optional[str]
    unit: Optional[str]
    planned_quantity: Optional[float]
    actual_quantity: float
    weight_percent: Optional[float]
    boq_value: float
    budget_cost: float
    actual_cost: float
    internal_material_cost: float
    internal_labor_cost: float
    internal_equipment_cost: float
    internal_overhead_cost: float
    internal_risk_cost: float
    planned_manpower: Optional[int]
    planned_equipment: Optional[str]
    revision_attention_required: bool
    revision_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VendorRateCardCreate(BaseModel):
    work_category: str
    work_keywords: Optional[str] = None
    unit: str
    unit_price: float = Field(ge=0)
    currency: str = "IDR"
    min_quantity: Optional[float] = Field(default=None, ge=0)
    mobilization_cost: float = Field(default=0, ge=0)
    lead_time_days: int = Field(default=7, ge=0)
    includes_material: bool = True
    includes_labor: bool = True
    includes_equipment: bool = False
    risk_multiplier: float = Field(default=1.0, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    notes: Optional[str] = None


class VendorRateCardResponse(VendorRateCardCreate):
    id: int
    vendor_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VendorProfileCreate(BaseModel):
    vendor_name: str
    specialty: str
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    is_approved: bool = True
    rating: float = Field(default=80, ge=0, le=100)
    quality_score: float = Field(default=80, ge=0, le=100)
    delivery_score: float = Field(default=80, ge=0, le=100)
    safety_score: float = Field(default=80, ge=0, le=100)
    capacity_score: float = Field(default=80, ge=0, le=100)
    notes: Optional[str] = None
    rate_cards: List[VendorRateCardCreate] = Field(default_factory=list)


class VendorProfileUpdate(BaseModel):
    vendor_name: Optional[str] = None
    specialty: Optional[str] = None
    location: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    is_approved: Optional[bool] = None
    rating: Optional[float] = Field(default=None, ge=0, le=100)
    quality_score: Optional[float] = Field(default=None, ge=0, le=100)
    delivery_score: Optional[float] = Field(default=None, ge=0, le=100)
    safety_score: Optional[float] = Field(default=None, ge=0, le=100)
    capacity_score: Optional[float] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class VendorProfileResponse(BaseModel):
    id: int
    project_id: Optional[int]
    vendor_name: str
    specialty: str
    location: Optional[str]
    contact_name: Optional[str]
    contact_phone: Optional[str]
    is_approved: bool
    rating: float
    quality_score: float
    delivery_score: float
    safety_score: float
    capacity_score: float
    notes: Optional[str]
    rate_cards: List[VendorRateCardResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductivityBenchmarkCreate(BaseModel):
    work_category: str
    work_keywords: Optional[str] = None
    unit: str
    output_per_day: float = Field(gt=0)
    crew_size: int = Field(default=1, ge=1)
    labor_cost_per_day: float = Field(default=0, ge=0)
    equipment_cost_per_day: float = Field(default=0, ge=0)
    material_cost_per_unit: float = Field(default=0, ge=0)
    overhead_percent: float = Field(default=8, ge=0)
    risk_percent: float = Field(default=5, ge=0)
    confidence_score: float = Field(default=75, ge=0, le=100)
    source_label: str = "manual"
    notes: Optional[str] = None


class ProductivityBenchmarkUpdate(BaseModel):
    work_category: Optional[str] = None
    work_keywords: Optional[str] = None
    unit: Optional[str] = None
    output_per_day: Optional[float] = Field(default=None, gt=0)
    crew_size: Optional[int] = Field(default=None, ge=1)
    labor_cost_per_day: Optional[float] = Field(default=None, ge=0)
    equipment_cost_per_day: Optional[float] = Field(default=None, ge=0)
    material_cost_per_unit: Optional[float] = Field(default=None, ge=0)
    overhead_percent: Optional[float] = Field(default=None, ge=0)
    risk_percent: Optional[float] = Field(default=None, ge=0)
    confidence_score: Optional[float] = Field(default=None, ge=0, le=100)
    source_label: Optional[str] = None
    notes: Optional[str] = None


class ProductivityBenchmarkResponse(ProductivityBenchmarkCreate):
    id: int
    project_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: int
    dependency_type: Literal["finish_to_start", "start_to_start"] = "finish_to_start"
    lag_days: int = Field(default=0, ge=0)


class TaskDependencyResponse(TaskDependencyCreate):
    id: int
    task_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialApprovalDecision(BaseModel):
    status: Literal["pending", "submitted", "approved", "rejected"]
    note: Optional[str] = None


class MaterialApprovalResponse(BaseModel):
    id: int
    material_id: int
    status: str
    submitted_by: Optional[int]
    submitted_at: Optional[datetime]
    decided_by: Optional[int]
    decided_at: Optional[datetime]
    note: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionCreate(BaseModel):
    project_id: int
    task_id: int
    inspection_type: Literal["itp", "work_inspection", "material_test", "test_result"] = "work_inspection"
    title: str
    is_required: bool = True
    due_date: Optional[datetime] = None
    document_id: Optional[int] = None


class InspectionDecision(BaseModel):
    status: Literal["passed", "failed", "cancelled"]
    result_note: Optional[str] = None
    ncr_title: Optional[str] = None
    ncr_severity: Literal["minor", "major", "critical"] = "major"
    ncr_assigned_to: Optional[int] = None
    ncr_due_date: Optional[datetime] = None


class InspectionResponse(BaseModel):
    id: int
    project_id: int
    task_id: int
    inspection_type: str
    title: str
    status: str
    is_required: bool
    due_date: Optional[datetime]
    requested_by: int
    inspected_by: Optional[int]
    inspected_at: Optional[datetime]
    result_note: Optional[str]
    document_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NonConformanceUpdate(BaseModel):
    status: Optional[Literal["open", "corrective_action", "ready_for_close", "closed"]] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    corrective_action: Optional[str] = None


class NonConformanceResponse(BaseModel):
    id: int
    project_id: int
    task_id: int
    inspection_id: Optional[int]
    ncr_number: str
    title: str
    description: Optional[str]
    severity: str
    status: str
    assigned_to: Optional[int]
    due_date: Optional[datetime]
    corrective_action: Optional[str]
    closed_by: Optional[int]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# DAILY REPORT SCHEMAS
# ─────────────────────────────────────────────

class RequirementConfirmationInput(BaseModel):
    requirement_id: int
    confirmed: bool
    note: Optional[str] = None


class RequirementConfirmationResponse(RequirementConfirmationInput):
    id: int
    report_id: int

    class Config:
        from_attributes = True


class DailyReportCreate(BaseModel):
    project_id: int
    task_id: int
    report_text: str
    weather: Optional[str] = None
    manpower_count: Optional[int] = None
    work_progress: Optional[str] = None
    issues: Optional[str] = None
    actual_quantity: float = Field(default=0, ge=0)
    actual_cost: float = Field(default=0, ge=0)
    requirement_confirmations: List[RequirementConfirmationInput] = Field(default_factory=list)

    @field_validator("report_text")
    @classmethod
    def report_text_min_length(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Laporan kegiatan minimal 10 karakter")
        return v.strip()


class DailyReportUpdate(BaseModel):
    report_text: Optional[str] = None
    weather: Optional[str] = None
    manpower_count: Optional[int] = None
    work_progress: Optional[str] = None
    issues: Optional[str] = None
    actual_quantity: Optional[float] = Field(default=None, ge=0)
    actual_cost: Optional[float] = Field(default=None, ge=0)
    requirement_confirmations: Optional[List[RequirementConfirmationInput]] = None


class ReportProgressResponse(BaseModel):
    report_id: int
    task_id: int
    quantity_this_report: float
    cost_this_report: float
    cumulative_quantity: float
    progress_after_approval: float
    applied_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportEvidenceResponse(BaseModel):
    id: int
    report_id: int
    uploaded_by: int
    evidence_type: EvidenceType
    file_name: str
    file_size: Optional[int]
    mime_type: Optional[str]
    caption: Optional[str]
    telegram_message_id: Optional[str]
    download_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportReviewResponse(BaseModel):
    id: int
    reviewer_id: int
    from_status: str
    to_status: str
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReportWorkflowResponse(BaseModel):
    task_id: int
    status: ReportStatus
    validation_passed: bool
    validation_score: float
    validation_result: Optional[str]
    revision_note: Optional[str]
    submitted_at: Optional[datetime]
    verified_by: Optional[int]
    verified_at: Optional[datetime]
    approved_by: Optional[int]
    approved_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportDecision(BaseModel):
    decision: Literal["needs_revision", "verified", "approved"]
    note: Optional[str] = None


class DailyReportResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    report_date: datetime
    report_text: str
    weather: Optional[str]
    manpower_count: Optional[int]
    work_progress: Optional[str]
    issues: Optional[str]
    ai_summary: Optional[str]
    ai_risks: Optional[str]
    workflow: Optional[ReportWorkflowResponse] = None
    evidence: List[ReportEvidenceResponse] = Field(default_factory=list)
    reviews: List[ReportReviewResponse] = Field(default_factory=list)
    requirement_checks: List[RequirementConfirmationResponse] = Field(default_factory=list)
    progress_entry: Optional[ReportProgressResponse] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TelegramAutoGroupPreviewRequest(BaseModel):
    message: str = Field(..., min_length=3)


class TelegramAutoGroupCandidate(BaseModel):
    task_id: int
    title: str
    wbs_code: Optional[str] = None
    project_id: int
    project_name: str
    confidence: float
    reasons: List[str] = Field(default_factory=list)


class TelegramAutoGroupPreviewResponse(BaseModel):
    matched: bool
    confidence: float
    threshold: float
    task_id: Optional[int] = None
    title: Optional[str] = None
    wbs_code: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    candidates: List[TelegramAutoGroupCandidate] = Field(default_factory=list)
    parsed_fields: dict


# ─────────────────────────────────────────────
# GENERAL SCHEMAS
# ─────────────────────────────────────────────

class TaskCommentCreate(BaseModel):
    comment: str


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    comment: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskAttachmentResponse(BaseModel):
    id: int
    task_id: int
    document_id: Optional[int]
    uploaded_by: int
    file_name: str
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovalCreate(BaseModel):
    project_id: int
    title: str
    description: Optional[str] = None
    approval_type: ApprovalType = ApprovalType.OTHER
    approver_id: Optional[int] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    due_date: Optional[datetime] = None


class ApprovalDecision(BaseModel):
    status: ApprovalStatus
    decision_note: Optional[str] = None

    @field_validator("status")
    @classmethod
    def only_terminal_status(cls, v):
        if v not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED):
            raise ValueError("Status keputusan harus approved, rejected, atau cancelled")
        return v


class ApprovalResponse(BaseModel):
    id: int
    project_id: int
    requested_by: int
    approver_id: Optional[int]
    title: str
    description: Optional[str]
    approval_type: ApprovalType
    status: ApprovalStatus
    related_entity_type: Optional[str]
    related_entity_id: Optional[int]
    due_date: Optional[datetime]
    decision_note: Optional[str]
    decided_by: Optional[int]
    decided_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommunicationCreate(BaseModel):
    project_id: int
    subject: str
    communication_type: CommunicationType = CommunicationType.ISSUE
    assigned_to: Optional[int] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    description: Optional[str] = None
    question: Optional[str] = None
    response: Optional[str] = None
    discipline: Optional[str] = None
    location: Optional[str] = None
    related_task_id: Optional[int] = None
    related_document_id: Optional[int] = None
    due_date: Optional[datetime] = None


class CommunicationUpdate(BaseModel):
    subject: Optional[str] = None
    communication_type: Optional[CommunicationType] = None
    assigned_to: Optional[int] = None
    status: Optional[CommunicationStatus] = None
    priority: Optional[TaskPriority] = None
    description: Optional[str] = None
    question: Optional[str] = None
    response: Optional[str] = None
    discipline: Optional[str] = None
    location: Optional[str] = None
    related_task_id: Optional[int] = None
    related_document_id: Optional[int] = None
    due_date: Optional[datetime] = None


class CommunicationMessageCreate(BaseModel):
    message: str
    message_type: Literal["comment", "response"] = "comment"
    mention_user_ids: List[int] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def message_min_length(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Pesan komunikasi minimal 2 karakter")
        return v.strip()


class CommunicationEscalateRequest(BaseModel):
    reason: str
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None

    @field_validator("reason")
    @classmethod
    def reason_min_length(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("Alasan eskalasi minimal 5 karakter")
        return v.strip()


class CommunicationAttachmentResponse(BaseModel):
    id: int
    communication_id: int
    message_id: Optional[int]
    document_id: Optional[int]
    uploaded_by: int
    file_name: str
    file_size: Optional[int]
    mime_type: Optional[str]
    caption: Optional[str]
    download_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CommunicationMentionResponse(BaseModel):
    id: int
    communication_id: int
    message_id: int
    mentioned_user_id: int
    created_by: int
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CommunicationReadReceiptResponse(BaseModel):
    id: int
    communication_id: int
    user_id: int
    last_read_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommunicationMessageResponse(BaseModel):
    id: int
    communication_id: int
    user_id: Optional[int]
    message_type: str
    message: str
    telegram_message_id: Optional[str]
    created_at: datetime
    mentions: List[CommunicationMentionResponse] = Field(default_factory=list)
    attachments: List[CommunicationAttachmentResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CommunicationLinkResponse(BaseModel):
    id: int
    communication_id: int
    source_type: str
    source_id: int
    label: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CommunicationResponse(BaseModel):
    id: int
    project_id: int
    created_by: int
    assigned_to: Optional[int]
    communication_type: CommunicationType
    status: CommunicationStatus
    priority: TaskPriority
    subject: str
    description: Optional[str]
    question: Optional[str]
    response: Optional[str]
    discipline: Optional[str]
    location: Optional[str]
    related_task_id: Optional[int]
    related_document_id: Optional[int]
    due_date: Optional[datetime]
    answered_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    thread_count: int = 0
    attachment_count: int = 0
    unread_count: int = 0
    mention_count: int = 0
    last_activity_at: Optional[datetime] = None
    last_read_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommunicationDetailResponse(CommunicationResponse):
    messages: List[CommunicationMessageResponse] = Field(default_factory=list)
    attachments: List[CommunicationAttachmentResponse] = Field(default_factory=list)
    mentions: List[CommunicationMentionResponse] = Field(default_factory=list)
    read_receipts: List[CommunicationReadReceiptResponse] = Field(default_factory=list)
    links: List[CommunicationLinkResponse] = Field(default_factory=list)


class FeatureFlagUpdate(BaseModel):
    enabled: bool


class FeatureFlagResponse(BaseModel):
    id: int
    feature_key: str
    label: str
    category: str
    description: Optional[str]
    enabled: bool
    is_core: bool
    updated_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommercialPlanResponse(BaseModel):
    plan_key: Literal["starter", "professional", "enterprise"]
    name: str
    positioning: str
    monthly_base_price_min_idr: Optional[int]
    monthly_base_price_max_idr: Optional[int]
    implementation_fee_min_idr: Optional[int]
    implementation_fee_max_idr: Optional[int]
    included_users: Optional[int]
    active_project_limit: Optional[int]
    storage_limit_gb: Optional[float]
    ai_token_limit_monthly: Optional[int]
    automation_run_limit_monthly: Optional[int]
    enabled_features: List[str]
    recommended_for: List[str]


class CommercialTenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: Optional[str] = Field(default=None, max_length=80, pattern=r"^[a-z0-9-]+$")
    status: Literal["trial", "active", "paused", "cancelled"] = "trial"
    plan_key: Literal["starter", "professional", "enterprise"] = "professional"
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    billing_contact_email: Optional[EmailStr] = None
    trial_ends_at: Optional[datetime] = None
    subscription_starts_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    onboarding_stage: Literal["discovery", "setup", "training", "pilot", "live", "renewal"] = "discovery"
    notes: Optional[str] = None


class CommercialTenantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    status: Optional[Literal["trial", "active", "paused", "cancelled"]] = None
    plan_key: Optional[Literal["starter", "professional", "enterprise"]] = None
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    billing_contact_email: Optional[EmailStr] = None
    trial_ends_at: Optional[datetime] = None
    subscription_starts_at: Optional[datetime] = None
    subscription_ends_at: Optional[datetime] = None
    max_users: Optional[int] = Field(default=None, ge=0)
    active_project_limit: Optional[int] = Field(default=None, ge=0)
    storage_limit_gb: Optional[float] = Field(default=None, ge=0)
    ai_token_limit_monthly: Optional[int] = Field(default=None, ge=0)
    automation_run_limit_monthly: Optional[int] = Field(default=None, ge=0)
    onboarding_stage: Optional[Literal["discovery", "setup", "training", "pilot", "live", "renewal"]] = None
    notes: Optional[str] = None


class CommercialTenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    plan_key: str
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    billing_contact_email: Optional[str]
    trial_ends_at: Optional[datetime]
    subscription_starts_at: Optional[datetime]
    subscription_ends_at: Optional[datetime]
    max_users: Optional[int]
    active_project_limit: Optional[int]
    storage_limit_gb: Optional[float]
    ai_token_limit_monthly: Optional[int]
    automation_run_limit_monthly: Optional[int]
    onboarding_stage: str
    notes: Optional[str]
    created_by: Optional[int]
    updated_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommercialEntitlementUpdate(BaseModel):
    enabled: bool
    notes: Optional[str] = None


class CommercialEntitlementResponse(BaseModel):
    id: int
    tenant_id: int
    feature_key: str
    label: str
    category: str
    enabled: bool
    is_core: bool
    source: str
    notes: Optional[str]
    updated_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class CommercialUsageResponse(BaseModel):
    id: int
    tenant_id: int
    metric_key: str
    label: str
    period: str
    used_value: float
    limit_value: Optional[float]
    unit: str
    percent_used: Optional[float]
    updated_at: datetime


class CommercialReadinessCheck(BaseModel):
    key: str
    title: str
    status: Literal["done", "partial", "todo", "risk"]
    detail: str
    action: str


class CommercialReadinessResponse(BaseModel):
    summary: Dict[str, Any]
    checks: List[CommercialReadinessCheck]


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int]
    project_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[str]
    summary: Optional[str]
    before_data: Optional[str]
    after_data: Optional[str]
    channel: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentQuestion(BaseModel):
    project_id: int
    question: str


class DocumentSource(BaseModel):
    document_id: int
    file_name: str
    file_type: DocumentType
    version: int
    snippet: str
    chunk_id: Optional[int] = None
    score: Optional[float] = None


class DocumentAnswer(BaseModel):
    answer: str
    sources: List[DocumentSource]
    governance: str
    retrieval_mode: str = "rag"
    safety_status: str = "ok"


class DocumentSyncPreviewRequest(BaseModel):
    include_tasks: bool = True
    force_new: bool = False


class DocumentSyncSelection(BaseModel):
    change_ids: List[str] = Field(min_length=1)
    approver_id: Optional[int] = None


class DocumentSyncResponse(BaseModel):
    id: int
    document_id: int
    project_id: int
    created_by: int
    approval_id: Optional[int]
    status: DocumentSyncStatus
    plan: Dict[str, Any]
    selected_change_ids: List[str]
    generated_with_ai: bool
    reviewed_by: Optional[int]
    applied_by: Optional[int]
    requested_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    applied_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class PaginatedResponse(BaseModel):
    total: int
    page: int
    limit: int
    data: List
