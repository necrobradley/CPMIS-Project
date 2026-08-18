export type ProjectStatus = 'planning' | 'active' | 'on_hold' | 'completed' | 'cancelled'
export type TaskStatus    = 'todo' | 'in_progress' | 'review' | 'done' | 'blocked'
export type TaskPriority  = 'low' | 'medium' | 'high' | 'critical'
export type UserRole      = 'owner' | 'admin' | 'director' | 'manager' | 'staff' | 'subcontractor'
export type DocumentType  = 'tender' | 'contract' | 'daily_report' | 'photo' | 'drawing' | 'other'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'
export type ApprovalType = 'document' | 'task' | 'instruction' | 'scope_change' | 'other'
export type CommunicationType = 'rfi' | 'submittal' | 'site_instruction' | 'issue' | 'escalation' | 'meeting_action'
export type CommunicationStatus = 'draft' | 'open' | 'in_review' | 'answered' | 'closed' | 'void'
export type ReportStatus = 'draft' | 'needs_revision' | 'ready_for_review' | 'verified' | 'approved'
export type EvidenceType = 'photo' | 'document'
export type DocumentSyncStatus = 'draft' | 'pending_approval' | 'approved' | 'applied' | 'rejected' | 'cancelled' | 'failed'

export interface Project {
  id:               number
  project_name:     string
  description?:     string
  location?:        string
  contract_value?:  number
  start_date?:      string
  end_date?:        string
  status:           ProjectStatus
  plan_key?:        CommercialPlanKey | null
  owner_id:         number
  progress_percent: number
  created_at:       string
}

export interface Division {
  id:            number
  division_name: string
  description?:  string
  project_id:    number
  manager_id?:   number
  created_at:    string
}

export type ProjectMemberRole =
  | 'project_admin'
  | 'project_manager'
  | 'division_lead'
  | 'staff'
  | 'subcontractor'
  | 'viewer'
  | string

export interface ProjectMemberRoleCatalog {
  code:             string
  label:            string
  category:         string
  category_label:   string
  default_division: string
  responsibility:   string
  access_hint:      string
  can_be_task_pic:  boolean
  requires_division: boolean
}

export interface ProjectRolePolicy extends ProjectMemberRoleCatalog {
  project_id:  number
  enabled:     boolean
  updated_by?: number
  created_at?: string
  updated_at?: string
}

export interface ProjectMember {
  id:           number
  project_id:   number
  user_id:      number
  division_id?: number
  project_role: ProjectMemberRole
  is_active:    boolean
  joined_at:    string
  user:         User
  division?:    Division
}

export interface Task {
  id:               number
  title:            string
  description?:     string
  project_id:       number
  division_id?:     number
  division?:        Division
  assigned_to?:     number
  assignee?:        User
  created_by:       number
  priority:         TaskPriority
  status:           TaskStatus
  deadline?:        string
  progress_percent: number
  approval_status?: ApprovalStatus
  approval_id?:     number
  approved_by?:     number
  approved_at?:     string
  approval_note?:   string
  ai_generated:     boolean
  ai_source?:       string
  parent_task_id?:  number
  specification?:   TaskSpecification
  requirements:     TaskRequirement[]
  materials:        TaskMaterialSpecification[]
  created_at:       string
}

export interface TaskSpecification {
  id:                      number
  task_id:                 number
  wbs_code:                string
  work_package?:           string
  location?:               string
  acceptance_criteria:     string
  reporting_instructions?: string
  required_photo_count:    number
  required_document_count: number
  template_name:           string
  template_version:        string
  source_document_id?:     number
}

export interface TaskRequirement {
  id:               number
  task_id:          number
  code:             string
  title:            string
  description?:     string
  requirement_type: string
  validation_rule:  string
  is_mandatory:     boolean
  sequence:         number
}

export interface TaskMaterialSpecification {
  id:                       number
  task_id:                  number
  material_code?:           string
  material_name:            string
  category?:                string
  technical_specification?: string
  standard_reference?:      string
  grade?:                   string
  approved_manufacturer?:   string
  dimensions?:              string
  unit?:                    string
  planned_quantity?:        number
  certificate_required:     boolean
  test_required:            boolean
  approval_required:        boolean
  source_document_id?:      number
  source_page?:             string
  revision?:                string
  sequence:                 number
  created_at:               string
  updated_at:               string
}

export interface User {
  id:          number
  name:        string
  email?:      string
  role:        UserRole
  phone?:      string
  division_id?: number
  telegram_id?: string
  avatar_url?: string
  is_active:   boolean
  email_verified_at?: string
  email_verification_required?: boolean
  must_set_password?: boolean
  created_at:  string
  project_id?: number
  project_division_id?: number
  project_division_name?: string
  project_role?: string
  project_role_label?: string
}

