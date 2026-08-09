'use client'

import { FormEvent, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, ArrowRight, Boxes, CalendarClock, Check, CheckCircle2,
  CircleDollarSign, ClipboardCheck, Database, FileArchive, Gauge, HardHat, Loader2,
  Handshake, PackageCheck, Pencil, Plus, RefreshCw, ShieldAlert, ShieldCheck,
  TrendingUp, Users, X,
} from 'lucide-react'
import toast from 'react-hot-toast'

import { controlsApi, projectsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Project } from '@/types'
import { formatDate } from '@/lib/utils'

type Blocker = { code: string; label: string; entity_id?: number }
type Gate = {
  can_start: boolean
  can_complete: boolean
  start_blockers: Blocker[]
  completion_blockers: Blocker[]
  approved_report_count: number
  required_inspection_count: number
  passed_inspection_count: number
  open_ncr_count: number
  required_material_count: number
  approved_material_count: number
}
type ControlTask = {
  id: number
  title: string
  wbs_code?: string
  status: string
  approval_status?: string
  approval_id?: number
  priority: string
  assigned_to?: number
  deadline?: string
  planned_start?: string
  planned_finish?: string
  location?: string
  unit?: string
  planned_quantity?: number
  actual_quantity: number
  progress_percent: number
  boq_value: number
  budget_cost: number
  actual_cost: number
  internal_material_cost: number
  internal_labor_cost: number
  internal_equipment_cost: number
  internal_overhead_cost: number
  internal_risk_cost: number
  planned_manpower?: number
  planned_equipment?: string
  gate: Gate
  vendor_strategy?: VendorStrategy
}
type VendorCriterion = { key: string; label: string; matched: boolean; weight: number; reason: string }
type VendorCandidate = {
  vendor_id: number
  vendor_name: string
  rate_id: number
  specialty: string
  work_category: string
  unit: string
  unit_price: number
  quantity: number
  base_cost: number
  mobilization_cost: number
  management_cost: number
  risk_cost: number
  total_cost: number
  lead_time_days: number
  rating: number
  match_score: number
  saving_vs_internal: number
  margin?: number | null
  margin_percent?: number | null
}
type ProductivitySnapshot = {
  benchmark_id: number
  work_category: string
  unit: string
  quantity: number
  output_per_day: number
  duration_days: number
  crew_size: number
  labor_cost_per_day: number
  equipment_cost_per_day: number
  material_cost_per_unit: number
  components: Record<string, number>
  total_cost: number
  match_score: number
  confidence_score: number
  source_label: string
  notes?: string
}
type MakeOrBuy = {
  recommendation: string
  label: string
  data_confidence: string
  boq_value: number
  quantity: number
  unit?: string
  internal?: {
    estimated: boolean
    source: string
    total_cost: number
    duration_days?: number
    margin?: number | null
    margin_percent?: number | null
    components: Record<string, number>
    productivity_benchmark?: ProductivitySnapshot | null
  } | null
  productivity_benchmark?: ProductivitySnapshot | null
  productivity_candidates: ProductivitySnapshot[]
  best_vendor?: VendorCandidate | null
  candidates: VendorCandidate[]
  candidate_count: number
  reasons: string[]
}
type VendorStrategy = {
  score: number
  recommendation: 'internal_preferred' | 'vendor_review' | 'vendor_recommended'
  label: string
  criteria: VendorCriterion[]
  make_or_buy: MakeOrBuy
}
type MaterialRow = {
  id: number
  task_id: number
  material_name: string
  material_code?: string
  status: string
  note?: string
}
type InspectionRow = {
  id: number
  task_id: number
  inspection_type: string
  title: string
  status: string
  is_required: boolean
  due_date?: string
  result_note?: string
}
type NcrRow = {
  id: number
  task_id: number
  ncr_number: string
  title: string
  severity: string
  status: string
  assigned_to?: number
  due_date?: string
  corrective_action?: string
}
type HandoverRow = {
  id: number
  task_id?: number
  category: string
  title: string
  status: string
  auto_collected: boolean
}
type ControlsSummary = {
  project: { id: number; name: string; progress_percent: number; contract_value?: number }
  setup: Record<string, boolean>
  metrics: {
    task_count: number
    blocked_task_count: number
    start_blocker_count: number
    completion_blocker_count: number
    pending_material_count: number
    pending_inspection_count: number
    open_ncr_count: number
    overdue_rfi_count: number
    handover_item_count: number
    pending_task_approval_count: number
    vendor_review_count: number
    vendor_recommended_count: number
    make_or_buy_review_count: number
    vendor_saving_potential: number
    progress_percent: number
    budget_cost: number
    actual_cost: number
  }
  s_curve: { date: string; planned_percent: number; actual_percent: number; variance_percent: number }[]
  lookahead: ControlTask[]
  tasks: ControlTask[]
  materials: MaterialRow[]
  inspections: InspectionRow[]
  ncrs: NcrRow[]
  overdue_rfis: { id: number; subject: string; due_date?: string; related_task_id?: number }[]
  handover: HandoverRow[]
}
type MyWork = {
  role: string
  tasks: { id: number; title: string; project_id: number; status: string; deadline?: string; priority: string; progress_percent: number; gate: Gate }[]
  reports: { id: number; task_id: number; status: string; report_date: string; reporter: string }[]
  ncrs: NcrRow[]
}
type ProductivityBenchmark = {
  id: number
  project_id?: number
  work_category: string
  work_keywords?: string
  unit: string
  output_per_day: number
  crew_size: number
  labor_cost_per_day: number
  equipment_cost_per_day: number
  material_cost_per_unit: number
  overhead_percent: number
  risk_percent: number
  confidence_score: number
  source_label: string
  notes?: string
}

const tabs = [
  { id: 'today', label: 'My Work Today', icon: HardHat },
  { id: 'setup', label: 'Project Setup', icon: ClipboardCheck },
  { id: 'timeline', label: 'Timeline', icon: TrendingUp },
  { id: 'lookahead', label: 'Lookahead', icon: CalendarClock },
  { id: 'strategy', label: 'Make-or-Buy', icon: Handshake },
  { id: 'quality', label: 'QA/QC', icon: ShieldCheck },
  { id: 'cost', label: 'Progress & Cost', icon: CircleDollarSign },
  { id: 'closeout', label: 'Closeout', icon: FileArchive },
]

const setupLabels: Record<string, string> = {
  contract_ready: 'Kontrak terdaftar',
  wbs_ready: 'WBS dan acceptance criteria',
  boq_baseline_ready: 'Baseline volume BOQ',
  schedule_ready: 'Baseline schedule',
  organization_ready: 'Divisi dan project team',
  document_structure_ready: 'Document register',
}

