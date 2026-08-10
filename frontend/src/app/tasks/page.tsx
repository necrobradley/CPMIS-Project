'use client'
import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi, projectsApi } from '@/lib/api'
import { Division, ProjectMember, ProjectMemberRoleCatalog, ProjectRolePolicy, Task, Project } from '@/types'
import { STATUS_LABELS, PRIORITY_LABELS, statusBadgeClass, priorityBadgeClass, formatDate, isOverdue } from '@/lib/utils'
import {
  Plus, CheckSquare, Loader2, Calendar, AlertTriangle, Bot, X,
  ClipboardCheck, MapPin, ShieldCheck, Layers3, Columns3, ListChecks,
  FileText, FlaskConical, PackageCheck, Pencil, Trash2,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/lib/store'

const COLUMNS: { key: Task['status']; label: string; color: string }[] = [
  { key: 'todo',        label: 'Belum Mulai',       color: 'bg-slate-100' },
  { key: 'in_progress', label: 'Dikerjakan',         color: 'bg-blue-50' },
  { key: 'review',      label: 'Tinjauan',           color: 'bg-amber-50' },
  { key: 'done',        label: 'Selesai',            color: 'bg-emerald-50' },
  { key: 'blocked',     label: 'Terhambat',          color: 'bg-red-50' },
]

const EMPTY_MATERIAL_FORM = {
  material_code: '', material_name: '', category: '', technical_specification: '',
  standard_reference: '', grade: '', approved_manufacturer: '', dimensions: '',
  unit: '', planned_quantity: '', certificate_required: false, test_required: false,
  approval_required: true, source_page: '', revision: '',
}

const FALLBACK_CROSS_DIVISION_PIC_ROLES = new Set(['project_manager'])

function mutationError(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return fallback
}

export default function TasksPage() {
  const router = useRouter()
  const qc = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const canManage = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const [projectId, setProjectId] = useState<number | undefined>()
  const [divisionId, setDivisionId] = useState<number | 'unassigned' | undefined>()
  const [viewMode, setViewMode] = useState<'status' | 'division'>('status')
  const [showForm, setShowForm] = useState(false)
  const [showMaterialForm, setShowMaterialForm] = useState(false)
  const [editingMaterialId, setEditingMaterialId] = useState<number | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [form, setForm] = useState({
    title: '', description: '', priority: 'medium', deadline: '', project_id: '',
    division_id: '', assigned_to: '',
    wbs_code: '', work_package: '', acceptance_criteria: '', required_photo_count: '2',
    required_document_count: '0',
  })
  const [materialForm, setMaterialForm] = useState({ ...EMPTY_MATERIAL_FORM })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  const { data: tasks = [], isLoading } = useQuery<Task[]>({
    queryKey: ['tasks', projectId],
    queryFn: async () => (await tasksApi.list(projectId ? { project_id: projectId } : {})).data,
  })

  const { data: projectDivisions = [] } = useQuery<Division[]>({
    queryKey: ['project-divisions', projectId],
    queryFn: async () => (await projectsApi.divisions(projectId!)).data,
    enabled: Boolean(projectId),
  })

  const { data: formDivisions = [] } = useQuery<Division[]>({
    queryKey: ['project-divisions', Number(form.project_id)],
    queryFn: async () => (await projectsApi.divisions(Number(form.project_id))).data,
    enabled: Boolean(form.project_id),
  })

  const { data: formMembers = [] } = useQuery<ProjectMember[]>({
    queryKey: ['project-members', Number(form.project_id)],
    queryFn: async () => (await projectsApi.members(Number(form.project_id))).data,
    enabled: Boolean(form.project_id),
  })
  const { data: formRolePolicy = [] } = useQuery<ProjectRolePolicy[]>({
    queryKey: ['project-role-policy', Number(form.project_id)],
    queryFn: async () => (await projectsApi.rolePolicy(Number(form.project_id))).data,
    enabled: Boolean(form.project_id),
  })

  const { data: selectedTaskDivisions = [] } = useQuery<Division[]>({
    queryKey: ['project-divisions', selectedTask?.project_id],
    queryFn: async () => (await projectsApi.divisions(selectedTask!.project_id)).data,
    enabled: Boolean(selectedTask),
  })

  const { data: selectedTaskMembers = [] } = useQuery<ProjectMember[]>({
    queryKey: ['project-members', selectedTask?.project_id],
    queryFn: async () => (await projectsApi.members(selectedTask!.project_id)).data,
    enabled: Boolean(selectedTask),
  })
  const { data: selectedTaskRolePolicy = [] } = useQuery<ProjectRolePolicy[]>({
    queryKey: ['project-role-policy', selectedTask?.project_id],
    queryFn: async () => (await projectsApi.rolePolicy(selectedTask!.project_id)).data,
    enabled: Boolean(selectedTask),
  })

  const { data: roleCatalog = [] } = useQuery<ProjectMemberRoleCatalog[]>({
    queryKey: ['project-member-roles'],
    queryFn: async () => (await projectsApi.memberRoles()).data,
  })

  const divisions = useMemo(() => {
    if (projectId) return projectDivisions
    const byId = new Map<number, Division>()
    tasks.forEach((task) => {
      if (task.division) byId.set(task.division.id, task.division)
    })
    return Array.from(byId.values()).sort((a, b) => a.division_name.localeCompare(b.division_name))
  }, [projectDivisions, projectId, tasks])

  const visibleTasks = useMemo(() => {
    if (divisionId === 'unassigned') return tasks.filter((task) => !task.division_id)
    if (typeof divisionId === 'number') return tasks.filter((task) => task.division_id === divisionId)
    return tasks
  }, [divisionId, tasks])

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => tasksApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
    onError: (error) => toast.error(mutationError(error, 'Gagal update status')),
  })

  const createTask = useMutation({
    mutationFn: (data: Record<string, unknown>) => tasksApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      setShowForm(false)
      toast.success('Task diajukan ke Project Manager')
    },
    onError: (error) => toast.error(mutationError(error, 'Gagal membuat task')),
  })

  const updateDivision = useMutation({
    mutationFn: ({ id, nextDivisionId }: { id: number; nextDivisionId: number | null }) =>
      tasksApi.update(id, { division_id: nextDivisionId, assigned_to: null }),
    onSuccess: ({ data }) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      setSelectedTask(data)
      toast.success('Klasifikasi divisi diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui divisi task'),
  })

  const updateAssignee = useMutation({
    mutationFn: ({ id, assignedTo }: { id: number; assignedTo: number | null }) =>
      tasksApi.update(id, { assigned_to: assignedTo }),
    onSuccess: ({ data }) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      setSelectedTask(data)
      toast.success('PIC task diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui PIC task'),
  })

  const createMaterial = useMutation({
    mutationFn: ({ taskId, data }: { taskId: number; data: Record<string, unknown> }) =>
      tasksApi.createMaterial(taskId, data),
    onSuccess: async (_, variables) => {
      const { data } = await tasksApi.get(variables.taskId)
      setSelectedTask(data)
      qc.invalidateQueries({ queryKey: ['tasks'] })
      setShowMaterialForm(false)
      setEditingMaterialId(null)
      setMaterialForm({ ...EMPTY_MATERIAL_FORM })
      toast.success('Spesifikasi material ditambahkan')
    },
    onError: () => toast.error('Gagal menambahkan spesifikasi material'),
  })

  const updateMaterial = useMutation({
    mutationFn: ({ taskId, materialId, data }: { taskId: number; materialId: number; data: Record<string, unknown> }) =>
      tasksApi.updateMaterial(taskId, materialId, data),
    onSuccess: async (_, variables) => {
      const { data } = await tasksApi.get(variables.taskId)
      setSelectedTask(data)
      qc.invalidateQueries({ queryKey: ['tasks'] })
      setShowMaterialForm(false)
      setEditingMaterialId(null)
      setMaterialForm({ ...EMPTY_MATERIAL_FORM })
      toast.success('Spesifikasi material diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui spesifikasi material'),
  })

  const deleteMaterial = useMutation({
    mutationFn: ({ taskId, materialId }: { taskId: number; materialId: number }) =>
      tasksApi.deleteMaterial(taskId, materialId),
    onSuccess: async (_, variables) => {
      const { data } = await tasksApi.get(variables.taskId)
      setSelectedTask(data)
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.success('Spesifikasi material dihapus')
    },
    onError: () => toast.error('Gagal menghapus spesifikasi material'),
  })

  function handleMaterialSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedTask) return
    const data = {
      ...materialForm,
      planned_quantity: materialForm.planned_quantity ? Number(materialForm.planned_quantity) : null,
      sequence: editingMaterialId
        ? selectedTask.materials.find((material) => material.id === editingMaterialId)?.sequence || 0
        : selectedTask.materials?.length || 0,
    }
    if (editingMaterialId) {
      updateMaterial.mutate({ taskId: selectedTask.id, materialId: editingMaterialId, data })
    } else {
      createMaterial.mutate({ taskId: selectedTask.id, data })
    }
  }

  function startEditingMaterial(material: Task['materials'][number]) {
    setEditingMaterialId(material.id)
    setMaterialForm({
      material_code: material.material_code || '',
      material_name: material.material_name,
      category: material.category || '',
      technical_specification: material.technical_specification || '',
      standard_reference: material.standard_reference || '',
      grade: material.grade || '',
      approved_manufacturer: material.approved_manufacturer || '',
      dimensions: material.dimensions || '',
      unit: material.unit || '',
      planned_quantity: material.planned_quantity != null ? String(material.planned_quantity) : '',
      certificate_required: material.certificate_required,
      test_required: material.test_required,
      approval_required: material.approval_required,
      source_page: material.source_page || '',
      revision: material.revision || '',
    })
    setShowMaterialForm(true)
  }

  function closeMaterialForm() {
    setShowMaterialForm(false)
    setEditingMaterialId(null)
    setMaterialForm({ ...EMPTY_MATERIAL_FORM })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.division_id) {
      toast.error('Pilih divisi penanggung jawab task')
      return
    }
    if (!form.assigned_to) {
      toast.error('Pilih staff sebagai PIC task')
      return
    }
    createTask.mutate({
      title: form.title,
      description: form.description,
      priority: form.priority,
      project_id: Number(form.project_id),
      division_id: form.division_id ? Number(form.division_id) : null,
      assigned_to: Number(form.assigned_to),
      deadline: form.deadline || null,
      specification: {
        wbs_code: form.wbs_code,
        work_package: form.work_package || null,
        acceptance_criteria: form.acceptance_criteria,
        required_photo_count: Number(form.required_photo_count),
        required_document_count: Number(form.required_document_count),
        reporting_instructions: 'Laporkan volume, tenaga kerja, kondisi lapangan, kendala, dan tindak lanjut.',
        template_name: 'Laporan Harian Lapangan',
        template_version: '1.0',
      },
      requirements: [
        { code: form.wbs_code + '-AREA', title: 'Area dan item pekerjaan telah diidentifikasi', description: 'Lokasi sesuai task dan drawing.', sequence: 1 },
        { code: form.wbs_code + '-QUALITY', title: 'Pemeriksaan mutu telah dilakukan', description: 'Hasil memenuhi acceptance criteria task.', sequence: 2 },
        { code: form.wbs_code + '-SAFETY', title: 'Kondisi keselamatan telah diperiksa', description: 'APD, akses, dan housekeeping terkendali.', sequence: 3 },
      ],
    })
  }

  function tasksByStatus(status: string) {
    return visibleTasks.filter((t) => t.status === status)
  }

  function projectName(project_id: number) {
    return projects.find((project) => project.id === project_id)?.project_name || 'Proyek'
  }

  function eligibleMembers(
    members: ProjectMember[],
    selectedDivisionId: string | number | undefined,
    policies: ProjectRolePolicy[] = [],
  ) {
    const numericDivisionId = Number(selectedDivisionId)
    const roleByCode = new Map(roleCatalog.map((role) => [role.code, role]))
    const enabledRoles = new Set(policies.filter((policy) => policy.enabled).map((policy) => policy.code))
    return members.filter((member) =>
      (!policies.length || enabledRoles.has(member.project_role)) &&
      (
        member.division_id === numericDivisionId ||
        Boolean(roleByCode.get(member.project_role)?.can_be_task_pic && !roleByCode.get(member.project_role)?.requires_division) ||
        FALLBACK_CROSS_DIVISION_PIC_ROLES.has(member.project_role)
      )
    )
  }

  function projectRoleLabel(code: string) {
    return roleCatalog.find((role) => role.code === code)?.label || code.replace(/_/g, ' ')
  }

  const boardGroups: { key: string; label: string; color: string; tasks: Task[]; meta?: string }[] =
    viewMode === 'status'
      ? COLUMNS.map((column) => ({
          key: column.key,
          label: column.label,
          color: column.color,
          tasks: tasksByStatus(column.key),
        }))
      : [
          ...divisions
            .filter((division) => typeof divisionId !== 'number' || division.id === divisionId)
            .map((division, index) => ({
              key: `division-${division.id}`,
              label: division.division_name,
              meta: projectId ? undefined : projectName(division.project_id),
              color: ['bg-cyan-50', 'bg-emerald-50', 'bg-amber-50', 'bg-violet-50', 'bg-sky-50'][index % 5],
              tasks: visibleTasks.filter((task) => task.division_id === division.id),
            })),
          ...((divisionId === undefined || divisionId === 'unassigned')
            ? [{
                key: 'division-unassigned',
                label: 'Belum diklasifikasikan',
                color: 'bg-slate-100',
                tasks: visibleTasks.filter((task) => !task.division_id),
              }]
            : []),
        ]

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Kanban Board</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {visibleTasks.length} task ditampilkan{visibleTasks.length !== tasks.length ? ` dari ${tasks.length}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <div className="flex rounded-lg border border-slate-200 bg-white p-1" aria-label="Kelompokkan task">
            <button
              type="button"
              onClick={() => setViewMode('status')}
              className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold transition ${viewMode === 'status' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'}`}
            >
              <ListChecks size={14} /> Status
            </button>
            <button
              type="button"
              onClick={() => setViewMode('division')}
              className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold transition ${viewMode === 'division' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'}`}
            >
              <Columns3 size={14} /> Divisi
            </button>
          </div>
          <select
            value={projectId ?? ''}
            onChange={(e) => {
              setProjectId(e.target.value ? Number(e.target.value) : undefined)
              setDivisionId(undefined)
            }}
            className="input w-48 text-sm"
            aria-label="Filter proyek"
          >
            <option value="">Semua Proyek</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.project_name}</option>)}
          </select>
          <select
            value={divisionId ?? ''}
            onChange={(e) => {
              const value = e.target.value
              setDivisionId(value === 'unassigned' ? 'unassigned' : value ? Number(value) : undefined)
            }}
            className="input w-48 text-sm"
            aria-label="Filter divisi"
          >
            <option value="">Semua Divisi</option>
            {divisions.map((division) => (
              <option key={division.id} value={division.id}>
                {division.division_name}{projectId ? '' : ` - ${projectName(division.project_id)}`}
              </option>
            ))}
            <option value="unassigned">Belum diklasifikasikan</option>
          </select>
          {canManage && (
            <button
              onClick={() => {
                setForm((current) => ({
                  ...current,
                  project_id: projectId ? String(projectId) : current.project_id,
                  division_id: projectId ? '' : current.division_id,
                  assigned_to: projectId ? '' : current.assigned_to,
                }))
                setShowForm(true)
              }}
              className="btn-primary"
            >
              <Plus size={16} /> Ajukan Task
            </button>
          )}
        </div>
      </div>

      {/* Create modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto animate-in">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Ajukan Task Baru</h2>
              <button onClick={() => setShowForm(false)} className="btn-ghost p-1.5" aria-label="Tutup form task"><X size={16} /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div>
                <label htmlFor="task-project" className="label">Proyek *</label>
                <select
                  id="task-project"
                  required
                  value={form.project_id}
                  onChange={(e) => setForm({ ...form, project_id: e.target.value, division_id: '', assigned_to: '' })}
                  className="input"
                >
                  <option value="">Pilih proyek...</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.project_name}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="task-division" className="label">Divisi *</label>
                <select
                  id="task-division"
                  required
                  value={form.division_id}
                  onChange={(e) => setForm({ ...form, division_id: e.target.value, assigned_to: '' })}
                  className="input"
                  disabled={!form.project_id || formDivisions.length === 0}
                >
                  <option value="">
                    {!form.project_id ? 'Pilih proyek terlebih dahulu' : formDivisions.length ? 'Pilih divisi...' : 'Proyek belum memiliki divisi'}
                  </option>
                  {formDivisions.map((division) => (
                    <option key={division.id} value={division.id}>{division.division_name}</option>
                  ))}
                </select>
                {form.project_id && formDivisions.length === 0 && (
                  <p className="mt-1.5 text-xs text-amber-700">Tambahkan divisi pada struktur proyek sebelum membuat task.</p>
                )}
              </div>
              <div>
                <label htmlFor="task-assignee" className="label">PIC / Staff Penanggung Jawab *</label>
                <select
                  id="task-assignee"
                  required
                  value={form.assigned_to}
                  onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
                  className="input"
                  disabled={!form.division_id}
                >
                  <option value="">{form.division_id ? 'Pilih PIC...' : 'Pilih divisi terlebih dahulu'}</option>
                  {eligibleMembers(formMembers, form.division_id, formRolePolicy).map((member) => (
                    <option key={member.id} value={member.user_id}>
                      {member.user.name} - {projectRoleLabel(member.project_role)}{member.division?.division_name ? ` / ${member.division.division_name}` : ''}
                    </option>
                  ))}
                </select>
                {form.division_id && eligibleMembers(formMembers, form.division_id, formRolePolicy).length === 0 && (
                  <p className="mt-1.5 text-xs text-amber-700">Belum ada staff pada divisi ini. Atur tim dari detail proyek.</p>
                )}
              </div>
              <div>
                <label className="label">Judul Task *</label>
                <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="input" placeholder="Pekerjaan pondasi pile cap..." />
              </div>
              <div>
                <label className="label">Deskripsi</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input resize-none" placeholder="Detail pekerjaan..." />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Kode WBS *</label>
                  <input required value={form.wbs_code} onChange={(e) => setForm({ ...form, wbs_code: e.target.value })}
                    className="input" placeholder="1.02.03" />
                </div>
                <div>
                  <label className="label">Work Package</label>
                  <input value={form.work_package} onChange={(e) => setForm({ ...form, work_package: e.target.value })}
                    className="input" placeholder="Struktur basement" />
                </div>
              </div>
              <div>
                <label className="label">Acceptance Criteria *</label>
                <textarea required rows={3} value={form.acceptance_criteria} onChange={(e) => setForm({ ...form, acceptance_criteria: e.target.value })}
                  className="input resize-none" placeholder="Kriteria objektif agar pekerjaan dapat diterima..." />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Foto Wajib</label>
                  <input type="number" min="0" value={form.required_photo_count} onChange={(e) => setForm({ ...form, required_photo_count: e.target.value })} className="input" />
                </div>
                <div>
                  <label className="label">Dokumen Wajib</label>
                  <input type="number" min="0" value={form.required_document_count} onChange={(e) => setForm({ ...form, required_document_count: e.target.value })} className="input" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Prioritas</label>
                  <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="input">
                    <option value="low">Rendah</option>
                    <option value="medium">Sedang</option>
                    <option value="high">Tinggi</option>
                    <option value="critical">Kritis</option>
                  </select>
                </div>
                <div>
                  <label className="label">Deadline</label>
                  <input type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} className="input" />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="btn-secondary flex-1 justify-center">Batal</button>
                <button type="submit" disabled={createTask.isPending || !form.division_id || !form.assigned_to} className="btn-primary flex-1 justify-center">
                  {createTask.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  Buat Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Kanban board */}
      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {boardGroups.map((col) => {
            const colTasks = col.tasks
            return (
              <div key={col.key} className={`flex-shrink-0 w-72 rounded-lg ${col.color} p-4`}>
                {/* Column header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-slate-700">{col.label}</span>
                      {col.meta && <span className="block truncate text-[11px] text-slate-500">{col.meta}</span>}
                    </div>
                    <span className="w-5 h-5 rounded-full bg-white text-slate-600 text-xs font-bold flex items-center justify-center shadow-sm">
                      {colTasks.length}
                    </span>
                  </div>
                </div>

                {/* Task cards */}
                <div className="space-y-3">
                  {colTasks.map((task) => (
                    <div
                      key={task.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => router.push(`/tasks/${task.id}`)}
                      onKeyDown={(event) => { if (event.key === 'Enter') router.push(`/tasks/${task.id}`) }}
                      className="cursor-pointer rounded-lg bg-white p-4 shadow-card transition-shadow hover:shadow-card-hover"
                    >
                      {/* AI badge */}
                      {task.ai_generated && (
                        <div className="flex items-center gap-1 mb-2">
                          <Bot size={11} className="text-violet-500" />
                          <span className="text-xs text-violet-500 font-medium">AI Generated</span>
                        </div>
                      )}

                      <h4 className="text-sm font-semibold text-slate-800 mb-2 leading-snug">{task.title}</h4>

                      {task.description && (
                        <p className="text-xs text-slate-400 line-clamp-2 mb-3">{task.description}</p>
                      )}

                      <div className="flex items-center gap-1.5 mb-3 flex-wrap">
                        <span className={priorityBadgeClass(task.priority)}>{PRIORITY_LABELS[task.priority]}</span>
                        {(task.approval_status || 'approved') !== 'approved' && (
                          <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ${
                            task.approval_status === 'rejected' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'
                          }`}>
                            {task.approval_status === 'rejected' ? 'Rejected PM' : 'Pending PM'}
                          </span>
                        )}
                        {viewMode === 'division' && (
                          <span className={statusBadgeClass(task.status)}>{STATUS_LABELS[task.status]}</span>
                        )}
                        {viewMode === 'status' && (
                          <span className="inline-flex items-center gap-1 rounded-md bg-cyan-50 px-2 py-1 text-xs font-medium text-cyan-800">
                            <Layers3 size={11} /> {task.division?.division_name || 'Tanpa divisi'}
                          </span>
                        )}
                        {task.assignee && (
                          <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                            PIC: {task.assignee.name}
                          </span>
                        )}
                      </div>

                      {task.deadline && (
                        <div className={`flex items-center gap-1.5 text-xs mb-3 ${isOverdue(task.deadline) && task.status !== 'done' ? 'text-red-500' : 'text-slate-400'}`}>
                          {isOverdue(task.deadline) && task.status !== 'done'
                            ? <AlertTriangle size={11} />
                            : <Calendar size={11} />
                          }
                          {formatDate(task.deadline)}
                        </div>
                      )}

                      {/* Progress bar */}
                      {task.progress_percent > 0 && (
                        <div className="mb-3">
                          <div className="h-1 bg-slate-100 rounded-full">
                            <div className="h-full bg-brand-500 rounded-full" style={{ width: `${task.progress_percent}%` }} />
                          </div>
                        </div>
                      )}

                      {/* Status change buttons */}
                      <div className="flex gap-1.5 flex-wrap">
                        <button
                          type="button"
                          onClick={(event) => { event.stopPropagation(); router.push(`/tasks/${task.id}`) }}
                          className="inline-flex items-center gap-1 rounded-md bg-cyan-50 px-2 py-1 text-xs font-semibold text-cyan-800 transition hover:bg-cyan-100"
                        >
                          <FileText size={11} /> Spesifikasi
                        </button>
                        {COLUMNS.filter((c) => c.key !== task.status).slice(0, 2).map((c) => (
                          <button key={c.key}
                            onClick={(event) => { event.stopPropagation(); updateStatus.mutate({ id: task.id, status: c.key }) }}
                            disabled={(task.approval_status || 'approved') !== 'approved'}
                            className="text-xs px-2 py-1 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 transition disabled:cursor-not-allowed disabled:opacity-50">
                            → {c.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}

                  {colTasks.length === 0 && (
                    <div className="text-center py-8">
                      <CheckSquare size={20} className="text-slate-300 mx-auto mb-2" />
                      <p className="text-xs text-slate-400">Tidak ada task</p>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {selectedTask && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/35" onClick={() => setSelectedTask(null)}>
          <aside
            className="h-full w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
              <div>
                <p className="text-xs font-semibold text-cyan-700">
                  WBS {selectedTask.specification?.wbs_code || '-'}
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-950">{selectedTask.title}</h2>
                <p className="mt-1 text-xs text-slate-500">{selectedTask.specification?.work_package || 'Work package belum ditetapkan'}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <span className={`inline-flex rounded-md px-2 py-1 text-[11px] font-semibold ${selectedTask.specification ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                    {selectedTask.specification ? 'Spesifikasi tersedia' : 'Spesifikasi belum lengkap'}
                  </span>
                  <span className={`inline-flex rounded-md px-2 py-1 text-[11px] font-semibold ${
                    (selectedTask.approval_status || 'approved') === 'approved'
                      ? 'bg-emerald-50 text-emerald-700'
                      : selectedTask.approval_status === 'rejected'
                        ? 'bg-rose-50 text-rose-700'
                        : 'bg-amber-50 text-amber-700'
                  }`}>
                    {(selectedTask.approval_status || 'approved') === 'approved'
                      ? 'Approved PM'
                      : selectedTask.approval_status === 'rejected'
                        ? 'Rejected PM'
                        : 'Pending approval PM'}
                  </span>
                </div>
                {canManage && (selectedTask.approval_status || 'approved') !== 'approved' && (
                  <button type="button" onClick={() => router.push('/approvals')} className="mt-3 btn-secondary px-3 py-2 text-xs">
                    <ClipboardCheck size={14} /> Buka Approval Center
                  </button>
                )}
              </div>
              <button onClick={() => setSelectedTask(null)} className="btn-ghost p-2" title="Tutup"><X size={17} /></button>
            </div>

            <div className="space-y-5 py-5">
              <section>
                <p className="label flex items-center gap-2"><Layers3 size={14} /> Klasifikasi divisi</p>
                {canManage ? (
                  <>
                    <select
                      value={selectedTask.division_id ?? ''}
                      onChange={(event) => updateDivision.mutate({
                        id: selectedTask.id,
                        nextDivisionId: event.target.value ? Number(event.target.value) : null,
                      })}
                      disabled={updateDivision.isPending}
                      className="input mt-2"
                    >
                      <option value="">Belum diklasifikasikan</option>
                      {selectedTaskDivisions.map((division) => (
                        <option key={division.id} value={division.id}>{division.division_name}</option>
                      ))}
                    </select>
                    <label htmlFor="task-detail-assignee" className="label mt-4">PIC / Staff penanggung jawab</label>
                    <select
                      id="task-detail-assignee"
                      value={selectedTask.assigned_to ?? ''}
                      onChange={(event) => updateAssignee.mutate({
                        id: selectedTask.id,
                        assignedTo: event.target.value ? Number(event.target.value) : null,
                      })}
                      disabled={updateAssignee.isPending || !selectedTask.division_id}
                      className="input mt-2"
                    >
                      <option value="">Belum ada PIC</option>
                      {eligibleMembers(selectedTaskMembers, selectedTask.division_id, selectedTaskRolePolicy).map((member) => (
                        <option key={member.id} value={member.user_id}>
                          {member.user.name} - {projectRoleLabel(member.project_role)}
                        </option>
                      ))}
                    </select>
                  </>
                ) : (
                  <div className="mt-2 space-y-1 text-sm font-medium text-slate-800">
                    <p>{selectedTask.division?.division_name || 'Belum diklasifikasikan'}</p>
                    <p className="text-xs font-normal text-slate-500">PIC: {selectedTask.assignee?.name || 'Belum ditetapkan'}</p>
                  </div>
                )}
                <p className="mt-1.5 text-xs text-slate-500">{projectName(selectedTask.project_id)}</p>
              </section>
              <section className="border-t border-slate-200 pt-5">
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700"><FileText size={17} /></div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-950">Spesifikasi pekerjaan</h3>
                    <p className="mt-0.5 text-xs text-slate-500">Acuan pelaksanaan, pemeriksaan, dan pelaporan task.</p>
                  </div>
                </div>
                <dl className="mt-4 divide-y divide-slate-100 border-y border-slate-200">
                  <div className="py-3">
                    <dt className="text-xs font-semibold text-slate-500">Lingkup pekerjaan</dt>
                    <dd className="mt-1 text-sm leading-relaxed text-slate-800">{selectedTask.description || 'Belum ada deskripsi lingkup pekerjaan.'}</dd>
                  </div>
                  <div className="grid gap-3 py-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs font-semibold text-slate-500">Work package</dt>
                      <dd className="mt-1 text-sm text-slate-800">{selectedTask.specification?.work_package || '-'}</dd>
                    </div>
                    <div>
                      <dt className="flex items-center gap-1 text-xs font-semibold text-slate-500"><MapPin size={12} /> Lokasi</dt>
                      <dd className="mt-1 text-sm text-slate-800">{selectedTask.specification?.location || '-'}</dd>
                    </div>
                  </div>
                  <div className="py-3">
                    <dt className="flex items-center gap-1 text-xs font-semibold text-slate-500"><ShieldCheck size={12} /> Kriteria penerimaan</dt>
                    <dd className="mt-1 text-sm leading-relaxed text-slate-800">{selectedTask.specification?.acceptance_criteria || 'Belum ditetapkan.'}</dd>
                  </div>
                  <div className="py-3">
                    <dt className="text-xs font-semibold text-slate-500">Instruksi pelaporan</dt>
                    <dd className="mt-1 text-sm leading-relaxed text-slate-800">{selectedTask.specification?.reporting_instructions || 'Belum ada instruksi pelaporan.'}</dd>
                  </div>
                  <div className="grid gap-3 py-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs font-semibold text-slate-500">Template laporan</dt>
                      <dd className="mt-1 text-sm text-slate-800">
                        {selectedTask.specification?.template_name || '-'}
                        {selectedTask.specification?.template_version ? ` v${selectedTask.specification.template_version}` : ''}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs font-semibold text-slate-500">Sumber spesifikasi</dt>
                      <dd className="mt-1 text-sm text-slate-800">
                        {selectedTask.specification?.source_document_id
                          ? `Dokumen #${selectedTask.specification.source_document_id}`
                          : selectedTask.ai_generated ? 'Hasil ekstraksi AI' : 'Input manual'}
                      </dd>
                    </div>
                  </div>
                </dl>
              </section>
              <section className="border-t border-slate-200 pt-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-violet-50 text-violet-700"><PackageCheck size={17} /></div>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-950">Material Specification Register</h3>
                      <p className="mt-0.5 text-xs text-slate-500">Material, mutu, standar, pengujian, dan referensi dokumen.</p>
                    </div>
                  </div>
                  {canManage && (
                    <button type="button" onClick={() => showMaterialForm ? closeMaterialForm() : setShowMaterialForm(true)} className="btn-secondary px-3 py-2 text-xs">
                      <Plus size={14} /> Material
                    </button>
                  )}
                </div>

                {showMaterialForm && canManage && (
                  <form onSubmit={handleMaterialSubmit} className="mt-4 space-y-3 border-y border-slate-200 bg-slate-50 p-4">
                    <div className="grid gap-3 sm:grid-cols-[140px_1fr]">
                      <div>
                        <label htmlFor="material-code" className="label">Kode material</label>
                        <input id="material-code" value={materialForm.material_code} onChange={(event) => setMaterialForm({ ...materialForm, material_code: event.target.value })} className="input" placeholder="MAT-001" />
                      </div>
                      <div>
                        <label htmlFor="material-name" className="label">Nama material *</label>
                        <input id="material-name" required value={materialForm.material_name} onChange={(event) => setMaterialForm({ ...materialForm, material_name: event.target.value })} className="input" placeholder="Beton ready mix" />
                      </div>
                    </div>
                    <div>
                      <label htmlFor="material-specification" className="label">Spesifikasi teknis *</label>
                      <textarea id="material-specification" required rows={3} value={materialForm.technical_specification} onChange={(event) => setMaterialForm({ ...materialForm, technical_specification: event.target.value })} className="input resize-none" placeholder="Komposisi, performa, toleransi, finishing, dan ketentuan teknis" />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div><label className="label">Kategori</label><input value={materialForm.category} onChange={(event) => setMaterialForm({ ...materialForm, category: event.target.value })} className="input" placeholder="Beton" /></div>
                      <div><label className="label">Grade / mutu</label><input value={materialForm.grade} onChange={(event) => setMaterialForm({ ...materialForm, grade: event.target.value })} className="input" placeholder="fc' 30 MPa" /></div>
                      <div><label className="label">Standar</label><input value={materialForm.standard_reference} onChange={(event) => setMaterialForm({ ...materialForm, standard_reference: event.target.value })} className="input" placeholder="SNI 2847:2019" /></div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div><label className="label">Dimensi</label><input value={materialForm.dimensions} onChange={(event) => setMaterialForm({ ...materialForm, dimensions: event.target.value })} className="input" placeholder="D16 mm" /></div>
                      <div><label className="label">Kuantitas rencana</label><input type="number" min="0" step="any" value={materialForm.planned_quantity} onChange={(event) => setMaterialForm({ ...materialForm, planned_quantity: event.target.value })} className="input" placeholder="0" /></div>
                      <div><label className="label">Satuan</label><input value={materialForm.unit} onChange={(event) => setMaterialForm({ ...materialForm, unit: event.target.value })} className="input" placeholder="m3 / kg / unit" /></div>
                    </div>
                    <div><label className="label">Produsen / merek disetujui</label><input value={materialForm.approved_manufacturer} onChange={(event) => setMaterialForm({ ...materialForm, approved_manufacturer: event.target.value })} className="input" placeholder="Sesuai approved material submittal" /></div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div><label className="label">Halaman sumber</label><input value={materialForm.source_page} onChange={(event) => setMaterialForm({ ...materialForm, source_page: event.target.value })} className="input" placeholder="Bab 4 / halaman 125" /></div>
                      <div><label className="label">Revisi</label><input value={materialForm.revision} onChange={(event) => setMaterialForm({ ...materialForm, revision: event.target.value })} className="input" placeholder="Rev.02" /></div>
                    </div>
                    <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-200 pt-3">
                      {[
                        ['certificate_required', 'Sertifikat wajib'],
                        ['test_required', 'Pengujian wajib'],
                        ['approval_required', 'Approval material wajib'],
                      ].map(([field, label]) => (
                        <label key={field} className="flex items-center gap-2 text-xs font-medium text-slate-700">
                          <input type="checkbox" checked={Boolean(materialForm[field as keyof typeof materialForm])} onChange={(event) => setMaterialForm({ ...materialForm, [field]: event.target.checked })} className="h-4 w-4 rounded border-slate-300" />
                          {label}
                        </label>
                      ))}
                    </div>
                    <div className="flex justify-end gap-2">
                      <button type="button" onClick={closeMaterialForm} className="btn-secondary">Batal</button>
                      <button disabled={createMaterial.isPending || updateMaterial.isPending} className="btn-primary">
                        {editingMaterialId ? <Pencil size={14} /> : <Plus size={14} />}
                        {editingMaterialId ? 'Perbarui material' : 'Simpan material'}
                      </button>
                    </div>
                  </form>
                )}

                <div className="mt-4 divide-y divide-slate-100 border-y border-slate-200">
                  {(selectedTask.materials || []).map((material) => (
                    <div key={material.id} className="py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h4 className="text-sm font-semibold text-slate-900">{material.material_name}</h4>
                            {material.material_code && <span className="font-mono text-[11px] font-semibold text-violet-700">{material.material_code}</span>}
                          </div>
                          <p className="mt-1 text-sm leading-relaxed text-slate-700">{material.technical_specification || 'Spesifikasi teknis belum dicatat.'}</p>
                        </div>
                        {canManage && (
                          <div className="flex gap-1">
                            <button type="button" onClick={() => startEditingMaterial(material)} className="btn-ghost p-2 text-slate-600" title="Edit material"><Pencil size={14} /></button>
                            <button type="button" onClick={() => deleteMaterial.mutate({ taskId: selectedTask.id, materialId: material.id })} className="btn-ghost p-2 text-rose-600" title="Hapus material"><Trash2 size={14} /></button>
                          </div>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {material.category && <span className="badge-gray">{material.category}</span>}
                        {material.grade && <span className="badge-info">Mutu {material.grade}</span>}
                        {material.standard_reference && <span className="badge-gray">{material.standard_reference}</span>}
                        {material.dimensions && <span className="badge-gray">{material.dimensions}</span>}
                        {material.planned_quantity != null && <span className="badge-gray">{material.planned_quantity.toLocaleString('id-ID')} {material.unit || ''}</span>}
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                        <p>Produsen: <span className="font-medium text-slate-700">{material.approved_manufacturer || 'Sesuai approved submittal'}</span></p>
                        <p>Sumber: <span className="font-medium text-slate-700">{material.source_document_id ? `Dokumen #${material.source_document_id}` : 'Input manual'}{material.source_page ? ` · ${material.source_page}` : ''}{material.revision ? ` · ${material.revision}` : ''}</span></p>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-3 text-[11px] font-semibold">
                        {material.certificate_required && <span className="text-emerald-700">Sertifikat wajib</span>}
                        {material.test_required && <span className="flex items-center gap-1 text-cyan-700"><FlaskConical size={11} /> Pengujian wajib</span>}
                        {material.approval_required && <span className="text-violet-700">Approval material wajib</span>}
                      </div>
                    </div>
                  ))}
                  {(selectedTask.materials || []).length === 0 && (
                    <p className="py-6 text-center text-sm text-slate-500">Belum ada spesifikasi material untuk task ini.</p>
                  )}
                </div>
              </section>
              <section>
                <p className="label">Evidence wajib</p>
                <div className="mt-2 grid grid-cols-2 gap-3">
                  <div className="border border-slate-200 p-3">
                    <p className="text-2xl font-bold text-slate-900">{selectedTask.specification?.required_photo_count || 0}</p>
                    <p className="text-xs text-slate-500">Foto lapangan</p>
                  </div>
                  <div className="border border-slate-200 p-3">
                    <p className="text-2xl font-bold text-slate-900">{selectedTask.specification?.required_document_count || 0}</p>
                    <p className="text-xs text-slate-500">Dokumen pendukung</p>
                  </div>
                </div>
              </section>
              <section>
                <p className="label flex items-center gap-2"><ClipboardCheck size={14} /> Requirement checklist</p>
                <div className="mt-2 divide-y divide-slate-100 border border-slate-200">
                  {selectedTask.requirements.map((requirement) => (
                    <div key={requirement.id} className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium text-slate-800">{requirement.title}</p>
                        <span className="text-xs font-semibold text-cyan-700">{requirement.code}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{requirement.description}</p>
                    </div>
                  ))}
                  {selectedTask.requirements.length === 0 && (
                    <p className="p-3 text-xs text-slate-500">Belum ada requirement.</p>
                  )}
                </div>
              </section>
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}