export interface DailyReport {
  id:              number
  project_id:      number
  user_id:         number
  report_date:     string
  report_text:     string
  weather?:        string
  manpower_count?: number
  work_progress?:  string
  issues?:         string
  ai_summary?:     string
  ai_risks?:       string
  workflow?:       ReportWorkflow
  evidence:        ReportEvidence[]
  reviews:         ReportReview[]
  requirement_checks: RequirementConfirmation[]
  progress_entry?: ReportProgressEntry
  created_at:      string
}

export interface ReportProgressEntry {
  report_id:                number
  task_id:                  number
  quantity_this_report:     number
  cost_this_report:         number
  cumulative_quantity:     number
  progress_after_approval:  number
  applied_at?:              string
}

export interface RequirementConfirmation {
  id?:            number
  report_id?:     number
  requirement_id: number
  confirmed:      boolean
  note?:          string
}

export interface ReportWorkflow {
  task_id:            number
  status:             ReportStatus
  validation_passed:  boolean
  validation_score:   number
  validation_result?: string
  revision_note?:     string
  submitted_at?:      string
  verified_by?:       number
  verified_at?:       string
  approved_by?:       number
  approved_at?:       string
}

export interface ReportEvidence {
  id:                  number
  report_id:           number
  uploaded_by:         number
  evidence_type:       EvidenceType
  file_name:           string
  file_size?:          number
  mime_type?:          string
  caption?:            string
  telegram_message_id?: string
  download_url?:       string
  created_at:          string
}

export interface ReportReview {
  id:           number
  reviewer_id:  number
  from_status:  string
  to_status:    string
  note?:        string
  created_at:   string
}

export interface DashboardStats {
  total_projects:  number
  active_projects: number
  total_tasks:     number
  done_tasks:      number
  overdue_tasks:   number
  total_reports:   number
}

export interface Document {
  id:          number
  file_name:   string
  file_type:   DocumentType
  file_size?:  number
  version:     number
  has_ai:      boolean
  uploaded_by: number
  created_at:  string
  latest_sync_id?: number
  sync_status?: DocumentSyncStatus
}

export interface DocumentSyncChange {
  id:        string
  entity:    'project' | 'division' | 'task'
  operation: 'create' | 'update'
  field?:    string
  label:     string
  risk:      'low' | 'medium' | 'high'
  before?:   unknown
  after:     unknown
}

export interface DocumentSyncPlan {
  version:  number
  document: { id: number; file_name: string; version: number }
  project:  { id: number; project_name: string }
  summary: {
    total: number
    project_updates: number
    divisions_created: number
    tasks_created: number
    tasks_updated: number
    high_risk: number
  }
  changes:  DocumentSyncChange[]
  warnings: string[]
  policy: {
    match_key: string
    delete_missing: boolean
    preserve_status_progress_assignee: boolean
    require_approval: boolean
  }
}

export interface DocumentSyncSession {
  id:                  number
  document_id:         number
  project_id:          number
  created_by:          number
  approval_id?:        number
  status:              DocumentSyncStatus
  plan:                DocumentSyncPlan
  selected_change_ids: string[]
  generated_with_ai:   boolean
  reviewed_by?:        number
  applied_by?:         number
  requested_at?:       string
  reviewed_at?:        string
  applied_at?:         string
  error_message?:      string
  created_at:          string
  updated_at:          string
}

export interface Notification {
  id:                  number
  title:               string
  message:             string
  type:                string
  is_read:             boolean
  related_task_id?:    number
  related_project_id?: number
  sent_to_telegram:    boolean
  created_at:          string
}

export interface FeatureFlag {
  id:           number
  feature_key:  string
  label:        string
  category:     string
  description?: string
  enabled:      boolean
  is_core:      boolean
  updated_by?:  number
  created_at:   string
  updated_at:   string
}

export type CommercialPlanKey = 'starter' | 'professional' | 'enterprise'
export type CommercialTenantStatus = 'trial' | 'active' | 'paused' | 'cancelled'
export type CommercialOnboardingStage = 'discovery' | 'setup' | 'training' | 'pilot' | 'live' | 'renewal'
export type CommercialReadinessStatus = 'done' | 'partial' | 'todo' | 'risk'

export interface CommercialPlan {
  plan_key:                      CommercialPlanKey
  name:                          string
  positioning:                   string
  monthly_base_price_min_idr?:   number
  monthly_base_price_max_idr?:   number
  implementation_fee_min_idr?:   number
  implementation_fee_max_idr?:   number
  included_users?:               number
  active_project_limit?:         number
  storage_limit_gb?:             number
  ai_token_limit_monthly?:       number
  automation_run_limit_monthly?: number
  enabled_features:              string[]
  recommended_for:               string[]
}