const statusClass = (status: string) => {
  if (['approved', 'passed', 'closed', 'done'].includes(status)) return 'badge-success'
  if (['failed', 'rejected', 'blocked', 'critical'].includes(status)) return 'badge-danger'
  if (['pending', 'submitted', 'open', 'ready_for_close'].includes(status)) return 'badge-warning'
  return 'badge-info'
}

const currency = (value?: number) => `Rp ${(value || 0).toLocaleString('id-ID')}`
const number = (value?: number) => (value || 0).toLocaleString('id-ID', { maximumFractionDigits: 2 })

function SCurveChart({ data }: { data: ControlsSummary['s_curve'] }) {
  if (!data.length) {
    return (
      <div className="flex min-h-64 items-center justify-center border border-dashed border-slate-300 bg-white text-sm text-slate-500">
        Baseline schedule belum cukup untuk membentuk S-curve.
      </div>
    )
  }
  const width = 760
  const height = 260
  const padding = 36
  const x = (index: number) => padding + (index / Math.max(1, data.length - 1)) * (width - padding * 2)
  const y = (value: number) => padding + ((100 - Math.max(0, Math.min(100, value))) / 100) * (height - padding * 2)
  const path = (key: 'planned_percent' | 'actual_percent') =>
    data.map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(point[key])}`).join(' ')
  const latest = data[data.length - 1]

  return (
    <div className="border border-slate-200 bg-white p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Project S-Curve</h2>
          <p className="mt-1 text-xs text-slate-500">Baseline plan dibandingkan dengan actual progress dari laporan approved.</p>
        </div>
        <div className={`rounded-lg px-3 py-2 text-xs font-semibold ${latest.variance_percent >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
          Variance {number(latest.variance_percent)}%
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-72 w-full">
        {[0, 25, 50, 75, 100].map((tick) => (
          <g key={tick}>
            <line x1={padding} x2={width - padding} y1={y(tick)} y2={y(tick)} className="stroke-slate-100" />
            <text x={8} y={y(tick) + 4} className="fill-slate-400 text-[11px]">{tick}%</text>
          </g>
        ))}
        <path d={path('planned_percent')} fill="none" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" />
        <path d={path('actual_percent')} fill="none" stroke="#0891b2" strokeWidth="3" strokeLinecap="round" />
        {data.map((point, index) => (
          <circle key={`${point.date}-${index}`} cx={x(index)} cy={y(point.actual_percent)} r="3.5" className="fill-cyan-600" />
        ))}
      </svg>
      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs font-semibold text-slate-600">
        <span className="inline-flex items-center gap-2"><span className="h-1 w-8 rounded-full bg-slate-900" /> Planned</span>
        <span className="inline-flex items-center gap-2"><span className="h-1 w-8 rounded-full bg-cyan-600" /> Actual</span>
        <span>Actual terakhir: {number(latest.actual_percent)}%</span>
        <span>Planned terakhir: {number(latest.planned_percent)}%</span>
      </div>
    </div>
  )
}

