'use client'
import { use, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { controlsApi, projectsApi, tasksApi, usersApi } from '@/lib/api'
import { Division, Project, ProjectMember, ProjectMemberRoleCatalog, ProjectRolePolicy, Task, User } from '@/types'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'
import {
  formatCurrency, formatDate, isOverdue, priorityBadgeClass,
  PRIORITY_LABELS, statusBadgeClass, STATUS_LABELS,
} from '@/lib/utils'
import {
  AlertTriangle, ArrowLeft, BarChart3, Building2, CalendarDays,
  CheckCircle2, CheckSquare2, ChevronRight, CircleDollarSign,
  Clock3, FolderTree, GitBranch, ListChecks, Loader2, MapPin,
  PlayCircle, Plus, Settings2, ToggleLeft, ToggleRight, Trash2, UserPlus, Users2, X,
} from 'lucide-react'

const PROJECT_ROLE_LABELS: Record<string, string> = {
  project_admin: 'Admin Proyek',
  project_manager: 'Project Manager',
  division_lead: 'Kepala Divisi',
  staff: 'Staff',
  subcontractor: 'Subkontraktor',
  viewer: 'Pengamat',
}
const PROJECT_ADMIN_ROLE_CODES = new Set(['project_admin'])

type ProjectSCurvePoint = {
  date: string
  planned_percent: number
  actual_percent: number
  variance_percent: number
}

function MiniSCurve({ data }: { data: ProjectSCurvePoint[] }) {
  if (!data.length) {
    return <div className="flex h-48 items-center justify-center border border-dashed border-slate-300 bg-white text-sm text-slate-500">Baseline belum cukup untuk S-curve.</div>
  }
  const width = 640
  const height = 190
  const padding = 28
  const x = (index: number) => padding + (index / Math.max(1, data.length - 1)) * (width - padding * 2)
  const y = (value: number) => padding + ((100 - Math.max(0, Math.min(100, value))) / 100) * (height - padding * 2)
  const path = (key: 'planned_percent' | 'actual_percent') =>
    data.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(point[key])}`).join(' ')
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-52 w-full">
      {[0, 50, 100].map((tick) => (
        <g key={tick}><line x1={padding} x2={width - padding} y1={y(tick)} y2={y(tick)} className="stroke-slate-100" /><text x={4} y={y(tick) + 4} className="fill-slate-400 text-[10px]">{tick}%</text></g>
      ))}
      <path d={path('planned_percent')} fill="none" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" />
      <path d={path('actual_percent')} fill="none" stroke="#0891b2" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

const FALLBACK_PROJECT_ROLES: ProjectMemberRoleCatalog[] = Object.entries(PROJECT_ROLE_LABELS).map(([code, label]) => ({
  code,
  label,
  category: 'basic',
  category_label: 'Basic',
  default_division: 'Project Team',
  responsibility: 'Peran proyek dasar.',
  access_hint: 'Mengikuti RBAC akun pengguna.',
  can_be_task_pic: code !== 'viewer',
  requires_division: !['project_manager', 'viewer'].includes(code),
}))

const DIVISION_TEMPLATES = [
  { division_name: 'Project Management', description: 'PM, Deputy PM, project coordination, escalation, governance, and decision control.' },
  { division_name: 'Site Management', description: 'Construction/site manager, site coordination, resource readiness, and daily field control.' },
  { division_name: 'Engineering', description: 'Project engineer, site engineer, technical coordination, method, and design clarification.' },
  { division_name: 'Architecture', description: 'Architectural works, finishing, facade, interior details, and related material approval.' },
  { division_name: 'MEP', description: 'Mechanical, electrical, plumbing, testing, commissioning, and MEP coordination.' },
  { division_name: 'BIM / Digital Engineering', description: 'BIM model, clash coordination, digital engineering, model-based quantity, and drawing coordination.' },
  { division_name: 'Survey', description: 'Survey control, setting out, elevation, measurement, and field survey records.' },
  { division_name: 'Planning & Controls', description: 'Baseline schedule, lookahead planning, progress tracking, delay analysis, and project controls.' },
  { division_name: 'Cost Control', description: 'Budget control, actual cost, cost variance, forecast, cashflow, and cost reporting.' },
  { division_name: 'Quantity Surveying', description: 'BOQ, quantity takeoff, progress volume, payment claim, variation order, and measurement.' },
  { division_name: 'Finance & Accounting', description: 'Project finance, invoice, payment tracking, accounting support, tax, and financial administration.' },
  { division_name: 'Commercial / Contract', description: 'Contract administration, claims, correspondence, notices, variation, and commercial risk.' },
  { division_name: 'Procurement', description: 'Purchasing, vendor follow-up, procurement document, material lead time, and submittal support.' },
  { division_name: 'Logistics', description: 'Delivery planning, site logistics, lifting/access coordination, and material movement.' },
  { division_name: 'Warehouse', description: 'Material receiving, stock control, issue record, storage, and warehouse evidence.' },
  { division_name: 'Document Control', description: 'Document register, drawing revision, transmittal, distribution, archive, and handover dossier.' },
  { division_name: 'QA/QC', description: 'Inspection, ITP, test result, checklist, NCR, requirement validation, and quality records.' },
  { division_name: 'HSE', description: 'Safety control, incident report, toolbox meeting, risk assessment, permit to work, and HSE compliance.' },
  { division_name: 'Site Execution', description: 'Supervisor, foreman/mandor, field staff, manpower, daily output, and field reporting.' },
  { division_name: 'Administration / GA', description: 'Project administration, general affairs, office support, attendance, and project facilities.' },
  { division_name: 'HR / People', description: 'Manpower administration, onboarding, staffing, attendance, and personnel coordination.' },
  { division_name: 'Legal & Permit', description: 'Legal review, permits, authority submission, land/legal issue, and regulatory compliance.' },
  { division_name: 'IT / Digital Support', description: 'System support, device, network, digital workflow, integration, and data support.' },
  { division_name: 'Security', description: 'Site security, access control, visitor record, incident coordination, and asset protection.' },
  { division_name: 'Owner / Executive', description: 'Owner representative, sponsor, client stakeholder, executive decision, and milestone acceptance.' },
  { division_name: 'Consultant', description: 'Design/supervision consultant, technical review, inspection review, and formal response.' },
  { division_name: 'Subcontractor', description: 'Subcontractor work package execution, field reporting, evidence, and submittal response.' },
  { division_name: 'Vendor / Supplier', description: 'Material supplier, delivery status, certificate, technical document, and procurement coordination.' },
]

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const projectId = Number(id)
  const qc = useQueryClient()
  const currentUser = useAuthStore((state) => state.user)
  const isAppAdmin = currentUser?.role === 'admin'
  const canManage = Boolean(currentUser && ['admin', 'director', 'manager'].includes(currentUser.role))
  const [showStructure, setShowStructure] = useState(false)
  const [divisionForm, setDivisionForm] = useState({ division_name: '', description: '' })
  const [memberForm, setMemberForm] = useState({ user_id: '', division_id: '', project_role: 'staff' })

  const { data: project, isLoading: projectLoading } = useQuery<Project>({
    queryKey: ['project', projectId],
    queryFn: async () => (await projectsApi.get(projectId)).data,
  })
  const { data: divisions = [] } = useQuery<Division[]>({
    queryKey: ['divisions', projectId],
    queryFn: async () => (await projectsApi.divisions(projectId)).data,
  })
  const { data: tasks = [] } = useQuery<Task[]>({
    queryKey: ['tasks', projectId],
    queryFn: async () => (await tasksApi.list({ project_id: projectId })).data,
  })
  const { data: controlsSummary } = useQuery<{
    s_curve: ProjectSCurvePoint[]
    metrics: { pending_task_approval_count: number; vendor_review_count: number; progress_percent: number }
  }>({
    queryKey: ['controls-summary', projectId],
    queryFn: async () => (await controlsApi.summary(projectId)).data,
    enabled: canManage,
  })
  const { data: members = [] } = useQuery<ProjectMember[]>({
    queryKey: ['project-members', projectId],
    queryFn: async () => (await projectsApi.members(projectId)).data,
  })
  const { data: users = [] } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: async () => (await usersApi.list()).data,
    enabled: canManage,
  })
  const { data: roleCatalog = FALLBACK_PROJECT_ROLES } = useQuery<ProjectMemberRoleCatalog[]>({
    queryKey: ['project-member-roles'],
    queryFn: async () => (await projectsApi.memberRoles()).data,
  })
  const { data: rolePolicy = [] } = useQuery<ProjectRolePolicy[]>({
    queryKey: ['project-role-policy', projectId],
    queryFn: async () => (await projectsApi.rolePolicy(projectId)).data,
  })
  const roleCatalogWithPolicy: ProjectRolePolicy[] = rolePolicy.length
    ? rolePolicy
    : roleCatalog.map((role) => ({ ...role, project_id: projectId, enabled: true }))
  const assignableRoleCatalog = roleCatalogWithPolicy.filter((role) => (
    role.enabled && (isAppAdmin || !PROJECT_ADMIN_ROLE_CODES.has(role.code))
  ))
  const selectedRoleCode = assignableRoleCatalog.some((role) => role.code === memberForm.project_role)
    ? memberForm.project_role
    : assignableRoleCatalog[0]?.code || memberForm.project_role
  const rolesForMember = (currentRole: string) => {
    if (!isAppAdmin && PROJECT_ADMIN_ROLE_CODES.has(currentRole)) {
      return roleCatalogWithPolicy.filter((role) => role.code === currentRole)
    }
    if (assignableRoleCatalog.some((role) => role.code === currentRole)) return assignableRoleCatalog
    const current = roleCatalogWithPolicy.find((role) => role.code === currentRole)
    return current ? [current, ...assignableRoleCatalog] : assignableRoleCatalog
  }
  const roleLabel = (code: string) => roleCatalogWithPolicy.find((role) => role.code === code)?.label || PROJECT_ROLE_LABELS[code] || code
  const groupedRoles = assignableRoleCatalog.reduce<Record<string, ProjectRolePolicy[]>>((groups, role) => {
    const key = role.category_label || 'Lainnya'
    groups[key] = [...(groups[key] || []), role]
    return groups
  }, {})
  const groupedPolicyRoles = roleCatalogWithPolicy.reduce<Record<string, ProjectRolePolicy[]>>((groups, role) => {
    const key = role.category_label || 'Lainnya'
    groups[key] = [...(groups[key] || []), role]
    return groups
  }, {})
  const selectedRole = roleCatalogWithPolicy.find((role) => role.code === selectedRoleCode)
  const memberRoleRequiresDivision = selectedRole?.requires_division ?? !['project_manager', 'viewer'].includes(selectedRoleCode)

  const createDivision = useMutation({
    mutationFn: (data?: typeof divisionForm) => projectsApi.createDivision(projectId, data || divisionForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['divisions', projectId] })
      qc.invalidateQueries({ queryKey: ['project-divisions', projectId] })
      setDivisionForm({ division_name: '', description: '' })
      toast.success('Divisi ditambahkan')
    },
    onError: () => toast.error('Gagal menambahkan divisi'),
  })

  const deleteDivision = useMutation({
    mutationFn: (divisionId: number) => projectsApi.deleteDivision(projectId, divisionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['divisions', projectId] })
      qc.invalidateQueries({ queryKey: ['project-divisions', projectId] })
      toast.success('Divisi dihapus')
    },
    onError: () => toast.error('Divisi masih memiliki task atau anggota'),
  })

  const addMember = useMutation({
    mutationFn: () => projectsApi.addMember(projectId, {
      user_id: Number(memberForm.user_id),
      division_id: memberForm.division_id ? Number(memberForm.division_id) : null,
      project_role: selectedRoleCode,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-members', projectId] })
      setMemberForm({ user_id: '', division_id: '', project_role: 'staff' })
      toast.success('Staff ditempatkan pada proyek')
    },
    onError: () => toast.error('Gagal menempatkan staff'),
  })

  const updateMember = useMutation({
    mutationFn: ({ membershipId, data }: { membershipId: number; data: Record<string, unknown> }) =>
      projectsApi.updateMember(projectId, membershipId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-members', projectId] })
      toast.success('Penempatan staff diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui penempatan staff'),
  })

  const removeMember = useMutation({
    mutationFn: (membershipId: number) => projectsApi.removeMember(projectId, membershipId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-members', projectId] })
      toast.success('Staff dikeluarkan dari proyek')
    },
    onError: () => toast.error('Staff masih memiliki task aktif'),
  })

  const updateRolePolicy = useMutation({
    mutationFn: ({ roleCode, enabled }: { roleCode: string; enabled: boolean }) =>
      projectsApi.updateRolePolicy(projectId, roleCode, enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-role-policy', projectId] })
      toast.success('Batasan role proyek diperbarui')
    },
    onError: () => toast.error('Gagal mengubah batasan role'),
  })

  if (projectLoading) {
    return <div className="flex justify-center py-24"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
  }

  if (!project) {
    return (
      <div className="card p-16 text-center">
        <Building2 size={28} className="mx-auto mb-3 text-slate-300" />
        <p className="text-sm text-slate-500">Proyek tidak ditemukan.</p>
      </div>
    )
  }

  const doneTasks = tasks.filter((task) => task.status === 'done').length
  const activeTasks = tasks.filter((task) => task.status === 'in_progress').length
  const reviewTasks = tasks.filter((task) => task.status === 'review').length
  const overdueTasks = tasks.filter((task) => isOverdue(task.deadline) && task.status !== 'done').length
  const pendingApprovalTasks = controlsSummary?.metrics.pending_task_approval_count ?? tasks.filter((task) => (task.approval_status || 'approved') === 'pending').length
  const structuredTasks = tasks.filter((task) => task.specification?.wbs_code).length
  const requirementCount = tasks.reduce((sum, task) => sum + task.requirements.length, 0)
  const existingDivisionNames = new Set(divisions.map((division) => division.division_name.toLowerCase()))
  const availableDivisionTemplates = DIVISION_TEMPLATES.filter(
    (template) => !existingDivisionNames.has(template.division_name.toLowerCase())
  )

  const summary = [
    ...(canManage ? [{ label: 'Nilai kontrak', value: formatCurrency(project.contract_value), icon: CircleDollarSign, tone: 'bg-emerald-50 text-emerald-700' }] : []),
    { label: 'Periode mulai', value: formatDate(project.start_date), icon: CalendarDays, tone: 'bg-blue-50 text-blue-700' },
    { label: 'Target selesai', value: formatDate(project.end_date), icon: Clock3, tone: 'bg-orange-50 text-orange-700' },
    { label: 'Struktur kerja', value: `${divisions.length} divisi`, icon: FolderTree, tone: 'bg-violet-50 text-violet-700' },
  ]

  return (
    <div className="space-y-7 animate-in">
      <div>
        <Link href="/projects" className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-brand-600">
          <ArrowLeft size={15} /> Daftar proyek
        </Link>
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
              <Building2 size={24} />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-bold text-slate-950 lg:text-3xl">{project.project_name}</h1>
                <span className={statusBadgeClass(project.status)}>{STATUS_LABELS[project.status]}</span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500">
                <span className="flex items-center gap-1.5"><MapPin size={14} />{project.location || 'Lokasi belum ditetapkan'}</span>
                <span className="flex items-center gap-1.5"><GitBranch size={14} />{structuredTasks}/{tasks.length} task memiliki WBS</span>
              </div>
              {project.description && <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{project.description}</p>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {canManage && (
              <button onClick={() => setShowStructure(true)} className="btn-secondary">
                <Settings2 size={16} /> Kelola divisi & tim
              </button>
            )}
            <Link href="/projects/tree" className="btn-secondary"><FolderTree size={16} /> Struktur proyek</Link>
            <Link href={`/tasks?project_id=${projectId}`} className="btn-primary"><CheckSquare2 size={16} /> Buka pekerjaan</Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-2 xl:grid-cols-4">
        {summary.map((item) => (
          <div key={item.label} className="flex min-w-0 items-center gap-3 bg-white p-4">
            <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${item.tone}`}><item.icon size={18} /></div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900">{item.value}</p>
              <p className="mt-0.5 text-xs text-slate-500">{item.label}</p>
            </div>
          </div>
        ))}
      </div>

      <section className="card overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_1fr]">
          <div className="border-b border-slate-200 p-5 lg:border-b-0 lg:border-r lg:p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Kemajuan proyek</p>
                <p className="mt-1 text-sm text-slate-500">Berdasarkan progres pekerjaan aktif</p>
              </div>
              <div className="text-right">
                <span className="text-3xl font-bold text-slate-950">{project.progress_percent}%</span>
                <p className="text-xs text-slate-500">keseluruhan</p>
              </div>
            </div>
            <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500 transition-all duration-700" style={{ width: `${project.progress_percent}%` }} />
            </div>
            <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3 text-xs text-slate-500">
              <span className="flex items-center gap-1.5"><ListChecks size={14} className="text-brand-600" />{tasks.length} total task</span>
              <span className="flex items-center gap-1.5"><GitBranch size={14} className="text-violet-600" />{requirementCount} requirement</span>
              <span className="flex items-center gap-1.5"><Users2 size={14} className="text-emerald-600" />{members.length} anggota proyek</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-px bg-slate-200 sm:grid-cols-4 lg:grid-cols-2">
            {[
              { label: 'Selesai', value: doneTasks, icon: CheckCircle2, color: 'text-emerald-600' },
              { label: 'Berjalan', value: activeTasks, icon: PlayCircle, color: 'text-blue-600' },
              { label: 'Tinjauan', value: reviewTasks, icon: BarChart3, color: 'text-violet-600' },
              { label: 'Pending PM', value: pendingApprovalTasks, icon: Clock3, color: 'text-amber-600' },
              { label: 'Terlambat', value: overdueTasks, icon: AlertTriangle, color: 'text-rose-600' },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-3 bg-white p-4">
                <item.icon size={18} className={item.color} />
                <div><p className="text-xl font-bold text-slate-950">{item.value}</p><p className="text-xs text-slate-500">{item.label}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {canManage && controlsSummary && (
        <section className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
          <div className="card p-5">
            <div className="mb-3 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Timeline S-curve</h2>
                <p className="mt-1 text-xs text-slate-500">Task yang sudah approved PM masuk ke baseline plan dan actual progress.</p>
              </div>
              <Link href="/controls" className="text-xs font-semibold text-brand-600 hover:text-brand-700">Buka Controls</Link>
            </div>
            <MiniSCurve data={controlsSummary.s_curve || []} />
            <div className="mt-2 flex flex-wrap gap-4 text-xs font-semibold text-slate-600">
              <span className="inline-flex items-center gap-2"><span className="h-1 w-8 rounded-full bg-slate-900" /> Planned</span>
              <span className="inline-flex items-center gap-2"><span className="h-1 w-8 rounded-full bg-cyan-600" /> Actual</span>
            </div>
          </div>
          <div className="card p-5">
            <h2 className="text-base font-semibold text-slate-900">Action queue PM</h2>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3"><span className="text-sm text-slate-600">Task menunggu approval</span><span className="text-xl font-bold text-amber-600">{pendingApprovalTasks}</span></div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-3"><span className="text-sm text-slate-600">Review vendor</span><span className="text-xl font-bold text-violet-600">{controlsSummary.metrics.vendor_review_count || 0}</span></div>
              <div className="flex items-center justify-between"><span className="text-sm text-slate-600">Progress controls</span><span className="text-xl font-bold text-cyan-700">{controlsSummary.metrics.progress_percent || project.progress_percent}%</span></div>
            </div>
          </div>
        </section>
      )}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Divisi proyek</h2>
            <p className="mt-1 text-xs text-slate-500">Distribusi pekerjaan dan progres per tim.</p>
          </div>
          <span className="badge-gray">{divisions.length} divisi</span>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {divisions.map((division) => {
            const divisionTasks = tasks.filter((task) => task.division_id === division.id)
            const divisionMembers = members.filter((member) => member.division_id === division.id)
            const divisionDone = divisionTasks.filter((task) => task.status === 'done').length
            const progress = divisionTasks.length ? Math.round((divisionDone / divisionTasks.length) * 100) : 0
            return (
              <div key={division.id} className="card p-5 transition-shadow hover:shadow-card-hover">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><Users2 size={16} /></div>
                    <div className="min-w-0"><h3 className="text-sm font-semibold text-slate-900">{division.division_name}</h3><p className="mt-1 text-xs text-slate-500">{divisionMembers.length} staff · {divisionTasks.length} task</p></div>
                  </div>
                  <span className="text-sm font-bold text-slate-700">{progress}%</span>
                </div>
                <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${progress}%` }} /></div>
                <p className="mt-2 text-xs text-slate-500">{divisionDone} dari {divisionTasks.length} task selesai</p>
                <div className="mt-4 flex -space-x-2">
                  {divisionMembers.slice(0, 5).map((member) => (
                    <div key={member.id} title={`${member.user.name} - ${roleLabel(member.project_role)}`} className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-slate-800 text-[10px] font-semibold text-white">
                      {member.user.name.charAt(0).toUpperCase()}
                    </div>
                  ))}
                  {divisionMembers.length > 5 && <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-slate-200 text-[10px] font-semibold text-slate-600">+{divisionMembers.length - 5}</div>}
                </div>
              </div>
            )
          })}
          {!divisions.length && <div className="card p-8 text-center text-sm text-slate-500 md:col-span-2 xl:col-span-3">Belum ada divisi pada proyek ini.</div>}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Daftar pekerjaan</h2>
            <p className="mt-1 text-xs text-slate-500">Task, WBS, penanggung jawab proses, dan target penyelesaian.</p>
          </div>
          <Link href={`/tasks?project_id=${projectId}`} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">Lihat Kanban <ChevronRight size={14} /></Link>
        </div>
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-[820px] w-full">
              <thead className="bg-slate-50/80">
                <tr className="border-b border-slate-200">
                  {['WBS / Task', 'PIC', 'Prioritas', 'Approval', 'Status', 'Deadline', 'Progress'].map((header) => <th key={header} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{header}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tasks.map((task) => (
                  <tr key={task.id} className="transition hover:bg-slate-50">
                    <td className="max-w-[420px] px-5 py-4">
                      <div className="flex items-start gap-3">
                        <CheckSquare2 size={16} className="mt-0.5 flex-shrink-0 text-slate-400" />
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold text-slate-900">{task.title}</span>{task.specification?.wbs_code && <span className="font-mono text-[11px] font-medium text-brand-700">{task.specification.wbs_code}</span>}</div>
                          <p className="mt-1 line-clamp-1 text-xs text-slate-500">{task.specification?.work_package || task.description || 'Work package belum ditetapkan'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4"><span className="text-xs font-medium text-slate-700">{task.assignee?.name || 'Belum ditetapkan'}</span></td>
                    <td className="px-5 py-4"><span className={priorityBadgeClass(task.priority)}>{PRIORITY_LABELS[task.priority]}</span></td>
                    <td className="px-5 py-4">
                      <span className={
                        (task.approval_status || 'approved') === 'approved'
                          ? 'badge-success'
                          : task.approval_status === 'rejected'
                            ? 'badge-danger'
                            : 'badge-warning'
                      }>{task.approval_status || 'approved'}</span>
                    </td>
                    <td className="px-5 py-4"><span className={statusBadgeClass(task.status)}>{STATUS_LABELS[task.status]}</span></td>
                    <td className="px-5 py-4"><span className={`inline-flex items-center gap-1.5 text-xs ${isOverdue(task.deadline) && task.status !== 'done' ? 'font-semibold text-rose-600' : 'text-slate-500'}`}>{isOverdue(task.deadline) && task.status !== 'done' && <AlertTriangle size={12} />}{task.deadline ? formatDate(task.deadline) : '-'}</span></td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2"><div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-500" style={{ width: `${task.progress_percent}%` }} /></div><span className="text-xs font-medium text-slate-600">{task.progress_percent}%</span></div>
                    </td>
                  </tr>
                ))}
                {!tasks.length && <tr><td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-500">Belum ada task untuk proyek ini.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {showStructure && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4" onClick={() => setShowStructure(false)}>
          <div className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-lg bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white p-5">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Struktur divisi dan tim</h2>
                <p className="mt-1 text-xs text-slate-500">Tentukan unit kerja proyek, tempatkan staff, lalu assign PIC pada setiap task.</p>
              </div>
              <button onClick={() => setShowStructure(false)} className="btn-ghost p-2" aria-label="Tutup pengelolaan tim"><X size={17} /></button>
            </div>

            <div className="grid gap-0 lg:grid-cols-[340px_1fr]">
              <div className="border-b border-slate-200 p-5 lg:border-b-0 lg:border-r">
                <h3 className="text-sm font-semibold text-slate-900">Tambah divisi</h3>
                <form
                  className="mt-4 space-y-3"
                  onSubmit={(event) => { event.preventDefault(); createDivision.mutate(divisionForm) }}
                >
                  <div>
                    <label htmlFor="division-name" className="label">Nama divisi *</label>
                    <input id="division-name" required value={divisionForm.division_name} onChange={(event) => setDivisionForm({ ...divisionForm, division_name: event.target.value })} className="input" placeholder="Contoh: QA/QC" />
                  </div>
                  <div>
                    <label htmlFor="division-description" className="label">Tanggung jawab</label>
                    <textarea id="division-description" rows={3} value={divisionForm.description} onChange={(event) => setDivisionForm({ ...divisionForm, description: event.target.value })} className="input resize-none" placeholder="Lingkup dan fungsi utama divisi" />
                  </div>
                  <button disabled={createDivision.isPending} className="btn-primary w-full justify-center"><Plus size={15} /> Tambah divisi</button>
                </form>

                <div className="mt-6 border-t border-slate-200 pt-5">
                  <h3 className="text-sm font-semibold text-slate-900">Template divisi</h3>
                  <p className="mt-1 text-xs text-slate-500">Tambahkan unit umum proyek tanpa mengetik manual.</p>
                  <div className="mt-3 grid max-h-64 gap-2 overflow-y-auto pr-1">
                    {availableDivisionTemplates.map((template) => (
                      <button
                        key={template.division_name}
                        type="button"
                        onClick={() => createDivision.mutate(template)}
                        disabled={createDivision.isPending}
                        className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 text-left transition hover:border-brand-200 hover:bg-brand-50"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-xs font-semibold text-slate-900">{template.division_name}</span>
                          <span className="mt-1 line-clamp-2 block text-[11px] leading-4 text-slate-500">{template.description}</span>
                        </span>
                        <Plus size={14} className="mt-0.5 flex-shrink-0 text-brand-600" />
                      </button>
                    ))}
                    {!availableDivisionTemplates.length && (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">Semua template divisi sudah ada di proyek ini.</div>
                    )}
                  </div>
                </div>

                <div className="mt-6 border-t border-slate-200 pt-5">
                  <h3 className="text-sm font-semibold text-slate-900">Divisi aktif</h3>
                  <div className="mt-3 divide-y divide-slate-100 border-y border-slate-100">
                    {divisions.map((division) => (
                      <div key={division.id} className="flex items-center justify-between gap-3 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-800">{division.division_name}</p>
                          <p className="text-xs text-slate-500">{members.filter((member) => member.division_id === division.id).length} anggota</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => deleteDivision.mutate(division.id)}
                          disabled={deleteDivision.isPending}
                          className="btn-ghost p-2 text-rose-600"
                          title="Hapus divisi"
                        ><Trash2 size={15} /></button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {isAppAdmin ? (
                <div className="border-t border-slate-200 p-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">Batasan role proyek</h3>
                      <p className="mt-1 text-xs leading-5 text-slate-500">
                        Aktifkan hanya role yang relevan agar manager lebih cepat memilih PIC dan struktur tim.
                      </p>
                    </div>
                    <span className="badge badge-info">{assignableRoleCatalog.length}/{roleCatalogWithPolicy.length} aktif</span>
                  </div>
                  <div className="mt-4 max-h-[360px] space-y-4 overflow-y-auto pr-1">
                    {Object.entries(groupedPolicyRoles).map(([category, roles]) => (
                      <div key={category} className="rounded-lg border border-slate-200">
                        <div className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">{category}</div>
                        <div className="divide-y divide-slate-100">
                          {roles.map((role) => {
                            const isPending = updateRolePolicy.isPending && updateRolePolicy.variables?.roleCode === role.code
                            return (
                              <div key={role.code} className="flex flex-col gap-3 p-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-sm font-semibold text-slate-900">{role.label}</p>
                                    <span className="badge-gray">{role.can_be_task_pic ? 'PIC task' : 'Stakeholder'}</span>
                                    {role.requires_division && <span className="badge-gray">Wajib divisi</span>}
                                  </div>
                                  <p className="mt-1 text-xs leading-5 text-slate-500">{role.responsibility}</p>
                                </div>
                                <button
                                  type="button"
                                  disabled={role.code === 'project_admin' || isPending}
                                  onClick={() => updateRolePolicy.mutate({ roleCode: role.code, enabled: !role.enabled })}
                                  className={`flex h-9 min-w-[92px] items-center justify-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition ${
                                    role.enabled ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                  } ${(role.code === 'project_admin' || isPending) ? 'cursor-not-allowed opacity-60' : ''}`}
                                >
                                  {role.enabled ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}
                                  {role.enabled ? 'Aktif' : 'Off'}
                                </button>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : canManage ? (
                <div className="border-t border-slate-200 p-5">
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                    <h3 className="text-sm font-semibold text-amber-900">Struktur admin proyek dikunci</h3>
                    <p className="mt-1 text-xs leading-5 text-amber-800">
                      Manager dapat menempatkan staff operasional. Pembuatan Project Manager, Deputy PM, Sponsor, Owner Rep, dan perubahan policy role dilakukan dari akun admin aplikasi.
                    </p>
                  </div>
                </div>
              ) : null}

              <div className="p-5">
                <h3 className="text-sm font-semibold text-slate-900">Tempatkan staff</h3>
                <form
                  className="mt-4 grid gap-3 md:grid-cols-[1.2fr_1fr_1fr_auto]"
                  onSubmit={(event) => { event.preventDefault(); addMember.mutate() }}
                >
                  <select required value={memberForm.user_id} onChange={(event) => setMemberForm({ ...memberForm, user_id: event.target.value })} className="input" aria-label="Pilih staff">
                    <option value="">Pilih staff...</option>
                    {users.map((user) => <option key={user.id} value={user.id}>{user.name} - {user.role}</option>)}
                  </select>
                  <select required={memberRoleRequiresDivision} value={memberForm.division_id} onChange={(event) => setMemberForm({ ...memberForm, division_id: event.target.value })} className="input" aria-label="Pilih divisi staff">
                    <option value="">{memberRoleRequiresDivision ? 'Pilih divisi...' : 'Tanpa divisi'}</option>
                    {divisions.map((division) => <option key={division.id} value={division.id}>{division.division_name}</option>)}
                  </select>
                  <select value={selectedRoleCode} onChange={(event) => setMemberForm({ ...memberForm, project_role: event.target.value })} className="input" aria-label="Peran proyek">
                    {Object.entries(groupedRoles).map(([category, roles]) => (
                      <optgroup key={category} label={category}>
                        {roles.map((role) => <option key={role.code} value={role.code}>{role.label}</option>)}
                      </optgroup>
                    ))}
                  </select>
                  <button disabled={addMember.isPending || !memberForm.user_id || assignableRoleCatalog.length === 0 || (memberRoleRequiresDivision && !memberForm.division_id)} className="btn-primary justify-center"><UserPlus size={15} /> Tempatkan</button>
                </form>
                {selectedRole && (
                  <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-slate-900">{selectedRole.label}</span>
                      <span className="badge-gray">{selectedRole.category_label}</span>
                      <span className="badge-gray">{selectedRole.can_be_task_pic ? 'Bisa jadi PIC task' : 'Stakeholder/reviewer'}</span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-600">{selectedRole.responsibility}</p>
                    <p className="mt-1 text-xs text-slate-500">Divisi umum: {selectedRole.default_division}</p>
                  </div>
                )}

                <div className="mt-6 overflow-x-auto border border-slate-200">
                  <table className="min-w-[680px] w-full">
                    <thead className="bg-slate-50">
                      <tr>{['Staff', 'Divisi', 'Peran proyek', ''].map((header) => <th key={header} className="px-4 py-3 text-left text-xs font-semibold text-slate-500">{header}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {members.map((member) => {
                        const isProjectAdminMember = PROJECT_ADMIN_ROLE_CODES.has(member.project_role)
                        const canEditMember = isAppAdmin || !isProjectAdminMember
                        return (
                          <tr key={member.id}>
                            <td className="px-4 py-3">
                              <p className="text-sm font-medium text-slate-800">{member.user.name}</p>
                              <p className="text-xs text-slate-500">{member.user.email}</p>
                              {isProjectAdminMember && <p className="mt-1 text-[11px] font-semibold text-amber-700">Admin proyek</p>}
                            </td>
                            <td className="px-4 py-3">
                              <select
                                value={member.division_id ?? ''}
                                disabled={!canEditMember}
                                onChange={(event) => updateMember.mutate({ membershipId: member.id, data: { division_id: event.target.value ? Number(event.target.value) : null } })}
                                className="input py-2 text-xs disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                              >
                                <option value="">Tanpa divisi</option>
                                {divisions.map((division) => <option key={division.id} value={division.id}>{division.division_name}</option>)}
                              </select>
                            </td>
                            <td className="px-4 py-3">
                              <select
                                value={member.project_role}
                                disabled={!canEditMember}
                                onChange={(event) => updateMember.mutate({ membershipId: member.id, data: { project_role: event.target.value } })}
                                className="input py-2 text-xs disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                              >
                                {rolesForMember(member.project_role).map((role) => (
                                  <option key={role.code} value={role.code}>
                                    {role.label}{role.enabled ? '' : ' (nonaktif)'}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                onClick={() => removeMember.mutate(member.id)}
                                disabled={!canEditMember}
                                className="btn-ghost p-2 text-rose-600 disabled:cursor-not-allowed disabled:text-slate-300"
                                title={canEditMember ? 'Keluarkan dari proyek' : 'Hanya admin aplikasi yang dapat mengubah admin proyek'}
                              >
                                <Trash2 size={15} />
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                      {!members.length && <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-slate-500">Belum ada anggota proyek.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
