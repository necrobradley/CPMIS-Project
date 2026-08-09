'use client'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, ClipboardList,
  Clock3, Download, FileText, Flag, Loader2, MapPin, PackageCheck, ShieldAlert,
} from 'lucide-react'
import { projectsApi, tasksApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Project, Task } from '@/types'
import {
  PRIORITY_LABELS, STATUS_LABELS, formatDate, isOverdue,
  priorityBadgeClass, statusBadgeClass,
} from '@/lib/utils'

type FocusFilter = 'all' | 'today' | 'ready' | 'blocked' | 'review' | 'done'

type WorkDataGroup = {
  key: string
  projectName: string
  divisionName: string
  taskCount: number
  wbsCodes: string[]
  requirementCount: number
  materialCount: number
  evidenceCount: number
  sourceDocumentCount: number
  sourceDocumentIds: number[]
  blockedCount: number
  reviewCount: number
  doneCount: number
}

type MutableWorkDataGroup = WorkDataGroup & {
  wbsSet: Set<string>
  sourceDocumentSet: Set<number>
}

type ExcelTableRow = Record<string, string | number | boolean | undefined>

function sameDay(value: string | Date | null | undefined, now = new Date()) {
  if (!value) return false
  const date = new Date(value)
  return date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
}

function sortByFieldPriority(a: Task, b: Task) {
  const priorityRank = { critical: 0, high: 1, medium: 2, low: 3 }
  const dateA = a.deadline ? new Date(a.deadline).getTime() : Number.MAX_SAFE_INTEGER
  const dateB = b.deadline ? new Date(b.deadline).getTime() : Number.MAX_SAFE_INTEGER
  return dateA - dateB || priorityRank[a.priority] - priorityRank[b.priority]
}

function joinTaskRequirements(task: Task) {
  return [...(task.requirements || [])]
    .sort((a, b) => a.sequence - b.sequence)
    .map((requirement) => {
      const mandatory = requirement.is_mandatory ? 'wajib' : 'opsional'
      return `${requirement.code} - ${requirement.title} (${mandatory})`
    })
    .join(' | ')
}

function joinTaskMaterials(task: Task) {
  return [...(task.materials || [])]
    .sort((a, b) => a.sequence - b.sequence)
    .map((material) => [
      material.material_code,
      material.material_name,
      material.technical_specification,
      material.standard_reference,
      material.revision ? `Rev ${material.revision}` : '',
    ].filter(Boolean).join(' - '))
    .join(' | ')
}

function taskSourceDocumentIds(task: Task) {
  const ids = new Set<number>()
  if (task.specification?.source_document_id) ids.add(task.specification.source_document_id)
  for (const material of task.materials || []) {
    if (material.source_document_id) ids.add(material.source_document_id)
  }
  return Array.from(ids).sort((a, b) => a - b)
}

function buildWorkDataGroups(tasks: Task[], projectMap: Map<number, string>) {
  const groups = new Map<string, MutableWorkDataGroup>()

  tasks.forEach((task) => {
    const key = `${task.project_id}-${task.division_id || 'none'}`
    const projectName = projectMap.get(task.project_id) || `Proyek #${task.project_id}`
    const divisionName = task.division?.division_name || 'Divisi belum diisi'
    let group = groups.get(key)

    if (!group) {
      group = {
        key,
        projectName,
        divisionName,
        taskCount: 0,
        wbsCodes: [],
        requirementCount: 0,
        materialCount: 0,
        evidenceCount: 0,
        sourceDocumentCount: 0,
        sourceDocumentIds: [],
        blockedCount: 0,
        reviewCount: 0,
        doneCount: 0,
        wbsSet: new Set<string>(),
        sourceDocumentSet: new Set<number>(),
      }
      groups.set(key, group)
    }

    group.taskCount += 1
    group.requirementCount += task.requirements?.length || 0
    group.materialCount += task.materials?.length || 0
    group.evidenceCount += (task.specification?.required_photo_count || 0) + (task.specification?.required_document_count || 0)
    if (task.specification?.wbs_code) group.wbsSet.add(task.specification.wbs_code)
    taskSourceDocumentIds(task).forEach((id) => group.sourceDocumentSet.add(id))
    if (task.status === 'blocked') group.blockedCount += 1
    if (task.status === 'review') group.reviewCount += 1
    if (task.status === 'done') group.doneCount += 1
  })

  return Array.from(groups.values())
    .map(({ wbsSet, sourceDocumentSet, ...group }) => ({
      ...group,
      wbsCodes: Array.from(wbsSet).sort(),
      sourceDocumentCount: sourceDocumentSet.size,
      sourceDocumentIds: Array.from(sourceDocumentSet).sort((a, b) => a - b),
    }))
    .sort((a, b) => a.projectName.localeCompare(b.projectName) || a.divisionName.localeCompare(b.divisionName))
}

