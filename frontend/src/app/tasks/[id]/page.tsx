'use client'

import { use, useMemo, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, ArrowLeft, CalendarDays, Camera, CheckCircle2,
  ClipboardCheck, FileCheck2, FileText, FlaskConical, FolderKanban,
  Layers3, Loader2, MapPin, PackageCheck, Pencil, Plus, ShieldCheck,
  Trash2, UserRound,
} from 'lucide-react'
import toast from 'react-hot-toast'

import { projectsApi, tasksApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import {
  formatDate, isOverdue, PRIORITY_LABELS, priorityBadgeClass,
  STATUS_LABELS, statusBadgeClass,
} from '@/lib/utils'
import { Division, Project, ProjectMember, ProjectMemberRoleCatalog, ProjectRolePolicy, Task, TaskMaterialSpecification } from '@/types'

type DetailTab = 'overview' | 'materials' | 'requirements'

const EMPTY_MATERIAL_FORM = {
  material_code: '', material_name: '', category: '', technical_specification: '',
  standard_reference: '', grade: '', approved_manufacturer: '', dimensions: '',
  unit: '', planned_quantity: '', certificate_required: false, test_required: false,
  approval_required: true, source_page: '', revision: '',
}

const STATUS_OPTIONS: Task['status'][] = ['todo', 'in_progress', 'review', 'done', 'blocked']
const FALLBACK_CROSS_DIVISION_PIC_ROLES = new Set(['project_manager'])

function mutationError(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return fallback
}

export default function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const taskId = Number(id)
  const qc = useQueryClient()
  const currentUser = useAuthStore((state) => state.user)
  const canManage = Boolean(currentUser && ['admin', 'director', 'manager'].includes(currentUser.role))
  const [activeTab, setActiveTab] = useState<DetailTab>('overview')
  const [showMaterialForm, setShowMaterialForm] = useState(false)
  const [editingMaterialId, setEditingMaterialId] = useState<number | null>(null)
  const [materialForm, setMaterialForm] = useState({ ...EMPTY_MATERIAL_FORM })

  const { data: task, isLoading, isError } = useQuery<Task>({
    queryKey: ['task', taskId],
    queryFn: async () => (await tasksApi.get(taskId)).data,
    enabled: Number.isFinite(taskId),
  })
  const { data: project } = useQuery<Project>({
    queryKey: ['project', task?.project_id],
    queryFn: async () => (await projectsApi.get(task!.project_id)).data,
    enabled: Boolean(task),
  })
  const { data: divisions = [] } = useQuery<Division[]>({
    queryKey: ['project-divisions', task?.project_id],
    queryFn: async () => (await projectsApi.divisions(task!.project_id)).data,
    enabled: Boolean(task),
  })
  const { data: members = [] } = useQuery<ProjectMember[]>({
    queryKey: ['project-members', task?.project_id],
    queryFn: async () => (await projectsApi.members(task!.project_id)).data,
    enabled: Boolean(task),
  })
  const { data: roleCatalog = [] } = useQuery<ProjectMemberRoleCatalog[]>({
    queryKey: ['project-member-roles'],
    queryFn: async () => (await projectsApi.memberRoles()).data,
  })
  const { data: rolePolicy = [] } = useQuery<ProjectRolePolicy[]>({
    queryKey: ['project-role-policy', task?.project_id],
    queryFn: async () => (await projectsApi.rolePolicy(task!.project_id)).data,
    enabled: Boolean(task),
  })

  const eligibleMembers = useMemo(() => {
    const roleByCode = new Map(roleCatalog.map((role) => [role.code, role]))
    const enabledRoles = new Set(rolePolicy.filter((policy) => policy.enabled).map((policy) => policy.code))
    return members.filter((member) =>
      (!rolePolicy.length || enabledRoles.has(member.project_role)) &&
      (
        (task?.division_id && member.division_id === task.division_id) ||
        Boolean(roleByCode.get(member.project_role)?.can_be_task_pic && !roleByCode.get(member.project_role)?.requires_division) ||
        FALLBACK_CROSS_DIVISION_PIC_ROLES.has(member.project_role)
      )
    )
  }, [members, roleCatalog, rolePolicy, task?.division_id])

  function projectRoleLabel(code: string) {
    return roleCatalog.find((role) => role.code === code)?.label || code.replace(/_/g, ' ')
  }

  const refreshTask = async () => {
    const { data } = await tasksApi.get(taskId)
    qc.setQueryData(['task', taskId], data)
    qc.invalidateQueries({ queryKey: ['tasks'] })
  }

  const updateTask = useMutation({
    mutationFn: (data: Record<string, unknown>) => tasksApi.update(taskId, data),
    onSuccess: async () => {
      await refreshTask()
      toast.success('Penanggung jawab task diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui task'),
  })

  const updateStatus = useMutation({
    mutationFn: (status: Task['status']) => tasksApi.updateStatus(taskId, status),
    onSuccess: async () => {
      await refreshTask()
      toast.success('Status task diperbarui')
    },
    onError: (error) => toast.error(mutationError(error, 'Perubahan status tidak diizinkan')),
  })

  const saveMaterial = useMutation({
    mutationFn: (payload: Record<string, unknown>) => editingMaterialId
      ? tasksApi.updateMaterial(taskId, editingMaterialId, payload)
      : tasksApi.createMaterial(taskId, payload),
    onSuccess: async () => {
      await refreshTask()
      closeMaterialForm()
      toast.success(editingMaterialId ? 'Spesifikasi material diperbarui' : 'Material ditambahkan')
    },
    onError: () => toast.error('Gagal menyimpan spesifikasi material'),
  })

  const deleteMaterial = useMutation({
    mutationFn: (materialId: number) => tasksApi.deleteMaterial(taskId, materialId),
    onSuccess: async () => {
      await refreshTask()
      toast.success('Material dihapus')
    },
    onError: () => toast.error('Gagal menghapus material'),
  })

  function openNewMaterialForm() {
    setEditingMaterialId(null)
    setMaterialForm({ ...EMPTY_MATERIAL_FORM })
    setShowMaterialForm(true)
  }

  function openEditMaterialForm(material: TaskMaterialSpecification) {
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

  function submitMaterial(event: React.FormEvent) {
    event.preventDefault()
    if (!task) return
    const existing = task.materials.find((material) => material.id === editingMaterialId)
    saveMaterial.mutate({
      ...materialForm,
      planned_quantity: materialForm.planned_quantity ? Number(materialForm.planned_quantity) : null,
      sequence: existing?.sequence ?? task.materials.length,
    })
  }

  if (isLoading) {
    return <div className="flex justify-center py-24"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
  }

  if (isError || !task) {
    return (
      <div className="py-20 text-center">
        <AlertTriangle size={28} className="mx-auto text-amber-500" />
        <p className="mt-3 text-sm text-slate-600">Detail task tidak dapat dimuat.</p>
        <Link href="/tasks" className="btn-secondary mt-5 inline-flex"><ArrowLeft size={15} /> Kembali ke Task Board</Link>
      </div>
    )
  }

  const specification = task.specification
  const overdue = isOverdue(task.deadline) && task.status !== 'done'
  const approvalStatus = task.approval_status || 'approved'
  const sourceLabel = specification?.source_document_id
    ? `Dokumen #${specification.source_document_id}`
    : task.ai_source?.toLowerCase().includes('dataset terstruktur')
      ? 'Dataset terstruktur (impor)'
      : task.ai_generated ? 'Hasil ekstraksi AI' : 'Input manual'

  const tabs: { key: DetailTab; label: string; count?: number }[] = [
    { key: 'overview', label: 'Ringkasan' },
    { key: 'materials', label: 'Material', count: task.materials.length },
    { key: 'requirements', label: 'Requirement', count: task.requirements.length },
  ]

  return (
    <div className="space-y-6 animate-in">
      <div>
        <Link href="/tasks" className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-brand-600">
          <ArrowLeft size={15} /> Task Board
        </Link>
        <div className="mt-4 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-semibold text-cyan-700">WBS {specification?.wbs_code || '-'}</span>
              <span className={statusBadgeClass(task.status)}>{STATUS_LABELS[task.status]}</span>
              <span className={priorityBadgeClass(task.priority)}>{PRIORITY_LABELS[task.priority]}</span>
              <span className={
                approvalStatus === 'approved'
                  ? 'badge-success'
                  : approvalStatus === 'rejected'
                    ? 'badge-danger'
                    : 'badge-warning'
              }>{approvalStatus === 'approved' ? 'Approved PM' : approvalStatus === 'rejected' ? 'Rejected PM' : 'Pending approval PM'}</span>
            </div>
            <h1 className="mt-2 text-2xl font-bold text-slate-950 lg:text-3xl">{task.title}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {task.description || specification?.work_package || 'Lingkup pekerjaan belum dideskripsikan.'}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link href={`/projects/${task.project_id}`} className="btn-secondary"><FolderKanban size={15} /> Detail proyek</Link>
            {canManage && approvalStatus !== 'approved' && (
              <Link href="/approvals" className="btn-secondary"><ClipboardCheck size={15} /> Approval Center</Link>
            )}
            <select
              value={task.status}
              onChange={(event) => updateStatus.mutate(event.target.value as Task['status'])}
              disabled={updateStatus.isPending || approvalStatus !== 'approved'}
              className="input w-44 text-sm"
              aria-label="Ubah status task"
            >
              {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 lg:grid-cols-5">
        <SummaryCell icon={FolderKanban} label="Proyek" value={project?.project_name || `Proyek #${task.project_id}`} tone="text-cyan-700 bg-cyan-50" />
        <SummaryCell icon={UserRound} label="PIC" value={task.assignee?.name || 'Belum ditetapkan'} tone="text-violet-700 bg-violet-50" />
        <SummaryCell icon={ClipboardCheck} label="Approval PM" value={approvalStatus} tone={approvalStatus === 'approved' ? 'text-emerald-700 bg-emerald-50' : approvalStatus === 'rejected' ? 'text-rose-700 bg-rose-50' : 'text-amber-700 bg-amber-50'} />
        <SummaryCell icon={CalendarDays} label="Deadline" value={task.deadline ? formatDate(task.deadline) : 'Belum ditetapkan'} tone={overdue ? 'text-rose-700 bg-rose-50' : 'text-amber-700 bg-amber-50'} />
        <SummaryCell icon={CheckCircle2} label="Progress" value={`${task.progress_percent}%`} tone="text-emerald-700 bg-emerald-50" />
      </div>

      <div className="border-b border-slate-200">
        <nav className="flex gap-6 overflow-x-auto" aria-label="Bagian detail task">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`flex h-11 flex-shrink-0 items-center gap-2 border-b-2 text-sm font-semibold transition ${activeTab === tab.key ? 'border-cyan-600 text-cyan-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}
            >
              {tab.label}
              {tab.count != null && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{tab.count}</span>}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'overview' && (
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.6fr)_360px]">
          <div className="space-y-8">
            <section>
              <SectionHeading icon={FileText} title="Spesifikasi pekerjaan" description="Acuan pelaksanaan, pemeriksaan, dan pelaporan." />
              <dl className="mt-4 divide-y divide-slate-100 border-y border-slate-200">
                <SpecRow label="Lingkup pekerjaan" value={task.description || 'Belum ada deskripsi lingkup pekerjaan.'} />
                <div className="grid gap-4 py-4 md:grid-cols-2">
                  <SpecItem label="Work package" value={specification?.work_package || '-'} />
                  <SpecItem label="Lokasi" value={specification?.location || '-'} icon={MapPin} />
                </div>
                <SpecRow label="Kriteria penerimaan" value={specification?.acceptance_criteria || 'Belum ditetapkan.'} icon={ShieldCheck} />
                <SpecRow label="Instruksi pelaporan" value={specification?.reporting_instructions || 'Belum ditetapkan.'} />
                <div className="grid gap-4 py-4 md:grid-cols-2">
                  <SpecItem label="Template laporan" value={`${specification?.template_name || '-'}${specification?.template_version ? ` v${specification.template_version}` : ''}`} />
                  <SpecItem label="Sumber spesifikasi" value={sourceLabel} />
                </div>
              </dl>
            </section>

            <section>
              <SectionHeading icon={Camera} title="Evidence wajib" description="Bukti minimum sebelum laporan dapat diproses." />
              <div className="mt-4 grid grid-cols-2 gap-px overflow-hidden border border-slate-200 bg-slate-200">
                <EvidenceCell icon={Camera} value={specification?.required_photo_count || 0} label="Foto lapangan" />
                <EvidenceCell icon={FileCheck2} value={specification?.required_document_count || 0} label="Dokumen pendukung" />
              </div>
            </section>
          </div>

          <aside className="border-t border-slate-200 pt-6 xl:border-l xl:border-t-0 xl:pl-7 xl:pt-0">
            <SectionHeading icon={UserRound} title="Tanggung jawab" description="Klasifikasi dan pemilik pekerjaan saat ini." />
            <div className="mt-5 space-y-4">
              <div>
                <label className="label">Proyek</label>
                <p className="mt-1 text-sm font-medium text-slate-800">{project?.project_name || `Proyek #${task.project_id}`}</p>
              </div>
              <div>
                <label htmlFor="task-detail-division" className="label">Divisi</label>
                {canManage ? (
                  <select
                    id="task-detail-division"
                    value={task.division_id ?? ''}
                    onChange={(event) => updateTask.mutate({ division_id: event.target.value ? Number(event.target.value) : null, assigned_to: null })}
                    disabled={updateTask.isPending}
                    className="input mt-1"
                  >
                    <option value="">Belum diklasifikasikan</option>
                    {divisions.map((division) => <option key={division.id} value={division.id}>{division.division_name}</option>)}
                  </select>
                ) : <p className="mt-1 text-sm font-medium text-slate-800">{task.division?.division_name || 'Belum diklasifikasikan'}</p>}
              </div>
              <div>
                <label htmlFor="task-detail-pic" className="label">PIC / staff</label>
                {canManage ? (
                  <select
                    id="task-detail-pic"
                    value={task.assigned_to ?? ''}
                    onChange={(event) => updateTask.mutate({ assigned_to: event.target.value ? Number(event.target.value) : null })}
                    disabled={updateTask.isPending || !task.division_id}
                    className="input mt-1"
                  >
                    <option value="">Belum ada PIC</option>
                    {task.assignee && !eligibleMembers.some((member) => member.user_id === task.assigned_to) && (
                      <option value={task.assignee.id}>{task.assignee.name} - penempatan lama</option>
                    )}
                    {eligibleMembers.map((member) => (
                      <option key={member.id} value={member.user_id}>
                        {member.user.name} - {projectRoleLabel(member.project_role)}
                      </option>
                    ))}
                  </select>
                ) : <p className="mt-1 text-sm font-medium text-slate-800">{task.assignee?.name || 'Belum ditetapkan'}</p>}
              </div>
              <div className="border-t border-slate-200 pt-4">
                <p className="label">Kelengkapan definisi</p>
                <div className="mt-3 space-y-2 text-xs">
                  <DefinitionCheck complete={Boolean(specification?.wbs_code)} label="Kode WBS" />
                  <DefinitionCheck complete={Boolean(specification?.acceptance_criteria)} label="Kriteria penerimaan" />
                  <DefinitionCheck complete={task.materials.length > 0} label="Spesifikasi material" />
                  <DefinitionCheck complete={task.requirements.length > 0} label="Requirement checklist" />
                </div>
              </div>
            </div>
          </aside>
        </div>
      )}

      {activeTab === 'materials' && (
        <section>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <SectionHeading icon={PackageCheck} title="Material Specification Register" description="Material, mutu, standar, pengujian, dan sumber revisi." />
            {canManage && <button type="button" onClick={openNewMaterialForm} className="btn-primary"><Plus size={15} /> Tambah material</button>}
          </div>

          {showMaterialForm && canManage && (
            <MaterialForm
              form={materialForm}
              setForm={setMaterialForm}
              editing={Boolean(editingMaterialId)}
              pending={saveMaterial.isPending}
              onSubmit={submitMaterial}
              onCancel={closeMaterialForm}
            />
          )}

          <div className="mt-5 divide-y divide-slate-100 border-y border-slate-200">
            {task.materials.map((material) => (
              <MaterialRow
                key={material.id}
                material={material}
                canManage={canManage}
                onEdit={() => openEditMaterialForm(material)}
                onDelete={() => deleteMaterial.mutate(material.id)}
              />
            ))}
            {task.materials.length === 0 && (
              <div className="py-16 text-center">
                <PackageCheck size={24} className="mx-auto text-slate-300" />
                <p className="mt-3 text-sm text-slate-500">Belum ada spesifikasi material untuk task ini.</p>
              </div>
            )}
          </div>
        </section>
      )}

      {activeTab === 'requirements' && (
        <section>
          <SectionHeading icon={ClipboardCheck} title="Requirement checklist" description="Kondisi wajib yang akan diperiksa pada laporan pekerjaan." />
          <div className="mt-5 divide-y divide-slate-100 border-y border-slate-200">
            {task.requirements.map((requirement, index) => (
              <div key={requirement.id} className="grid gap-3 py-4 md:grid-cols-[40px_1fr_auto] md:items-start">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-50 text-xs font-bold text-cyan-700">{index + 1}</div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{requirement.title}</h3>
                    {requirement.is_mandatory && <span className="text-[11px] font-semibold text-rose-600">Wajib</span>}
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{requirement.description || 'Tidak ada penjelasan tambahan.'}</p>
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  <span className="font-mono text-xs font-semibold text-cyan-700">{requirement.code}</span>
                  <span className="text-xs text-slate-500">{requirement.validation_rule.replaceAll('_', ' ')}</span>
                </div>
              </div>
            ))}
            {task.requirements.length === 0 && <p className="py-16 text-center text-sm text-slate-500">Belum ada requirement.</p>}
          </div>
        </section>
      )}
    </div>
  )
}

function SummaryCell({ icon: Icon, label, value, tone }: { icon: typeof FolderKanban; label: string; value: string; tone: string }) {
  return (
    <div className="flex min-w-0 items-center gap-3 bg-white p-4">
      <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${tone}`}><Icon size={18} /></div>
      <div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{value}</p><p className="mt-0.5 text-xs text-slate-500">{label}</p></div>
    </div>
  )
}

function SectionHeading({ icon: Icon, title, description }: { icon: typeof FileText; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700"><Icon size={17} /></div>
      <div><h2 className="text-sm font-semibold text-slate-950">{title}</h2><p className="mt-0.5 text-xs text-slate-500">{description}</p></div>
    </div>
  )
}

function SpecRow({ label, value, icon: Icon }: { label: string; value: string; icon?: typeof FileText }) {
  return <div className="py-4"><dt className="flex items-center gap-1 text-xs font-semibold text-slate-500">{Icon && <Icon size={12} />}{label}</dt><dd className="mt-1.5 text-sm leading-6 text-slate-800">{value}</dd></div>
}

function SpecItem({ label, value, icon: Icon }: { label: string; value: string; icon?: typeof FileText }) {
  return <div><dt className="flex items-center gap-1 text-xs font-semibold text-slate-500">{Icon && <Icon size={12} />}{label}</dt><dd className="mt-1.5 text-sm text-slate-800">{value}</dd></div>
}

function EvidenceCell({ icon: Icon, value, label }: { icon: typeof Camera; value: number; label: string }) {
  return <div className="flex items-center gap-3 bg-white p-4"><Icon size={18} className="text-slate-400" /><div><p className="text-xl font-bold text-slate-900">{value}</p><p className="text-xs text-slate-500">{label}</p></div></div>
}

function DefinitionCheck({ complete, label }: { complete: boolean; label: string }) {
  return <div className="flex items-center gap-2"><CheckCircle2 size={14} className={complete ? 'text-emerald-500' : 'text-slate-300'} /><span className={complete ? 'text-slate-700' : 'text-slate-400'}>{label}</span></div>
}

function MaterialRow({ material, canManage, onEdit, onDelete }: { material: TaskMaterialSpecification; canManage: boolean; onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="py-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-slate-900">{material.material_name}</h3>{material.material_code && <span className="font-mono text-[11px] font-semibold text-violet-700">{material.material_code}</span>}</div>
          <p className="mt-1.5 max-w-4xl text-sm leading-6 text-slate-700">{material.technical_specification || 'Spesifikasi teknis belum dicatat.'}</p>
        </div>
        {canManage && <div className="flex gap-1"><button type="button" onClick={onEdit} className="btn-ghost p-2" title="Edit material"><Pencil size={14} /></button><button type="button" onClick={onDelete} className="btn-ghost p-2 text-rose-600" title="Hapus material"><Trash2 size={14} /></button></div>}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {material.category && <span className="badge-gray">{material.category}</span>}
        {material.grade && <span className="badge-info">Mutu {material.grade}</span>}
        {material.standard_reference && <span className="badge-gray">{material.standard_reference}</span>}
        {material.dimensions && <span className="badge-gray">{material.dimensions}</span>}
        {material.planned_quantity != null && <span className="badge-gray">{material.planned_quantity.toLocaleString('id-ID')} {material.unit || ''}</span>}
      </div>
      <div className="mt-3 grid gap-2 text-xs text-slate-500 md:grid-cols-2">
        <p>Produsen: <span className="font-medium text-slate-700">{material.approved_manufacturer || 'Sesuai approved submittal'}</span></p>
        <p>Sumber: <span className="font-medium text-slate-700">{material.source_document_id ? `Dokumen #${material.source_document_id}` : 'Input manual'}{material.source_page ? ` · ${material.source_page}` : ''}{material.revision ? ` · ${material.revision}` : ''}</span></p>
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-[11px] font-semibold">
        {material.certificate_required && <span className="text-emerald-700">Sertifikat wajib</span>}
        {material.test_required && <span className="flex items-center gap-1 text-cyan-700"><FlaskConical size={11} /> Pengujian wajib</span>}
        {material.approval_required && <span className="text-violet-700">Approval material wajib</span>}
      </div>
    </div>
  )
}

type MaterialFormState = typeof EMPTY_MATERIAL_FORM

function MaterialForm({ form, setForm, editing, pending, onSubmit, onCancel }: {
  form: MaterialFormState
  setForm: React.Dispatch<React.SetStateAction<MaterialFormState>>
  editing: boolean
  pending: boolean
  onSubmit: (event: React.FormEvent) => void
  onCancel: () => void
}) {
  return (
    <form onSubmit={onSubmit} className="mt-6 space-y-4 border-y border-slate-200 bg-slate-50 p-5">
      <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
        <Field label="Kode material"><input value={form.material_code} onChange={(event) => setForm({ ...form, material_code: event.target.value })} className="input" placeholder="MAT-001" /></Field>
        <Field label="Nama material *"><input required value={form.material_name} onChange={(event) => setForm({ ...form, material_name: event.target.value })} className="input" placeholder="Beton ready mix" /></Field>
      </div>
      <Field label="Spesifikasi teknis *"><textarea required rows={3} value={form.technical_specification} onChange={(event) => setForm({ ...form, technical_specification: event.target.value })} className="input resize-none" placeholder="Komposisi, performa, toleransi, dan finishing" /></Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Kategori"><input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} className="input" placeholder="Beton" /></Field>
        <Field label="Grade / mutu"><input value={form.grade} onChange={(event) => setForm({ ...form, grade: event.target.value })} className="input" placeholder="fc' 30 MPa" /></Field>
        <Field label="Standar"><input value={form.standard_reference} onChange={(event) => setForm({ ...form, standard_reference: event.target.value })} className="input" placeholder="SNI 2847:2019" /></Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Dimensi"><input value={form.dimensions} onChange={(event) => setForm({ ...form, dimensions: event.target.value })} className="input" placeholder="D16 mm" /></Field>
        <Field label="Kuantitas"><input type="number" min="0" step="any" value={form.planned_quantity} onChange={(event) => setForm({ ...form, planned_quantity: event.target.value })} className="input" /></Field>
        <Field label="Satuan"><input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} className="input" placeholder="m3 / kg / unit" /></Field>
      </div>
      <Field label="Produsen / merek disetujui"><input value={form.approved_manufacturer} onChange={(event) => setForm({ ...form, approved_manufacturer: event.target.value })} className="input" placeholder="Sesuai approved material submittal" /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Halaman sumber"><input value={form.source_page} onChange={(event) => setForm({ ...form, source_page: event.target.value })} className="input" placeholder="Bab 4 / halaman 125" /></Field>
        <Field label="Revisi"><input value={form.revision} onChange={(event) => setForm({ ...form, revision: event.target.value })} className="input" placeholder="Rev.02" /></Field>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-200 pt-4">
        {[
          ['certificate_required', 'Sertifikat wajib'],
          ['test_required', 'Pengujian wajib'],
          ['approval_required', 'Approval material wajib'],
        ].map(([field, label]) => (
          <label key={field} className="flex items-center gap-2 text-xs font-medium text-slate-700">
            <input type="checkbox" checked={Boolean(form[field as keyof MaterialFormState])} onChange={(event) => setForm({ ...form, [field]: event.target.checked })} className="h-4 w-4 rounded border-slate-300" />
            {label}
          </label>
        ))}
      </div>
      <div className="flex justify-end gap-2"><button type="button" onClick={onCancel} className="btn-secondary">Batal</button><button disabled={pending} className="btn-primary">{editing ? <Pencil size={14} /> : <Plus size={14} />}{editing ? 'Perbarui material' : 'Simpan material'}</button></div>
    </form>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="label">{label}</span>{children}</label>
}