export default function ControlsPage() {
  const qc = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const isReviewer = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const visibleTabs = isReviewer ? tabs : tabs.filter((tab) => tab.id !== 'cost')
  const [activeTab, setActiveTab] = useState('today')
  const [projectId, setProjectId] = useState<number | null>(null)
  const [planTask, setPlanTask] = useState<ControlTask | null>(null)
  const [planForm, setPlanForm] = useState({
    planned_start: '', planned_finish: '', location: '', unit: '', planned_quantity: '',
    weight_percent: '', boq_value: '', budget_cost: '',
    internal_material_cost: '', internal_labor_cost: '', internal_equipment_cost: '',
    internal_overhead_cost: '', internal_risk_cost: '',
    planned_manpower: '', planned_equipment: '',
    depends_on_task_id: '', dependency_type: 'finish_to_start', lag_days: '0',
  })
  const [inspectionForm, setInspectionForm] = useState({ task_id: '', title: '', inspection_type: 'work_inspection', due_date: '' })
  const [productivityForm, setProductivityForm] = useState({
    work_category: 'finishing',
    work_keywords: 'cat, pengecatan, painting, dinding',
    unit: 'm2',
    output_per_day: '30',
    crew_size: '3',
    labor_cost_per_day: '550000',
    equipment_cost_per_day: '75000',
    material_cost_per_unit: '23000',
    overhead_percent: '8',
    risk_percent: '5',
    confidence_score: '80',
    source_label: 'manual-project',
    notes: '',
  })

  const projectsQuery = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  const projects = projectsQuery.data || []

  useEffect(() => {
    if (!projectId && projects.length) setProjectId(projects[0].id)
  }, [projectId, projects])

  const summaryQuery = useQuery<ControlsSummary>({
    queryKey: ['controls-summary', projectId],
    queryFn: async () => (await controlsApi.summary(projectId!)).data,
    enabled: Boolean(projectId),
    refetchInterval: 20_000,
  })
  const myWorkQuery = useQuery<MyWork>({
    queryKey: ['my-work'],
    queryFn: async () => (await controlsApi.myWork()).data,
    refetchInterval: 20_000,
  })
  const productivityQuery = useQuery<ProductivityBenchmark[]>({
    queryKey: ['productivity', projectId],
    queryFn: async () => (await controlsApi.productivity(projectId!)).data,
    enabled: Boolean(projectId && isReviewer),
  })
  const summary = summaryQuery.data
  const myWork = myWorkQuery.data
  const productivityBenchmarks = productivityQuery.data || []

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['controls-summary'] })
    qc.invalidateQueries({ queryKey: ['my-work'] })
    qc.invalidateQueries({ queryKey: ['tasks'] })
    qc.invalidateQueries({ queryKey: ['projects'] })
    qc.invalidateQueries({ queryKey: ['productivity'] })
  }

  const baselineMutation = useMutation({
    mutationFn: () => controlsApi.bootstrapBaseline(projectId!),
    onSuccess: (response) => { refresh(); toast.success(`${response.data.created} baseline task dibuat`) },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Baseline gagal dibuat'),
  })
  const materialMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => controlsApi.decideMaterial(id, status),
    onSuccess: () => { refresh(); toast.success('Status material diperbarui') },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Material approval gagal'),
  })
  const inspectionMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => controlsApi.createInspection(payload),
    onSuccess: () => {
      refresh()
      setInspectionForm({ task_id: '', title: '', inspection_type: 'work_inspection', due_date: '' })
      toast.success('Inspection request dibuat')
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Inspection request gagal'),
  })
  const inspectionDecisionMutation = useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: string; note?: string }) =>
      controlsApi.decideInspection(id, {
        status, result_note: note, ncr_title: status === 'failed' ? `NCR dari inspection #${id}` : undefined,
      }),
    onSuccess: (_, variables) => {
      refresh()
      toast.success(variables.status === 'failed' ? 'Inspection gagal, NCR dan blocker dibuat' : 'Inspection dinyatakan passed')
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Keputusan inspeksi gagal'),
  })
  const ncrMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) => controlsApi.updateNcr(id, payload),
    onSuccess: () => { refresh(); toast.success('NCR diperbarui') },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'NCR gagal diperbarui'),
  })
  const planMutation = useMutation({
    mutationFn: async ({ id, payload, dependency }: { id: number; payload: Record<string, unknown>; dependency?: Record<string, unknown> }) => {
      const response = await controlsApi.updateTaskPlan(id, payload)
      if (dependency) await controlsApi.addDependency(id, dependency)
      return response
    },
    onSuccess: () => { refresh(); setPlanTask(null); toast.success('Baseline task diperbarui') },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Baseline task gagal disimpan'),
  })
  const handoverMutation = useMutation({
    mutationFn: () => controlsApi.refreshHandover(projectId!),
    onSuccess: () => { refresh(); toast.success('Handover dossier diperbarui') },
    onError: () => toast.error('Dossier gagal diperbarui'),
  })
  const productivityMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => controlsApi.createProductivity(projectId!, payload),
    onSuccess: () => {
      refresh()
      setProductivityForm({
        ...productivityForm,
        notes: '',
      })
      toast.success('Benchmark produktivitas ditambahkan')
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Benchmark produktivitas gagal disimpan'),
  })

  const currentProjectTasks = useMemo(
    () => summary?.tasks || [],
    [summary],
  )

  function openPlan(task: ControlTask) {
    setPlanTask(task)
    setPlanForm({
      planned_start: task.planned_start?.slice(0, 10) || '',
      planned_finish: task.planned_finish?.slice(0, 10) || '',
      location: task.location || '', unit: task.unit || '',
      planned_quantity: task.planned_quantity == null ? '' : String(task.planned_quantity),
      weight_percent: '', boq_value: task.boq_value ? String(task.boq_value) : '',
      budget_cost: task.budget_cost ? String(task.budget_cost) : '',
      internal_material_cost: task.internal_material_cost ? String(task.internal_material_cost) : '',
      internal_labor_cost: task.internal_labor_cost ? String(task.internal_labor_cost) : '',
      internal_equipment_cost: task.internal_equipment_cost ? String(task.internal_equipment_cost) : '',
      internal_overhead_cost: task.internal_overhead_cost ? String(task.internal_overhead_cost) : '',
      internal_risk_cost: task.internal_risk_cost ? String(task.internal_risk_cost) : '',
      planned_manpower: task.planned_manpower == null ? '' : String(task.planned_manpower),
      planned_equipment: task.planned_equipment || '',
      depends_on_task_id: '', dependency_type: 'finish_to_start', lag_days: '0',
    })
  }

  function savePlan(event: FormEvent) {
    event.preventDefault()
    if (!planTask) return
    planMutation.mutate({ id: planTask.id, payload: {
      planned_start: planForm.planned_start || null,
      planned_finish: planForm.planned_finish || null,
      location: planForm.location || null,
      unit: planForm.unit || null,
      planned_quantity: planForm.planned_quantity ? Number(planForm.planned_quantity) : null,
      weight_percent: planForm.weight_percent ? Number(planForm.weight_percent) : null,
      boq_value: planForm.boq_value ? Number(planForm.boq_value) : 0,
      budget_cost: planForm.budget_cost ? Number(planForm.budget_cost) : 0,
      internal_material_cost: planForm.internal_material_cost ? Number(planForm.internal_material_cost) : 0,
      internal_labor_cost: planForm.internal_labor_cost ? Number(planForm.internal_labor_cost) : 0,
      internal_equipment_cost: planForm.internal_equipment_cost ? Number(planForm.internal_equipment_cost) : 0,
      internal_overhead_cost: planForm.internal_overhead_cost ? Number(planForm.internal_overhead_cost) : 0,
      internal_risk_cost: planForm.internal_risk_cost ? Number(planForm.internal_risk_cost) : 0,
      planned_manpower: planForm.planned_manpower ? Number(planForm.planned_manpower) : null,
      planned_equipment: planForm.planned_equipment || null,
    }, dependency: planForm.depends_on_task_id ? {
      depends_on_task_id: Number(planForm.depends_on_task_id),
      dependency_type: planForm.dependency_type,
      lag_days: Number(planForm.lag_days || 0),
    } : undefined })
  }

  function createInspection(event: FormEvent) {
    event.preventDefault()
    inspectionMutation.mutate({
      project_id: projectId,
      task_id: Number(inspectionForm.task_id),
      title: inspectionForm.title,
      inspection_type: inspectionForm.inspection_type,
      due_date: inspectionForm.due_date || null,
      is_required: true,
    })
  }

  function createProductivity(event: FormEvent) {
    event.preventDefault()
    productivityMutation.mutate({
      work_category: productivityForm.work_category,
      work_keywords: productivityForm.work_keywords || null,
      unit: productivityForm.unit,
      output_per_day: Number(productivityForm.output_per_day),
      crew_size: Number(productivityForm.crew_size),
      labor_cost_per_day: Number(productivityForm.labor_cost_per_day || 0),
      equipment_cost_per_day: Number(productivityForm.equipment_cost_per_day || 0),
      material_cost_per_unit: Number(productivityForm.material_cost_per_unit || 0),
      overhead_percent: Number(productivityForm.overhead_percent || 0),
      risk_percent: Number(productivityForm.risk_percent || 0),
      confidence_score: Number(productivityForm.confidence_score || 75),
      source_label: productivityForm.source_label || 'manual-project',
      notes: productivityForm.notes || null,
    })
  }

  const metrics = summary?.metrics
  const kpis = [
    { label: 'Physical progress', value: `${number(metrics?.progress_percent)}%`, icon: Gauge, tone: 'bg-cyan-50 text-cyan-700' },
    { label: 'Pending task approval', value: metrics?.pending_task_approval_count || 0, icon: ClipboardCheck, tone: 'bg-amber-50 text-amber-700' },
    { label: 'Start blockers', value: metrics?.start_blocker_count || 0, icon: ShieldAlert, tone: 'bg-rose-50 text-rose-700' },
    { label: 'Make-or-buy review', value: metrics?.make_or_buy_review_count || 0, icon: Handshake, tone: 'bg-violet-50 text-violet-700' },
    { label: 'Material pending', value: metrics?.pending_material_count || 0, icon: PackageCheck, tone: 'bg-amber-50 text-amber-700' },
    { label: 'Inspection pending', value: metrics?.pending_inspection_count || 0, icon: ClipboardCheck, tone: 'bg-blue-50 text-blue-700' },
    { label: 'Saving potential', value: currency(metrics?.vendor_saving_potential), icon: CircleDollarSign, tone: 'bg-emerald-50 text-emerald-700' },
    { label: 'Open NCR', value: metrics?.open_ncr_count || 0, icon: AlertTriangle, tone: 'bg-orange-50 text-orange-700' },
  ]

  return (
    <div className="space-y-6 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-cyan-700">
            <HardHat size={14} /> Construction project controls
          </div>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">Project Controls</h1>
          <p className="mt-1 text-sm text-slate-500">{summary?.project.name || 'Pilih proyek aktif'}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={projectId || ''} onChange={(event) => setProjectId(Number(event.target.value))} className="input min-w-64">
            {projects.map((project) => <option key={project.id} value={project.id}>{project.project_name}</option>)}
          </select>
          {isReviewer && (
            <button type="button" onClick={() => baselineMutation.mutate()} disabled={!projectId || baselineMutation.isPending} className="btn-secondary">
              {baselineMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Boxes size={15} />} Baseline
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 2xl:grid-cols-8">
        {kpis.map((item) => <div key={item.label} className="border border-slate-200 bg-white p-4 shadow-sm">
          <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${item.tone}`}><item.icon size={18} /></div>
          <p className="mt-3 text-2xl font-bold text-slate-950">{item.value}</p>
          <p className="mt-0.5 text-xs font-medium text-slate-500">{item.label}</p>
        </div>)}
      </div>

      <div className="overflow-x-auto border-b border-slate-200">
        <div className="flex min-w-max gap-1">
          {visibleTabs.map((tab) => <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === tab.id ? 'border-cyan-600 text-cyan-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
            <tab.icon size={16} /> {tab.label}
          </button>)}
        </div>
      </div>

      {(summaryQuery.isLoading || myWorkQuery.isLoading) && <div className="flex min-h-72 items-center justify-center"><Loader2 className="animate-spin text-cyan-600" /></div>}

      {activeTab === 'today' && myWork && <section className="space-y-5">
        <div className="flex items-center justify-between"><div><h2 className="text-lg font-bold text-slate-900">My Work Today</h2><p className="text-xs font-medium uppercase text-slate-400">Role: {myWork.role}</p></div><span className="badge-info">{myWork.tasks.length} task aktif</span></div>
        <div className="grid gap-5 xl:grid-cols-3">
          <div className="overflow-hidden border border-slate-200 bg-white xl:col-span-2">
            <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800">Priority work</div>
            <div className="divide-y divide-slate-100">
              {myWork.tasks.slice(0, 10).map((task) => <Link key={task.id} href={`/tasks/${task.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
                <span className={`h-2.5 w-2.5 rounded-full ${task.gate.can_start ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-800">{task.title}</p><p className="mt-0.5 text-xs text-slate-500">{task.deadline ? formatDate(task.deadline) : 'Tanpa deadline'} | {number(task.progress_percent)}%</p></div>
                <span className={statusClass(task.status)}>{task.status}</span><ArrowRight size={15} className="text-slate-300" />
              </Link>)}
              {!myWork.tasks.length && <p className="p-5 text-sm text-slate-500">Tidak ada task aktif.</p>}
            </div>
          </div>
          <div className="space-y-4">
            <div className="border border-slate-200 bg-white p-4"><h3 className="text-sm font-semibold text-slate-800">Report queue</h3><p className="mt-2 text-3xl font-bold text-slate-950">{myWork.reports.length}</p><Link href="/reports" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-cyan-700">Buka laporan <ArrowRight size={13} /></Link></div>
            <div className="border border-slate-200 bg-white p-4"><h3 className="text-sm font-semibold text-slate-800">Assigned NCR</h3><p className="mt-2 text-3xl font-bold text-slate-950">{myWork.ncrs.length}</p><button type="button" onClick={() => setActiveTab('quality')} className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-cyan-700">Buka QA/QC <ArrowRight size={13} /></button></div>
          </div>
        </div>
      </section>}

      {activeTab === 'setup' && summary && <section className="space-y-5">
        <div className="flex items-center justify-between"><h2 className="text-lg font-bold text-slate-900">Project Setup Readiness</h2><span className="badge-info">{Object.values(summary.setup).filter(Boolean).length}/{Object.keys(summary.setup).length}</span></div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(summary.setup).map(([key, ready]) => <div key={key} className="flex items-center gap-3 border border-slate-200 bg-white p-4">
            <div className={`flex h-9 w-9 items-center justify-center rounded-full ${ready ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{ready ? <Check size={17} /> : <AlertTriangle size={17} />}</div>
            <div><p className="text-sm font-semibold text-slate-800">{setupLabels[key] || key}</p><p className="text-xs text-slate-500">{ready ? 'Ready' : 'Belum lengkap'}</p></div>
          </div>)}
        </div>
        <div className="flex flex-wrap gap-2"><Link href="/documents" className="btn-secondary">Document register</Link><Link href="/projects" className="btn-secondary">Project & team</Link><Link href="/tasks" className="btn-secondary">WBS & task</Link></div>
      </section>}

      {activeTab === 'timeline' && summary && <section className="space-y-5">
        <SCurveChart data={summary.s_curve || []} />
        <div className="overflow-x-auto border border-slate-200 bg-white">
          <table className="min-w-[980px] w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">WBS / pekerjaan</th><th className="px-4 py-3">Approval</th><th className="px-4 py-3">Baseline</th><th className="px-4 py-3">Progress</th><th className="px-4 py-3">Gate</th><th className="px-4 py-3"></th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.tasks.map((task) => (
                <tr key={task.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/tasks/${task.id}`} className="font-semibold text-slate-800 hover:text-cyan-700">{task.title}</Link>
                    <p className="text-xs text-slate-400">{task.wbs_code || 'WBS belum diisi'} | {task.location || 'Lokasi belum diisi'}</p>
                  </td>
                  <td className="px-4 py-3"><span className={statusClass(task.approval_status || 'approved')}>{task.approval_status || 'approved'}</span></td>
                  <td className="px-4 py-3 text-xs text-slate-600">{task.planned_start ? formatDate(task.planned_start) : '-'}<br />{task.planned_finish ? formatDate(task.planned_finish) : '-'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2"><div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-cyan-500" style={{ width: `${Math.min(100, task.progress_percent)}%` }} /></div><span className="text-xs font-semibold text-slate-700">{number(task.progress_percent)}%</span></div>
                  </td>
                  <td className="px-4 py-3"><span className={task.gate.can_start ? 'badge-success' : 'badge-danger'}>{task.gate.can_start ? 'Ready' : `${task.gate.start_blockers.length} blocker`}</span></td>
                  <td className="px-4 py-3">{isReviewer && <button type="button" onClick={() => openPlan(task)} className="btn-ghost p-2" title="Ubah baseline"><Pencil size={15} /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>}

      {activeTab === 'strategy' && summary && <section className="space-y-5">
        <div className="grid gap-4 md:grid-cols-4">
          <div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Perlu review teknis</p><p className="mt-2 text-2xl font-bold text-slate-950">{metrics?.vendor_review_count || 0}</p></div>
          <div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Rekomendasi vendor</p><p className="mt-2 text-2xl font-bold text-slate-950">{metrics?.vendor_recommended_count || 0}</p></div>
          <div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Make-or-buy review</p><p className="mt-2 text-2xl font-bold text-slate-950">{metrics?.make_or_buy_review_count || 0}</p></div>
          <div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Potensi saving vendor</p><p className="mt-2 text-2xl font-bold text-emerald-700">{currency(metrics?.vendor_saving_potential)}</p></div>
        </div>
        {isReviewer && <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="overflow-hidden border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h2 className="font-bold text-slate-900">Database Produktivitas Internal</h2>
                <p className="mt-0.5 text-xs text-slate-500">Output per hari, crew, dan biaya internal sebagai pembanding vendor.</p>
              </div>
              <span className="badge-info">{productivityBenchmarks.length} benchmark</span>
            </div>
            <div className="max-h-80 overflow-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                  <tr><th className="px-4 py-3">Kategori</th><th className="px-4 py-3">Output</th><th className="px-4 py-3">Crew</th><th className="px-4 py-3">Biaya/hari</th><th className="px-4 py-3">Material/unit</th><th className="px-4 py-3">Confidence</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {productivityBenchmarks.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3"><p className="font-semibold text-slate-800">{item.work_category}</p><p className="text-xs text-slate-400">{item.work_keywords || item.source_label}</p></td>
                      <td className="px-4 py-3 font-semibold text-slate-700">{number(item.output_per_day)} {item.unit}/hari</td>
                      <td className="px-4 py-3 text-slate-600">{item.crew_size} orang</td>
                      <td className="px-4 py-3 text-slate-600">{currency(item.labor_cost_per_day + item.equipment_cost_per_day)}</td>
                      <td className="px-4 py-3 text-slate-600">{currency(item.material_cost_per_unit)}</td>
                      <td className="px-4 py-3"><span className="badge-success">{number(item.confidence_score)}%</span></td>
                    </tr>
                  ))}
                  {!productivityBenchmarks.length && <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-500">Belum ada benchmark produktivitas.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
          <form onSubmit={createProductivity} className="border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center gap-2">
              <Database size={17} className="text-cyan-700" />
              <h2 className="font-bold text-slate-900">Tambah Benchmark</h2>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="label">Kategori<input required value={productivityForm.work_category} onChange={(e) => setProductivityForm({ ...productivityForm, work_category: e.target.value })} className="input mt-1" /></label>
              <label className="label">Satuan<input required value={productivityForm.unit} onChange={(e) => setProductivityForm({ ...productivityForm, unit: e.target.value })} className="input mt-1" /></label>
              <label className="label md:col-span-2">Keyword<input value={productivityForm.work_keywords} onChange={(e) => setProductivityForm({ ...productivityForm, work_keywords: e.target.value })} className="input mt-1" /></label>
              <label className="label">Output/hari<input required type="number" min="0.01" step="any" value={productivityForm.output_per_day} onChange={(e) => setProductivityForm({ ...productivityForm, output_per_day: e.target.value })} className="input mt-1" /></label>
              <label className="label">Crew<input required type="number" min="1" value={productivityForm.crew_size} onChange={(e) => setProductivityForm({ ...productivityForm, crew_size: e.target.value })} className="input mt-1" /></label>
              <label className="label">Biaya tenaga/hari<input type="number" min="0" step="any" value={productivityForm.labor_cost_per_day} onChange={(e) => setProductivityForm({ ...productivityForm, labor_cost_per_day: e.target.value })} className="input mt-1" /></label>
              <label className="label">Biaya alat/hari<input type="number" min="0" step="any" value={productivityForm.equipment_cost_per_day} onChange={(e) => setProductivityForm({ ...productivityForm, equipment_cost_per_day: e.target.value })} className="input mt-1" /></label>
              <label className="label">Material/unit<input type="number" min="0" step="any" value={productivityForm.material_cost_per_unit} onChange={(e) => setProductivityForm({ ...productivityForm, material_cost_per_unit: e.target.value })} className="input mt-1" /></label>
              <label className="label">Confidence (%)<input type="number" min="0" max="100" step="any" value={productivityForm.confidence_score} onChange={(e) => setProductivityForm({ ...productivityForm, confidence_score: e.target.value })} className="input mt-1" /></label>
              <label className="label">Overhead (%)<input type="number" min="0" step="any" value={productivityForm.overhead_percent} onChange={(e) => setProductivityForm({ ...productivityForm, overhead_percent: e.target.value })} className="input mt-1" /></label>
              <label className="label">Risk (%)<input type="number" min="0" step="any" value={productivityForm.risk_percent} onChange={(e) => setProductivityForm({ ...productivityForm, risk_percent: e.target.value })} className="input mt-1" /></label>
              <label className="label md:col-span-2">Catatan<input value={productivityForm.notes} onChange={(e) => setProductivityForm({ ...productivityForm, notes: e.target.value })} className="input mt-1" placeholder="Contoh: pengecatan standar 30 m2/hari" /></label>
            </div>
            <button disabled={productivityMutation.isPending || !projectId} className="btn-primary mt-4">
              {productivityMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Simpan benchmark
            </button>
          </form>
        </div>}
        <div className="grid gap-4">
          {[...summary.tasks].sort((a, b) => {
            const aScore = a.vendor_strategy?.make_or_buy?.best_vendor?.saving_vs_internal || a.vendor_strategy?.score || 0
            const bScore = b.vendor_strategy?.make_or_buy?.best_vendor?.saving_vs_internal || b.vendor_strategy?.score || 0
            return bScore - aScore
          }).map((task) => {
            const strategy = task.vendor_strategy
            const makeOrBuy = strategy?.make_or_buy
            const matched = strategy?.criteria.filter((criterion) => criterion.matched) || []
            const bestVendor = makeOrBuy?.best_vendor
            const recClass = makeOrBuy?.recommendation === 'vendor_recommended'
              ? 'bg-rose-50 text-rose-700'
              : makeOrBuy?.recommendation === 'vendor_review'
                ? 'bg-amber-50 text-amber-700'
                : makeOrBuy?.recommendation === 'hybrid_review'
                  ? 'bg-violet-50 text-violet-700'
                  : makeOrBuy?.recommendation === 'internal_preferred'
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-slate-100 text-slate-600'
            return (
              <div key={task.id} className="border border-slate-200 bg-white p-5">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <Link href={`/tasks/${task.id}`} className="font-semibold text-slate-900 hover:text-cyan-700">{task.title}</Link>
                    <p className="mt-1 text-xs text-slate-500">{task.wbs_code || 'WBS belum diisi'} | {task.location || 'Lokasi belum diisi'} | {number(makeOrBuy?.quantity)} {makeOrBuy?.unit || task.unit || ''}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-lg px-3 py-2 text-xs font-bold ${strategy?.recommendation === 'vendor_recommended' ? 'bg-rose-50 text-rose-700' : strategy?.recommendation === 'vendor_review' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>{strategy?.score || 0}/100</span>
                    <span className={`rounded-lg px-3 py-2 text-xs font-bold ${recClass}`}>{makeOrBuy?.label || 'Belum dianalisis'}</span>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 lg:grid-cols-4">
                  <div className="border border-slate-100 bg-slate-50 p-3">
                    <p className="text-xs font-semibold uppercase text-slate-400">Nilai BOQ / Budget item</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{currency(makeOrBuy?.boq_value || task.boq_value || task.budget_cost)}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">Confidence: {makeOrBuy?.data_confidence || '-'}</p>
                  </div>
                  <div className="border border-slate-100 bg-white p-3">
                    <p className="text-xs font-semibold uppercase text-slate-400">Estimasi internal</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{currency(makeOrBuy?.internal?.total_cost)}</p>
                    <p className={`mt-0.5 text-[11px] font-semibold ${(makeOrBuy?.internal?.margin || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>Margin {makeOrBuy?.internal?.margin == null ? '-' : currency(makeOrBuy.internal.margin)}</p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      {makeOrBuy?.internal?.source === 'productivity_benchmark' && makeOrBuy.internal.productivity_benchmark
                        ? `${number(makeOrBuy.internal.productivity_benchmark.output_per_day)} ${makeOrBuy.internal.productivity_benchmark.unit}/hari | ${makeOrBuy.internal.productivity_benchmark.duration_days} hari`
                        : `Source: ${makeOrBuy?.internal?.source || '-'}`}
                    </p>
                  </div>
                  <div className="border border-slate-100 bg-white p-3">
                    <p className="text-xs font-semibold uppercase text-slate-400">Vendor terbaik</p>
                    <p className="mt-1 truncate text-sm font-bold text-slate-900">{bestVendor?.vendor_name || 'Belum ada kandidat'}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">{bestVendor ? `${currency(bestVendor.total_cost)} | rating ${number(bestVendor.rating)}` : 'Tambahkan rate card vendor'}</p>
                  </div>
                  <div className="border border-slate-100 bg-white p-3">
                    <p className="text-xs font-semibold uppercase text-slate-400">Selisih vs internal</p>
                    <p className={`mt-1 text-lg font-bold ${(bestVendor?.saving_vs_internal || 0) > 0 ? 'text-emerald-700' : 'text-slate-900'}`}>{bestVendor ? currency(bestVendor.saving_vs_internal) : '-'}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">{makeOrBuy?.candidate_count || 0} kandidat vendor cocok</p>
                  </div>
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                  <div className="border border-slate-100 bg-slate-50 p-3">
                    <p className="text-xs font-bold uppercase text-slate-500">Alasan rekomendasi</p>
                    <div className="mt-2 space-y-1">
                      {(makeOrBuy?.reasons || ['Belum ada alasan analisis.']).map((reason) => <p key={reason} className="text-xs leading-5 text-slate-600">- {reason}</p>)}
                    </div>
                  </div>
                  <div className="border border-slate-100 bg-white p-3">
                    <p className="text-xs font-bold uppercase text-slate-500">Parameter teknis aktif</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {matched.map((criterion) => <span key={criterion.key} className="rounded-md bg-cyan-50 px-2 py-1 text-[11px] font-semibold text-cyan-700">+{criterion.weight} {criterion.label}</span>)}
                      {!matched.length && <span className="text-xs text-slate-500">Tidak ada parameter kuat untuk alih vendor pada task ini.</span>}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </section>}

      {activeTab === 'lookahead' && summary && <section className="space-y-4">
        <div className="flex items-center justify-between"><h2 className="text-lg font-bold text-slate-900">3-Week Lookahead</h2><span className="badge-info">{summary.lookahead.length} work item</span></div>
        <div className="overflow-x-auto border border-slate-200 bg-white"><table className="min-w-[1050px] w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">WBS / pekerjaan</th><th className="px-4 py-3">Lokasi</th><th className="px-4 py-3">Rencana</th><th className="px-4 py-3">Volume</th><th className="px-4 py-3">Resource</th><th className="px-4 py-3">Gate</th><th className="px-4 py-3"></th></tr></thead>
          <tbody className="divide-y divide-slate-100">{summary.lookahead.map((task) => <tr key={task.id} className="hover:bg-slate-50"><td className="px-4 py-3"><Link href={`/tasks/${task.id}`} className="font-semibold text-slate-800 hover:text-cyan-700">{task.title}</Link><p className="text-xs text-slate-400">{task.wbs_code || 'WBS belum diisi'} | {number(task.progress_percent)}%</p></td><td className="px-4 py-3 text-slate-600">{task.location || '-'}</td><td className="px-4 py-3 text-xs text-slate-600">{task.planned_start ? formatDate(task.planned_start) : '-'}<br />{task.planned_finish ? formatDate(task.planned_finish) : '-'}</td><td className="px-4 py-3 text-slate-700">{number(task.actual_quantity)} / {number(task.planned_quantity)} {task.unit || ''}</td><td className="px-4 py-3 text-xs text-slate-600">{task.planned_manpower || 0} orang<br />{task.planned_equipment || '-'}</td><td className="px-4 py-3"><span className={task.gate.can_start ? 'badge-success' : 'badge-danger'}>{task.gate.can_start ? 'Ready' : `${task.gate.start_blockers.length} blocker`}</span></td><td className="px-4 py-3">{isReviewer && <button type="button" onClick={() => openPlan(task)} className="btn-ghost p-2" title="Ubah baseline"><Pencil size={15} /></button>}</td></tr>)}</tbody>
        </table></div>
      </section>}

      {activeTab === 'quality' && summary && <section className="space-y-6">
        <div className="grid gap-6 xl:grid-cols-2">
          <div className="border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-200 px-4 py-3"><h2 className="font-bold text-slate-900">Material Approval</h2><span className="badge-warning">{summary.materials.filter((item) => item.status !== 'approved').length} pending</span></div><div className="divide-y divide-slate-100">{summary.materials.map((material) => <div key={material.id} className="flex items-center gap-3 px-4 py-3"><PackageCheck size={17} className="text-slate-400" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-800">{material.material_name}</p><p className="text-xs text-slate-500">{material.material_code || 'Tanpa kode'} | Task #{material.task_id}</p></div><span className={statusClass(material.status)}>{material.status}</span>{material.status !== 'approved' && <div className="flex gap-1">{material.status === 'pending' && <button type="button" onClick={() => materialMutation.mutate({ id: material.id, status: 'submitted' })} className="btn-ghost px-2 py-1 text-xs">Submit</button>}{isReviewer && <button type="button" onClick={() => materialMutation.mutate({ id: material.id, status: 'approved' })} className="btn-ghost p-2 text-emerald-700" title="Approve"><Check size={15} /></button>}{isReviewer && <button type="button" onClick={() => materialMutation.mutate({ id: material.id, status: 'rejected' })} className="btn-ghost p-2 text-rose-700" title="Reject"><X size={15} /></button>}</div>}</div>)}</div></div>
          <div className="border border-slate-200 bg-white"><div className="border-b border-slate-200 px-4 py-3"><h2 className="font-bold text-slate-900">New Inspection Request</h2></div><form onSubmit={createInspection} className="grid gap-3 p-4"><select required value={inspectionForm.task_id} onChange={(e) => setInspectionForm({ ...inspectionForm, task_id: e.target.value })} className="input"><option value="">Pilih task</option>{currentProjectTasks.map((task) => <option key={task.id} value={task.id}>{task.wbs_code ? `${task.wbs_code} - ` : ''}{task.title}</option>)}</select><div className="grid gap-3 md:grid-cols-2"><select value={inspectionForm.inspection_type} onChange={(e) => setInspectionForm({ ...inspectionForm, inspection_type: e.target.value })} className="input"><option value="itp">ITP Hold/Witness Point</option><option value="work_inspection">Work Inspection</option><option value="material_test">Material Test</option><option value="test_result">Test Result</option></select><input type="date" value={inspectionForm.due_date} onChange={(e) => setInspectionForm({ ...inspectionForm, due_date: e.target.value })} className="input" /></div><input required value={inspectionForm.title} onChange={(e) => setInspectionForm({ ...inspectionForm, title: e.target.value })} className="input" placeholder="Judul inspection request" /><button disabled={inspectionMutation.isPending} className="btn-primary justify-self-start"><Plus size={15} /> Buat IR</button></form></div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="overflow-hidden border border-slate-200 bg-white"><div className="border-b border-slate-200 px-4 py-3 font-bold text-slate-900">Inspection Register</div><div className="divide-y divide-slate-100">{summary.inspections.map((inspection) => <div key={inspection.id} className="p-4"><div className="flex items-start gap-3"><ClipboardCheck size={17} className="mt-0.5 text-slate-400" /><div className="min-w-0 flex-1"><p className="font-semibold text-slate-800">{inspection.title}</p><p className="text-xs text-slate-500">{inspection.inspection_type} | Task #{inspection.task_id} | {inspection.due_date ? formatDate(inspection.due_date) : 'Tanpa due date'}</p>{inspection.result_note && <p className="mt-1 text-xs text-slate-600">{inspection.result_note}</p>}</div><span className={statusClass(inspection.status)}>{inspection.status}</span></div>{inspection.status === 'pending' && isReviewer && <div className="mt-3 flex justify-end gap-2"><button type="button" onClick={() => inspectionDecisionMutation.mutate({ id: inspection.id, status: 'passed', note: 'Sesuai ITP dan acceptance criteria' })} className="btn-secondary text-emerald-700"><CheckCircle2 size={15} /> Pass</button><button type="button" onClick={() => { const note = window.prompt('Temuan inspeksi') || 'Tidak sesuai acceptance criteria'; inspectionDecisionMutation.mutate({ id: inspection.id, status: 'failed', note }) }} className="btn-secondary text-rose-700"><AlertTriangle size={15} /> Fail + NCR</button></div>}</div>)}</div></div>
          <div className="overflow-hidden border border-slate-200 bg-white"><div className="border-b border-slate-200 px-4 py-3 font-bold text-slate-900">NCR Register</div><div className="divide-y divide-slate-100">{summary.ncrs.map((ncr) => <div key={ncr.id} className="p-4"><div className="flex items-start gap-3"><ShieldAlert size={17} className="mt-0.5 text-rose-500" /><div className="min-w-0 flex-1"><p className="font-semibold text-slate-800">{ncr.ncr_number} | {ncr.title}</p><p className="text-xs text-slate-500">{ncr.severity} | Task #{ncr.task_id} | {ncr.due_date ? formatDate(ncr.due_date) : 'Tanpa due date'}</p>{ncr.corrective_action && <p className="mt-1 text-xs text-slate-600">CA: {ncr.corrective_action}</p>}</div><span className={statusClass(ncr.status)}>{ncr.status}</span></div>{ncr.status !== 'closed' && (isReviewer || ncr.assigned_to === user?.id) && <div className="mt-3 flex justify-end gap-2"><button type="button" onClick={() => { const action = window.prompt('Corrective action', ncr.corrective_action || '') || ''; if (action) ncrMutation.mutate({ id: ncr.id, payload: { corrective_action: action, status: 'ready_for_close' } }) }} className="btn-secondary text-xs">Corrective action</button>{isReviewer && ncr.corrective_action && <button type="button" onClick={() => ncrMutation.mutate({ id: ncr.id, payload: { status: 'closed' } })} className="btn-secondary text-xs text-emerald-700">Close NCR</button>}</div>}</div>)}</div></div>
        </div>
      </section>}

      {activeTab === 'cost' && summary && <section className="space-y-5">
        <div className="grid gap-4 md:grid-cols-3"><div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Contract value</p><p className="mt-2 text-2xl font-bold text-slate-950">{currency(summary.project.contract_value)}</p></div><div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Control budget</p><p className="mt-2 text-2xl font-bold text-slate-950">{currency(metrics?.budget_cost)}</p></div><div className="border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-400">Actual cost</p><p className="mt-2 text-2xl font-bold text-slate-950">{currency(metrics?.actual_cost)}</p><p className={`mt-1 text-xs font-semibold ${(metrics?.actual_cost || 0) > (metrics?.budget_cost || 0) ? 'text-rose-600' : 'text-emerald-600'}`}>Variance {currency((metrics?.budget_cost || 0) - (metrics?.actual_cost || 0))}</p></div></div>
        <div className="overflow-x-auto border border-slate-200 bg-white"><table className="min-w-[850px] w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Pekerjaan</th><th className="px-4 py-3">Progress volume</th><th className="px-4 py-3">Budget</th><th className="px-4 py-3">Actual</th><th className="px-4 py-3">Variance</th></tr></thead><tbody className="divide-y divide-slate-100">{summary.tasks.map((task) => <tr key={task.id}><td className="px-4 py-3"><p className="font-semibold text-slate-800">{task.title}</p><p className="text-xs text-slate-400">{task.wbs_code || '-'}</p></td><td className="px-4 py-3"><p>{number(task.actual_quantity)} / {number(task.planned_quantity)} {task.unit || ''}</p><div className="mt-1 h-1.5 w-36 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-cyan-500" style={{ width: `${Math.min(100, task.progress_percent)}%` }} /></div></td><td className="px-4 py-3">{currency(task.budget_cost)}</td><td className="px-4 py-3">{currency(task.actual_cost)}</td><td className={`px-4 py-3 font-semibold ${task.actual_cost > task.budget_cost && task.budget_cost > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>{currency(task.budget_cost - task.actual_cost)}</td></tr>)}</tbody></table></div>
      </section>}

      {activeTab === 'closeout' && summary && <section className="space-y-5">
        <div className="flex items-center justify-between"><div><h2 className="text-lg font-bold text-slate-900">Handover Dossier</h2><p className="text-xs text-slate-500">{summary.handover.length} controlled item</p></div>{isReviewer && <button type="button" onClick={() => handoverMutation.mutate()} className="btn-secondary"><RefreshCw size={15} className={handoverMutation.isPending ? 'animate-spin' : ''} /> Refresh dossier</button>}</div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{summary.handover.map((item) => <div key={item.id} className="flex items-start gap-3 border border-slate-200 bg-white p-4"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700"><FileArchive size={17} /></div><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-800">{item.title}</p><p className="mt-0.5 text-xs text-slate-500">{item.category.replaceAll('_', ' ')} | {item.auto_collected ? 'Auto' : 'Manual'}</p><span className={`mt-2 ${statusClass(item.status)}`}>{item.status}</span></div></div>)}</div>
        {!summary.handover.length && <div className="border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">Belum ada dokumen approved yang masuk dossier.</div>}
      </section>}

      {planTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4">
          <form onSubmit={savePlan} className="max-h-[90vh] w-full max-w-3xl overflow-y-auto border border-slate-200 bg-white p-6 shadow-xl">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-cyan-700">Task baseline</p>
                <h2 className="mt-1 text-lg font-bold text-slate-900">{planTask.title}</h2>
                <p className="mt-1 text-xs text-slate-500">Lengkapi data ini agar make-or-buy analysis bisa membandingkan internal vs vendor.</p>
              </div>
              <button type="button" onClick={() => setPlanTask(null)} className="btn-ghost p-2" aria-label="Tutup"><X size={17} /></button>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="label">Planned start<input type="date" value={planForm.planned_start} onChange={(e) => setPlanForm({ ...planForm, planned_start: e.target.value })} className="input mt-1" /></label>
              <label className="label">Planned finish<input type="date" value={planForm.planned_finish} onChange={(e) => setPlanForm({ ...planForm, planned_finish: e.target.value })} className="input mt-1" /></label>
              <label className="label">Lokasi<input value={planForm.location} onChange={(e) => setPlanForm({ ...planForm, location: e.target.value })} className="input mt-1" /></label>
              <label className="label">Satuan BOQ<input value={planForm.unit} onChange={(e) => setPlanForm({ ...planForm, unit: e.target.value })} className="input mt-1" /></label>
              <label className="label">Planned quantity<input type="number" min="0" step="any" value={planForm.planned_quantity} onChange={(e) => setPlanForm({ ...planForm, planned_quantity: e.target.value })} className="input mt-1" /></label>
              <label className="label">Bobot (%)<input type="number" min="0" max="100" step="any" value={planForm.weight_percent} onChange={(e) => setPlanForm({ ...planForm, weight_percent: e.target.value })} className="input mt-1" /></label>
            </div>

            <div className="mt-5 border-t border-slate-100 pt-5">
              <h3 className="text-sm font-bold text-slate-900">Nilai pekerjaan dan biaya internal</h3>
              <div className="mt-3 grid gap-4 md:grid-cols-3">
                <label className="label">Nilai BOQ / kontrak item<input type="number" min="0" step="any" value={planForm.boq_value} onChange={(e) => setPlanForm({ ...planForm, boq_value: e.target.value })} className="input mt-1" /></label>
                <label className="label">Control budget<input type="number" min="0" step="any" value={planForm.budget_cost} onChange={(e) => setPlanForm({ ...planForm, budget_cost: e.target.value })} className="input mt-1" /></label>
                <label className="label">Biaya risiko internal<input type="number" min="0" step="any" value={planForm.internal_risk_cost} onChange={(e) => setPlanForm({ ...planForm, internal_risk_cost: e.target.value })} className="input mt-1" /></label>
                <label className="label">Biaya material internal<input type="number" min="0" step="any" value={planForm.internal_material_cost} onChange={(e) => setPlanForm({ ...planForm, internal_material_cost: e.target.value })} className="input mt-1" /></label>
                <label className="label">Biaya tenaga kerja<input type="number" min="0" step="any" value={planForm.internal_labor_cost} onChange={(e) => setPlanForm({ ...planForm, internal_labor_cost: e.target.value })} className="input mt-1" /></label>
                <label className="label">Biaya alat internal<input type="number" min="0" step="any" value={planForm.internal_equipment_cost} onChange={(e) => setPlanForm({ ...planForm, internal_equipment_cost: e.target.value })} className="input mt-1" /></label>
                <label className="label">Overhead internal<input type="number" min="0" step="any" value={planForm.internal_overhead_cost} onChange={(e) => setPlanForm({ ...planForm, internal_overhead_cost: e.target.value })} className="input mt-1" /></label>
                <label className="label">Planned manpower<input type="number" min="0" value={planForm.planned_manpower} onChange={(e) => setPlanForm({ ...planForm, planned_manpower: e.target.value })} className="input mt-1" /></label>
                <label className="label">Alat utama<input value={planForm.planned_equipment} onChange={(e) => setPlanForm({ ...planForm, planned_equipment: e.target.value })} className="input mt-1" placeholder="Crane, excavator, concrete pump" /></label>
              </div>
            </div>

            <div className="mt-5 border-t border-slate-100 pt-5">
              <h3 className="text-sm font-bold text-slate-900">Dependency</h3>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <label className="label md:col-span-2">Predecessor<select value={planForm.depends_on_task_id} onChange={(e) => setPlanForm({ ...planForm, depends_on_task_id: e.target.value })} className="input mt-1"><option value="">Tidak menambah dependency</option>{currentProjectTasks.filter((task) => task.id !== planTask.id).map((task) => <option key={task.id} value={task.id}>{task.wbs_code ? `${task.wbs_code} - ` : ''}{task.title}</option>)}</select></label>
                <label className="label">Dependency type<select value={planForm.dependency_type} onChange={(e) => setPlanForm({ ...planForm, dependency_type: e.target.value })} className="input mt-1"><option value="finish_to_start">Finish to Start</option><option value="start_to_start">Start to Start</option></select></label>
                <label className="label">Lag (hari)<input type="number" min="0" value={planForm.lag_days} onChange={(e) => setPlanForm({ ...planForm, lag_days: e.target.value })} className="input mt-1" /></label>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={() => setPlanTask(null)} className="btn-secondary">Batal</button>
              <button disabled={planMutation.isPending} className="btn-primary">{planMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Simpan baseline</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