export interface CommercialTenant {
  id:                            number
  name:                          string
  slug:                          string
  status:                        CommercialTenantStatus
  plan_key:                      CommercialPlanKey
  contact_name?:                 string
  contact_email?:                string
  contact_phone?:                string
  billing_contact_email?:        string
  trial_ends_at?:                string
  subscription_starts_at?:       string
  subscription_ends_at?:         string
  max_users?:                    number
  active_project_limit?:         number
  storage_limit_gb?:             number
  ai_token_limit_monthly?:       number
  automation_run_limit_monthly?: number
  onboarding_stage:              CommercialOnboardingStage
  notes?:                        string
  created_by?:                   number
  updated_by?:                   number
  created_at:                    string
  updated_at:                    string
}

export interface CommercialEntitlement {
  id:          number
  tenant_id:   number
  feature_key: string
  label:       string
  category:    string
  enabled:     boolean
  is_core:     boolean
  source:      'plan' | 'manual'
  notes?:      string
  updated_by?: number
  created_at:  string
  updated_at:  string
}

export interface CommercialUsage {
  id:            number
  tenant_id:     number
  metric_key:    string
  label:         string
  period:        string
  used_value:    number
  limit_value?:  number
  unit:          string
  percent_used?: number
  updated_at:    string
}

export interface CommercialReadiness {
  summary: Record<string, number>
  checks: {
    key:    string
    title:  string
    status: CommercialReadinessStatus
    detail: string
    action: string
  }[]
}

export interface Approval {
  id:                  number
  project_id:          number
  requested_by:        number
  approver_id?:        number
  title:               string
  description?:        string
  approval_type:       ApprovalType
  status:              ApprovalStatus
  related_entity_type?: string
  related_entity_id?:  number
  due_date?:           string
  decision_note?:      string
  decided_by?:         number
  decided_at?:         string
  created_at:          string
  updated_at:          string
}

export interface AuditLog {
  id:           number
  actor_id?:    number
  project_id?:  number
  action:       string
  entity_type:  string
  entity_id?:   string
  summary?:     string
  before_data?: string
  after_data?:  string
  channel:      string
  created_at:   string
}

export interface CommunicationItem {
  id:                    number
  project_id:            number
  created_by:            number
  assigned_to?:          number
  communication_type:    CommunicationType
  status:                CommunicationStatus
  priority:              TaskPriority
  subject:               string
  description?:          string
  question?:             string
  response?:             string
  discipline?:           string
  location?:             string
  related_task_id?:      number
  related_document_id?:  number
  due_date?:             string
  answered_at?:          string
  closed_at?:            string
  created_at:            string
  updated_at:            string
  thread_count?:         number
  attachment_count?:     number
  unread_count?:         number
  mention_count?:        number
  last_activity_at?:     string
  last_read_at?:         string
}

export interface CommunicationAttachment {
  id:               number
  communication_id: number
  message_id?:      number
  document_id?:     number
  uploaded_by:      number
  file_name:        string
  file_size?:       number
  mime_type?:       string
  caption?:         string
  download_url?:    string
  created_at:       string
}

export interface CommunicationMention {
  id:                 number
  communication_id:   number
  message_id:         number
  mentioned_user_id:  number
  created_by:         number
  is_read:            boolean
  read_at?:           string
  created_at:         string
}

export interface CommunicationReadReceipt {
  id:               number
  communication_id: number
  user_id:          number
  last_read_at:     string
  created_at:       string
  updated_at:       string
}

export interface CommunicationMessage {
  id:                  number
  communication_id:    number
  user_id?:            number
  message_type:        string
  message:             string
  telegram_message_id?: string
  mentions:            CommunicationMention[]
  attachments:         CommunicationAttachment[]
  created_at:          string
}

export interface CommunicationLink {
  id:               number
  communication_id: number
  source_type:      string
  source_id:        number
  label?:           string
  created_at:       string
}

export interface CommunicationDetail extends CommunicationItem {
  messages:       CommunicationMessage[]
  attachments:    CommunicationAttachment[]
  mentions:       CommunicationMention[]
  read_receipts:  CommunicationReadReceipt[]
  links:          CommunicationLink[]
}

export interface DocumentSource {
  document_id: number
  file_name:   string
  file_type:   DocumentType
  version:     number
  snippet:     string
}

export interface DocumentAnswer {
  answer:     string
  sources:    DocumentSource[]
  governance: string
}

export interface ComplianceResult {
  project_id:           number
  project_name:         string
  compliance_score:     number
  status:               string
  summary:              string
  missing_deliverables: string[]
  completed_items:      string[]
  at_risk_items:        string[]
  milestone_status:     { name: string; status: string }[]
  recommendations:      string[]
  contracts_checked:    number
  total_tasks:          number
}