function excelSafeValue(value: unknown) {
  const text = value === null || value === undefined ? '' : String(value).replace(/\r?\n/g, ' ')
  return /^[=+\-@]/.test(text.trim()) ? `'${text}` : text
}

function escapeHtml(value: unknown) {
  return excelSafeValue(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderExcelTable(title: string, rows: ExcelTableRow[]) {
  const safeRows = rows.length > 0 ? rows : [{ Status: 'Tidak ada data' }]
  const headers = Object.keys(safeRows[0])

  return `
    <h2>${escapeHtml(title)}</h2>
    <table>
      <thead>
        <tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${safeRows.map((row) => `
          <tr>${headers.map((header) => `<td>${escapeHtml(row[header])}</td>`).join('')}</tr>
        `).join('')}
      </tbody>
    </table>
  `
}

function buildTaskRows(tasks: Task[], projectMap: Map<number, string>): ExcelTableRow[] {
  return [...tasks].sort(sortByFieldPriority).map((task) => {
    const specification = task.specification
    return {
      Project: projectMap.get(task.project_id) || `Proyek #${task.project_id}`,
      Division: task.division?.division_name || '',
      WBS: specification?.wbs_code || '',
      'Parent Task ID': task.parent_task_id || '',
      'Task ID': task.id,
      Task: task.title,
      'Work Package': specification?.work_package || '',
      Status: STATUS_LABELS[task.status],
      Priority: PRIORITY_LABELS[task.priority],
      Deadline: task.deadline ? formatDate(task.deadline) : '',
      Location: specification?.location || '',
      'Progress Percent': task.progress_percent,
      'Acceptance Criteria': specification?.acceptance_criteria || '',
      'Reporting Instructions': specification?.reporting_instructions || '',
      'Required Photos': specification?.required_photo_count || 0,
      'Required Documents': specification?.required_document_count || 0,
      'Spec Source Document ID': specification?.source_document_id || '',
      Template: specification?.template_name ? `${specification.template_name} ${specification.template_version}` : '',
      'Checklist Requirements': joinTaskRequirements(task),
      'Material Specifications': joinTaskMaterials(task),
      'Material Source Document IDs': taskSourceDocumentIds(task).join(' | '),
      'Material Source Pages': (task.materials || []).map((material) => material.source_page).filter(Boolean).join(' | '),
    }
  })
}

function buildRequirementRows(tasks: Task[], projectMap: Map<number, string>): ExcelTableRow[] {
  return [...tasks].sort(sortByFieldPriority).flatMap((task) => (
    [...(task.requirements || [])]
      .sort((a, b) => a.sequence - b.sequence)
      .map((requirement) => ({
        Project: projectMap.get(task.project_id) || `Proyek #${task.project_id}`,
        Division: task.division?.division_name || '',
        WBS: task.specification?.wbs_code || '',
        'Task ID': task.id,
        Task: task.title,
        Code: requirement.code,
        Requirement: requirement.title,
        Type: requirement.requirement_type,
        Mandatory: requirement.is_mandatory ? 'Ya' : 'Tidak',
        'Validation Rule': requirement.validation_rule,
        Description: requirement.description || '',
      }))
  ))
}

function buildMaterialRows(tasks: Task[], projectMap: Map<number, string>): ExcelTableRow[] {
  return [...tasks].sort(sortByFieldPriority).flatMap((task) => (
    [...(task.materials || [])]
      .sort((a, b) => a.sequence - b.sequence)
      .map((material) => ({
        Project: projectMap.get(task.project_id) || `Proyek #${task.project_id}`,
        Division: task.division?.division_name || '',
        WBS: task.specification?.wbs_code || '',
        'Task ID': task.id,
        Task: task.title,
        Code: material.material_code || '',
        Material: material.material_name,
        Category: material.category || '',
        'Technical Specification': material.technical_specification || '',
        Standard: material.standard_reference || '',
        Grade: material.grade || '',
        Manufacturer: material.approved_manufacturer || '',
        Dimensions: material.dimensions || '',
        Unit: material.unit || '',
        Quantity: material.planned_quantity ?? '',
        'Certificate Required': material.certificate_required ? 'Ya' : 'Tidak',
        'Test Required': material.test_required ? 'Ya' : 'Tidak',
        'Approval Required': material.approval_required ? 'Ya' : 'Tidak',
        'Source Document ID': material.source_document_id || '',
        'Source Page': material.source_page || '',
        Revision: material.revision || '',
      }))
  ))
}

function downloadDivisionPackage(tasks: Task[], projectMap: Map<number, string>, userName?: string) {
  if (typeof document === 'undefined' || tasks.length === 0) return

  const groups = buildWorkDataGroups(tasks, projectMap)
  const summaryRows: ExcelTableRow[] = groups.map((group) => ({
    Project: group.projectName,
    Division: group.divisionName,
    Tasks: group.taskCount,
    WBS: group.wbsCodes.join(' | '),
    Checklist: group.requirementCount,
    Material: group.materialCount,
    Evidence: group.evidenceCount,
    'Source Documents': group.sourceDocumentCount,
    'Source Document IDs': group.sourceDocumentIds.join(' | '),
    Blocker: group.blockedCount,
    Review: group.reviewCount,
    Done: group.doneCount,
  }))

  const exportedAt = new Date()
  const html = `<!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body { font-family: Arial, sans-serif; color: #0f172a; }
          h1 { font-size: 20px; margin: 0 0 4px; }
          h2 { font-size: 15px; margin: 24px 0 8px; color: #0e7490; }
          p { margin: 0 0 16px; color: #475569; }
          table { border-collapse: collapse; margin-bottom: 18px; width: 100%; }
          th { background: #e0f2fe; border: 1px solid #94a3b8; color: #0f172a; font-weight: 700; padding: 6px; text-align: left; }
          td { border: 1px solid #cbd5e1; mso-number-format: "\\@"; padding: 6px; vertical-align: top; }
        </style>
      </head>
      <body>
        <h1>Paket Kerja Divisi</h1>
        <p>Staff: ${escapeHtml(userName || 'Staff')} | Dibuat: ${escapeHtml(exportedAt.toLocaleString('id-ID'))} | Format: Excel</p>
        ${renderExcelTable('Ringkasan Relasi Data', summaryRows)}
        ${renderExcelTable('Detail Task', buildTaskRows(tasks, projectMap))}
        ${renderExcelTable('Checklist Requirement', buildRequirementRows(tasks, projectMap))}
        ${renderExcelTable('Spesifikasi Material', buildMaterialRows(tasks, projectMap))}
      </body>
    </html>
  `

  const blob = new Blob([`\uFEFF${html}`], { type: 'application/vnd.ms-excel;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const owner = (userName || 'staff').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'staff'
  const stamp = new Date().toISOString().slice(0, 10)

  link.href = url
  link.download = `paket-kerja-divisi-${owner}-${stamp}.xls`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export default function DivisionTasksPage() {
  const user = useAuthStore((state) => state.user)
  const [focus, setFocus] = useState<FocusFilter>('all')

  const { data: tasks = [], isLoading } = useQuery<Task[]>({
    queryKey: ['division-tasks', user?.id],
    queryFn: async () => (await tasksApi.list({ scope: 'division' })).data,
    enabled: Boolean(user),
    refetchInterval: 20_000,
  })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  const projectMap = useMemo(
    () => new Map(projects.map((project) => [project.id, project.project_name])),
    [projects],
  )

  const relationMetrics = useMemo(() => {
    const projectIds = new Set<number>()
    const divisionNames = new Set<string>()
    const wbsCodes = new Set<string>()
    const sourceDocumentIds = new Set<number>()
    let requirementCount = 0
    let materialCount = 0
    let evidenceCount = 0

    tasks.forEach((task) => {
      projectIds.add(task.project_id)
      if (task.division?.division_name) divisionNames.add(task.division.division_name)
      if (task.specification?.wbs_code) wbsCodes.add(task.specification.wbs_code)
      taskSourceDocumentIds(task).forEach((id) => sourceDocumentIds.add(id))
      requirementCount += task.requirements?.length || 0
      materialCount += task.materials?.length || 0
      evidenceCount += (task.specification?.required_photo_count || 0) + (task.specification?.required_document_count || 0)
    })

    return {
      projectCount: projectIds.size,
      divisionCount: divisionNames.size,
      wbsCount: wbsCodes.size,
      requirementCount,
      materialCount,
      evidenceCount,
      sourceDocumentCount: sourceDocumentIds.size,
    }
  }, [tasks])

  const workDataGroups = useMemo<WorkDataGroup[]>(
    () => buildWorkDataGroups(tasks, projectMap),
    [projectMap, tasks],
  )

  const activeTasks = tasks.filter((task) => task.status !== 'done')
  const overdueTasks = activeTasks.filter((task) => isOverdue(task.deadline))
  const todayTasks = activeTasks.filter((task) => sameDay(task.deadline) || isOverdue(task.deadline))
  const readyTasks = activeTasks.filter((task) => ['todo', 'in_progress'].includes(task.status) && !isOverdue(task.deadline))
  const blockedTasks = activeTasks.filter((task) => task.status === 'blocked')
  const reviewTasks = activeTasks.filter((task) => task.status === 'review')
  const doneTasks = tasks.filter((task) => task.status === 'done')

  const visibleTasks = useMemo(() => {
    const groups: Record<FocusFilter, Task[]> = {
      all: activeTasks,
      today: todayTasks,
      ready: readyTasks,
      blocked: blockedTasks,
      review: reviewTasks,
      done: doneTasks,
    }
    return [...groups[focus]].sort(sortByFieldPriority)
  }, [activeTasks, blockedTasks, doneTasks, focus, readyTasks, reviewTasks, todayTasks])

  const focusTabs: { key: FocusFilter; label: string; count: number; icon: typeof Clock3 }[] = [
    { key: 'all', label: 'Semua', count: activeTasks.length, icon: ClipboardList },
    { key: 'today', label: 'Hari ini', count: todayTasks.length, icon: Clock3 },
    { key: 'ready', label: 'Siap kerja', count: readyTasks.length, icon: ClipboardList },
    { key: 'blocked', label: 'Blocker', count: blockedTasks.length, icon: ShieldAlert },
    { key: 'review', label: 'Review', count: reviewTasks.length, icon: FileText },
    { key: 'done', label: 'Selesai', count: doneTasks.length, icon: CheckCircle2 },
  ]

  return (
    <div className="space-y-6 animate-in">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Division worklist</p>
          <h1 className="page-title">Tugas Divisi</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            {user?.name ? `${user.name} - ` : ''}pekerjaan aktif berdasarkan penempatan divisi proyek.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => downloadDivisionPackage(tasks, projectMap, user?.name)}
            disabled={isLoading || tasks.length === 0}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Download size={15} />
            Unduh Excel Divisi
          </button>
          <Link href="/reports" className="btn-secondary">
            <FileText size={15} />
            Laporan
          </Link>
          <Link href="/communications" className="btn-secondary">
            <AlertTriangle size={15} />
            Eskalasi
          </Link>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Aktif" value={activeTasks.length} icon={ClipboardList} tone="cyan" />
        <MetricCard label="Terlambat" value={overdueTasks.length} icon={AlertTriangle} tone="rose" />
        <MetricCard label="Butuh review" value={reviewTasks.length} icon={FileText} tone="amber" />
        <MetricCard label="Selesai" value={doneTasks.length} icon={CheckCircle2} tone="emerald" />
      </div>

      <section className="border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Paket data kerja</p>
            <h2 className="mt-1 text-lg font-bold text-slate-950">Relasi tugas, divisi, dan data pendukung</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
              Ringkasan ini memperlihatkan data yang dipakai staff: WBS, checklist requirement, material, evidence, dan status pekerjaan per divisi proyek.
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-2 rounded-lg border border-cyan-100 bg-cyan-50 px-3 py-2 text-xs font-semibold text-cyan-700">
            <Download size={14} />
            Excel sesuai akses divisi
          </span>
        </div>

        <div className="grid gap-3 px-5 py-4 md:grid-cols-3 xl:grid-cols-7">
          <DataMetric label="Proyek" value={relationMetrics.projectCount} />
          <DataMetric label="Divisi" value={relationMetrics.divisionCount} />
          <DataMetric label="WBS" value={relationMetrics.wbsCount} />
          <DataMetric label="Checklist" value={relationMetrics.requirementCount} />
          <DataMetric label="Material" value={relationMetrics.materialCount} />
          <DataMetric label="Evidence" value={relationMetrics.evidenceCount} />
          <DataMetric label="Dokumen" value={relationMetrics.sourceDocumentCount} />
        </div>

        <div className="divide-y divide-slate-100 border-t border-slate-100">
          {workDataGroups.length === 0 ? (
            <div className="px-5 py-6 text-sm text-slate-500">Belum ada task divisi yang dapat dipetakan.</div>
          ) : (
            workDataGroups.map((group) => (
              <div key={group.key} className="grid gap-3 px-5 py-4 lg:grid-cols-[1fr_220px]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge bg-slate-100 text-slate-700">{group.projectName}</span>
                    <span className="badge bg-cyan-50 text-cyan-700">{group.divisionName}</span>
                    {group.wbsCodes.slice(0, 4).map((code) => (
                      <span key={code} className="badge bg-white text-slate-500 ring-1 ring-slate-200">WBS {code}</span>
                    ))}
                    {group.wbsCodes.length > 4 && (
                      <span className="badge bg-white text-slate-400 ring-1 ring-slate-200">+{group.wbsCodes.length - 4} WBS</span>
                    )}
                    {group.sourceDocumentIds.slice(0, 3).map((id) => (
                      <span key={id} className="badge bg-indigo-50 text-indigo-700">Doc #{id}</span>
                    ))}
                    {group.sourceDocumentIds.length > 3 && (
                      <span className="badge bg-white text-slate-400 ring-1 ring-slate-200">+{group.sourceDocumentIds.length - 3} dokumen</span>
                    )}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    {group.taskCount} task memakai {group.requirementCount} checklist, {group.materialCount} spesifikasi material, {group.evidenceCount} evidence wajib, dan {group.sourceDocumentCount} dokumen sumber.
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-lg bg-rose-50 px-2 py-2 text-rose-700">
                    <div className="text-lg font-bold">{group.blockedCount}</div>
                    <div>Blocker</div>
                  </div>
                  <div className="rounded-lg bg-amber-50 px-2 py-2 text-amber-700">
                    <div className="text-lg font-bold">{group.reviewCount}</div>
                    <div>Review</div>
                  </div>
                  <div className="rounded-lg bg-emerald-50 px-2 py-2 text-emerald-700">
                    <div className="text-lg font-bold">{group.doneCount}</div>
                    <div>Selesai</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {focusTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setFocus(tab.key)}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  focus === tab.key
                    ? 'border-cyan-200 bg-cyan-50 text-cyan-700'
                    : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-800'
                }`}
              >
                <tab.icon size={14} />
                {tab.label}
                <span className="rounded-full bg-white px-1.5 py-0.5 text-[10px] text-slate-500">{tab.count}</span>
              </button>
            ))}
          </div>
          <span className="text-xs font-medium text-slate-400">Live refresh 20s</span>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 size={28} className="animate-spin text-brand-500" />
          </div>
        ) : visibleTasks.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <CheckCircle2 size={34} className="mx-auto text-emerald-400" />
            <p className="mt-3 text-sm font-semibold text-slate-700">Tidak ada task pada kategori ini.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {visibleTasks.map((task) => (
              <TaskRow key={task.id} task={task} projectName={projectMap.get(task.project_id)} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function MetricCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string
  value: number
  icon: typeof ClipboardList
  tone: 'cyan' | 'rose' | 'amber' | 'emerald'
}) {
  const toneClass = {
    cyan: 'bg-cyan-50 text-cyan-700',
    rose: 'bg-rose-50 text-rose-700',
    amber: 'bg-amber-50 text-amber-700',
    emerald: 'bg-emerald-50 text-emerald-700',
  }[tone]

  return (
    <div className="border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${toneClass}`}>
          <Icon size={18} />
        </div>
        <div className="text-3xl font-bold text-slate-950">{value}</div>
      </div>
      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  )
}

function DataMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="text-2xl font-bold text-slate-950">{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
    </div>
  )
}

function TaskRow({ task, projectName }: { task: Task; projectName?: string }) {
  const overdue = isOverdue(task.deadline) && task.status !== 'done'
  const requiredEvidence = (task.specification?.required_photo_count || 0) + (task.specification?.required_document_count || 0)
  const materialCount = task.materials?.length || 0

  return (
    <div className="grid gap-4 px-5 py-4 transition hover:bg-slate-50 xl:grid-cols-[1fr_220px]">
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className={statusBadgeClass(task.status) + ' badge'}>{STATUS_LABELS[task.status]}</span>
          <span className={priorityBadgeClass(task.priority) + ' badge'}>{PRIORITY_LABELS[task.priority]}</span>
          {overdue && <span className="badge-danger badge"><AlertTriangle size={11} /> Terlambat</span>}
        </div>
        <Link href={`/tasks/${task.id}`} className="line-clamp-2 text-base font-bold text-slate-900 hover:text-brand-600">
          {task.title}
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="flex items-center gap-1"><MapPin size={12} /> {task.specification?.location || task.division?.division_name || 'Lokasi belum diisi'}</span>
          <span className="flex items-center gap-1"><CalendarDays size={12} /> {task.deadline ? formatDate(task.deadline) : 'Tanpa deadline'}</span>
          <span className="flex items-center gap-1"><Flag size={12} /> {projectName || `Proyek #${task.project_id}`}</span>
        </div>
        {task.specification?.acceptance_criteria && (
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{task.specification.acceptance_criteria}</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600">{task.progress_percent}% progress</span>
          <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600">{requiredEvidence} evidence wajib</span>
          <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600">{materialCount} material</span>
          {task.specification?.wbs_code && <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600">WBS {task.specification.wbs_code}</span>}
          {task.parent_task_id && <span className="rounded-lg bg-slate-100 px-2 py-1 text-slate-600">Turunan task #{task.parent_task_id}</span>}
        </div>
      </div>
      <div className="flex flex-col justify-between gap-3">
        <div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-cyan-500" style={{ width: `${Math.min(task.progress_percent, 100)}%` }} />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
            <span>Progress</span>
            <span>{task.progress_percent}%</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Link href={`/tasks/${task.id}`} className="btn-secondary justify-center text-xs">
            Detail
            <ArrowRight size={13} />
          </Link>
          <Link href="/reports" className="btn-primary justify-center text-xs">
            <PackageCheck size={13} />
            Lapor
          </Link>
        </div>
      </div>
    </div>
  )
}
