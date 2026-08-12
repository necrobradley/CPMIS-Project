'use client'

import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, Calendar, Check, CheckCircle2, ChevronDown, ChevronUp,
  ClipboardCheck, CloudSun, Download, FileText, Image, Loader2, Paperclip,
  Pencil, Plus, Send, ShieldCheck, Users, X, XCircle,
} from 'lucide-react'
import toast from 'react-hot-toast'

import { projectsApi, reportsApi, tasksApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import {
  DailyReport, Project, ReportStatus, RequirementConfirmation, Task,
} from '@/types'
import { formatDateTime, timeAgo } from '@/lib/utils'

const STATUS_LABELS: Record<ReportStatus, string> = {
  draft: 'Draft',
  needs_revision: 'Perlu Revisi',
  ready_for_review: 'Siap Direview',
  verified: 'Terverifikasi',
  approved: 'Disetujui',
}

const STATUS_CLASSES: Record<ReportStatus, string> = {
  draft: 'bg-slate-100 text-slate-700',
  needs_revision: 'bg-red-50 text-red-700',
  ready_for_review: 'bg-amber-50 text-amber-700',
  verified: 'bg-blue-50 text-blue-700',
  approved: 'bg-emerald-50 text-emerald-700',
}

type ReportForm = {
  project_id: string
  task_id: string
  report_text: string
  weather: string
  manpower_count: string
  actual_quantity: string
  actual_cost: string
  work_progress: string
  issues: string
}

const emptyForm = (): ReportForm => ({
  project_id: '',
  task_id: '',
  report_text: '',
  weather: '',
  manpower_count: '',
  actual_quantity: '',
  actual_cost: '',
  work_progress: '',
  issues: '',
})

function parseValidation(value?: string) {
  if (!value) return null
  try {
    return JSON.parse(value) as {
      score: number
      summary: string
      items: { code: string; label: string; passed: boolean; message: string }[]
    }
  } catch {
    return null
  }
}

export default function ReportsPage() {
  const qc = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const isReviewer = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const [showForm, setShowForm] = useState(false)
  const [editReport, setEditReport] = useState<DailyReport | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [form, setForm] = useState<ReportForm>(emptyForm())
  const [confirmed, setConfirmed] = useState<Record<number, boolean>>({})
  const [files, setFiles] = useState<File[]>([])
  const [reviewNotes, setReviewNotes] = useState<Record<number, string>>({})

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  const { data: tasks = [] } = useQuery<Task[]>({
    queryKey: ['tasks'],
    queryFn: async () => (await tasksApi.list()).data,
  })
  const { data: reports = [], isLoading } = useQuery<DailyReport[]>({
    queryKey: ['reports', statusFilter],
    queryFn: async () => (
      await reportsApi.list(statusFilter ? { status: statusFilter } : undefined)
    ).data,
  })

  const selectedTask = tasks.find((task) => task.id === Number(form.task_id))
  const availableTasks = useMemo(
    () => tasks.filter((task) => !form.project_id || task.project_id === Number(form.project_id)),
    [tasks, form.project_id],
  )
  const projectMap = Object.fromEntries(projects.map((project) => [project.id, project.project_name]))
  const taskMap = Object.fromEntries(tasks.map((task) => [task.id, task]))

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTask) throw new Error('Task wajib dipilih')
      const requirementConfirmations: RequirementConfirmation[] = selectedTask.requirements.map(
        (requirement) => ({
          requirement_id: requirement.id,
          confirmed: Boolean(confirmed[requirement.id]),
        }),
      )
      const payload = {
        project_id: Number(form.project_id),
        task_id: Number(form.task_id),
        report_text: form.report_text,
        weather: form.weather || null,
        manpower_count: form.manpower_count ? Number(form.manpower_count) : null,
        actual_quantity: form.actual_quantity ? Number(form.actual_quantity) : 0,
        actual_cost: form.actual_cost ? Number(form.actual_cost) : 0,
        work_progress: form.work_progress || null,
        issues: form.issues || null,
        requirement_confirmations: requirementConfirmations,
      }
      const response = editReport
        ? await reportsApi.update(editReport.id, payload)
        : await reportsApi.create(payload)
      const reportId = response.data.id as number
      for (const file of files) {
        const evidence = new FormData()
        evidence.append('evidence_type', file.type.startsWith('image/') ? 'photo' : 'document')
        evidence.append('caption', file.name)
        evidence.append('file', file)
        await reportsApi.uploadEvidence(reportId, evidence)
      }
      return response
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reports'] })
      closeForm()
      toast.success(editReport ? 'Draft diperbarui' : 'Draft dan evidence tersimpan')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || error.message || 'Gagal menyimpan laporan')
    },
  })

  const submitMutation = useMutation({
    mutationFn: (id: number) => reportsApi.submit(id),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ['reports'] })
      const status = response.data.workflow?.status as ReportStatus
      if (status === 'needs_revision') {
        toast.error('Laporan belum lengkap. Periksa hasil validasi.')
      } else {
        toast.success('Laporan masuk antrean review')
      }
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Submit gagal'),
  })

  const decisionMutation = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: string }) =>
      reportsApi.decide(id, decision, reviewNotes[id]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reports'] })
      toast.success('Keputusan review tersimpan')
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || 'Review gagal'),
  })

  function closeForm() {
    setShowForm(false)
    setEditReport(null)
    setForm(emptyForm())
    setConfirmed({})
    setFiles([])
  }

  function openEdit(report: DailyReport) {
    setEditReport(report)
    setForm({
      project_id: String(report.project_id),
      task_id: String(report.workflow?.task_id || ''),
      report_text: report.report_text,
      weather: report.weather || '',
      manpower_count: report.manpower_count == null ? '' : String(report.manpower_count),
      actual_quantity: report.progress_entry ? String(report.progress_entry.quantity_this_report) : '',
      actual_cost: report.progress_entry ? String(report.progress_entry.cost_this_report) : '',
      work_progress: report.work_progress || '',
      issues: report.issues || '',
    })
    setConfirmed(Object.fromEntries(
      report.requirement_checks.map((item) => [item.requirement_id, item.confirmed]),
    ))
    setFiles([])
    setShowForm(true)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    saveMutation.mutate()
  }

  async function downloadEvidence(evidenceId: number) {
    try {
      const response = await reportsApi.downloadEvidence(evidenceId)
      const url = URL.createObjectURL(response.data)
      const anchor = window.document.createElement('a')
      anchor.href = url
      anchor.download = `evidence-${evidenceId}`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Evidence tidak dapat dibuka')
    }
  }

  return (
    <div className="space-y-5 animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Laporan & Verifikasi</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {isReviewer ? 'Antrean pemeriksaan laporan lapangan' : 'Laporan berbasis task, requirement, dan evidence'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="input w-44 text-sm"
            aria-label="Filter status laporan"
          >
            <option value="">Semua status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          {!isReviewer && (
            <button onClick={() => setShowForm(true)} className="btn-primary">
              <Plus size={16} /> Laporan Baru
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {(Object.keys(STATUS_LABELS) as ReportStatus[]).map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(statusFilter === status ? '' : status)}
            className="border border-slate-200 bg-white p-3 text-left hover:border-slate-300"
          >
            <div className="text-xl font-bold text-slate-900">
              {reports.filter((report) => report.workflow?.status === status).length}
            </div>
            <div className="mt-1 text-xs text-slate-500">{STATUS_LABELS[status]}</div>
          </button>
        ))}
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto bg-white shadow-2xl">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white p-5">
              <div>
                <h2 className="font-semibold text-slate-950">
                  {editReport ? 'Perbaiki Draft Laporan' : 'Laporan Harian Terstruktur'}
                </h2>
                <p className="mt-0.5 text-xs text-slate-500">Template Laporan Harian Lapangan</p>
              </div>
              <button onClick={closeForm} className="btn-ghost p-2" title="Tutup"><X size={17} /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-5 p-5">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="label">Proyek *</label>
                  <select
                    required
                    disabled={Boolean(editReport)}
                    value={form.project_id}
                    onChange={(event) => setForm({
                      ...form, project_id: event.target.value, task_id: '',
                    })}
                    className="input"
                  >
                    <option value="">Pilih proyek</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>{project.project_name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Task / WBS *</label>
                  <select
                    required
                    disabled={Boolean(editReport)}
                    value={form.task_id}
                    onChange={(event) => {
                      setForm({ ...form, task_id: event.target.value })
                      setConfirmed({})
                    }}
                    className="input"
                  >
                    <option value="">Pilih pekerjaan</option>
                    {availableTasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {(task.specification?.wbs_code || task.id) + ' - ' + task.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="label">Volume aktual hari ini</label>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={form.actual_quantity}
                    onChange={(event) => setForm({ ...form, actual_quantity: event.target.value })}
                    className="input"
                    placeholder="Wajib untuk pekerjaan berbasis BOQ"
                  />
                </div>
                <div>
                  <label className="label">Biaya aktual hari ini</label>
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={form.actual_cost}
                    onChange={(event) => setForm({ ...form, actual_cost: event.target.value })}
                    className="input"
                    placeholder="Nilai realisasi biaya"
                  />
                </div>
              </div>

              {selectedTask?.specification && (
                <section className="border-l-4 border-cyan-500 bg-cyan-50 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-cyan-800">
                      WBS {selectedTask.specification.wbs_code}
                    </span>
                    <span className="text-xs text-cyan-700">
                      {selectedTask.specification.work_package}
                    </span>
                    <span className="text-xs text-cyan-700">
                      Template v{selectedTask.specification.template_version}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-slate-800">Acceptance criteria</p>
                  <p className="mt-1 text-sm leading-relaxed text-slate-600">
                    {selectedTask.specification.acceptance_criteria}
                  </p>
                  {selectedTask.specification.reporting_instructions && (
                    <p className="mt-2 text-xs leading-relaxed text-slate-500">
                      {selectedTask.specification.reporting_instructions}
                    </p>
                  )}
                </section>
              )}

              <div>
                <label className="label">Uraian kegiatan *</label>
                <textarea
                  required
                  minLength={10}
                  rows={4}
                  value={form.report_text}
                  onChange={(event) => setForm({ ...form, report_text: event.target.value })}
                  className="input resize-none"
                  placeholder="Jelaskan pekerjaan, volume aktual, area, dan hasil hari ini"
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="label">Progress pekerjaan *</label>
                  <textarea
                    required
                    rows={3}
                    value={form.work_progress}
                    onChange={(event) => setForm({ ...form, work_progress: event.target.value })}
                    className="input resize-none"
                    placeholder="Contoh: 12/20 titik selesai, 60%"
                  />
                </div>
                <div>
                  <label className="label">Kendala dan tindak lanjut</label>
                  <textarea
                    rows={3}
                    value={form.issues}
                    onChange={(event) => setForm({ ...form, issues: event.target.value })}
                    className="input resize-none"
                    placeholder="Tulis Tidak ada bila nihil"
                  />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="label">Cuaca</label>
                  <select
                    value={form.weather}
                    onChange={(event) => setForm({ ...form, weather: event.target.value })}
                    className="input"
                  >
                    <option value="">Pilih cuaca</option>
                    {['cerah', 'berawan', 'mendung', 'hujan', 'hujan lebat'].map((weather) => (
                      <option key={weather} value={weather}>{weather}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Jumlah tenaga kerja *</label>
                  <input
                    required
                    type="number"
                    min="0"
                    value={form.manpower_count}
                    onChange={(event) => setForm({ ...form, manpower_count: event.target.value })}
                    className="input"
                    placeholder="0"
                  />
                </div>
              </div>

              {selectedTask && selectedTask.requirements.length > 0 && (
                <section>
                  <div className="mb-2 flex items-center gap-2">
                    <ClipboardCheck size={16} className="text-cyan-600" />
                    <h3 className="text-sm font-semibold text-slate-900">Checklist requirement</h3>
                  </div>
                  <div className="divide-y divide-slate-100 border border-slate-200">
                    {selectedTask.requirements.map((requirement) => (
                      <label key={requirement.id} className="flex cursor-pointer items-start gap-3 p-3 hover:bg-slate-50">
                        <input
                          type="checkbox"
                          checked={Boolean(confirmed[requirement.id])}
                          onChange={(event) => setConfirmed({
                            ...confirmed, [requirement.id]: event.target.checked,
                          })}
                          className="mt-1 h-4 w-4 accent-cyan-600"
                        />
                        <span>
                          <span className="block text-sm font-medium text-slate-800">{requirement.title}</span>
                          <span className="mt-0.5 block text-xs text-slate-500">
                            {requirement.code} - {requirement.description}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                </section>
              )}

              <section>
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Paperclip size={16} className="text-cyan-600" />
                    <h3 className="text-sm font-semibold text-slate-900">Evidence</h3>
                  </div>
                  {selectedTask?.specification && (
                    <span className="text-xs text-slate-500">
                      Wajib {selectedTask.specification.required_photo_count} foto dan{' '}
                      {selectedTask.specification.required_document_count} dokumen
                    </span>
                  )}
                </div>
                <input
                  type="file"
                  multiple
                  accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
                  onChange={(event) => setFiles(Array.from(event.target.files || []))}
                  className="input text-sm"
                />
                {files.length > 0 && (
                  <p className="mt-2 text-xs text-slate-500">{files.length} file siap diunggah</p>
                )}
              </section>

              <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
                <button type="button" onClick={closeForm} className="btn-secondary">Batal</button>
                <button type="submit" disabled={saveMutation.isPending} className="btn-primary">
                  {saveMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
                  Simpan Draft
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-cyan-600" /></div>
      ) : reports.length === 0 ? (
        <div className="border border-dashed border-slate-300 bg-white py-16 text-center">
          <FileText size={36} className="mx-auto text-slate-300" />
          <p className="mt-3 text-sm text-slate-500">Belum ada laporan pada antrean ini.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => {
            const workflow = report.workflow
            const status = workflow?.status || 'draft'
            const task = workflow ? taskMap[workflow.task_id] : undefined
            const validation = parseValidation(workflow?.validation_result)
            const canEdit = !isReviewer && ['draft', 'needs_revision'].includes(status)
            return (
              <article key={report.id} className="card overflow-hidden">
                <div className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={'px-2 py-1 text-xs font-semibold ' + STATUS_CLASSES[status]}>
                          {STATUS_LABELS[status]}
                        </span>
                        {task?.specification?.wbs_code && (
                          <span className="text-xs font-semibold text-cyan-700">
                            WBS {task.specification.wbs_code}
                          </span>
                        )}
                        <span className="text-xs text-slate-400">#{report.id}</span>
                      </div>
                      <h2 className="mt-2 text-sm font-semibold text-slate-900">
                        {task?.title || 'Task tidak tersedia'}
                      </h2>
                      <p className="mt-1 text-xs text-slate-500">
                        {projectMap[report.project_id]} · {timeAgo(report.report_date)} · {formatDateTime(report.report_date)}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {canEdit && (
                        <button onClick={() => openEdit(report)} className="btn-ghost p-2" title="Edit draft">
                          <Pencil size={15} />
                        </button>
                      )}
                      <button
                        onClick={() => setExpanded(expanded === report.id ? null : report.id)}
                        className="btn-ghost p-2"
                        title="Detail laporan"
                      >
                        {expanded === report.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2 text-xs md:grid-cols-4">
                    <div className="flex items-center gap-2 text-slate-600">
                      <Users size={13} /> {report.manpower_count ?? '-'} pekerja
                    </div>
                    <div className="flex items-center gap-2 text-slate-600">
                      <CloudSun size={13} /> {report.weather || '-'}
                    </div>
                    <div className="flex items-center gap-2 text-slate-600">
                      <Image size={13} /> {report.evidence.filter((item) => item.evidence_type === 'photo').length} foto
                    </div>
                    <div className="flex items-center gap-2 text-slate-600">
                      <Paperclip size={13} /> {report.evidence.filter((item) => item.evidence_type === 'document').length} dokumen
                    </div>
                  </div>

                  {workflow?.revision_note && (
                    <div className="mt-3 flex items-start gap-2 bg-red-50 p-3 text-xs text-red-700">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span><strong>Catatan revisi:</strong> {workflow.revision_note}</span>
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3">
                    <div className="text-xs text-slate-500">
                      Skor pemeriksaan: <strong className="text-slate-800">{workflow?.validation_score || 0}%</strong>
                    </div>
                    {!isReviewer && ['draft', 'needs_revision'].includes(status) && (
                      <button
                        onClick={() => submitMutation.mutate(report.id)}
                        disabled={submitMutation.isPending}
                        className="btn-primary"
                      >
                        <Send size={14} /> Validasi & Submit
                      </button>
                    )}
                    {isReviewer && status === 'ready_for_review' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => decisionMutation.mutate({ id: report.id, decision: 'needs_revision' })}
                          className="btn-secondary text-red-700"
                        >
                          <XCircle size={14} /> Revisi
                        </button>
                        <button
                          onClick={() => decisionMutation.mutate({ id: report.id, decision: 'verified' })}
                          className="btn-primary"
                        >
                          <ShieldCheck size={14} /> Verifikasi
                        </button>
                      </div>
                    )}
                    {isReviewer && status === 'verified' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => decisionMutation.mutate({ id: report.id, decision: 'needs_revision' })}
                          className="btn-secondary text-red-700"
                        >
                          <XCircle size={14} /> Revisi
                        </button>
                        <button
                          onClick={() => decisionMutation.mutate({ id: report.id, decision: 'approved' })}
                          className="btn-primary"
                        >
                          <CheckCircle2 size={14} /> Setujui
                        </button>
                      </div>
                    )}
                  </div>
                  {isReviewer && ['ready_for_review', 'verified'].includes(status) && (
                    <textarea
                      rows={2}
                      value={reviewNotes[report.id] || ''}
                      onChange={(event) => setReviewNotes({
                        ...reviewNotes, [report.id]: event.target.value,
                      })}
                      className="input mt-3 resize-none text-sm"
                      placeholder="Catatan reviewer; wajib saat meminta revisi"
                    />
                  )}
                </div>

                {expanded === report.id && (
                  <div className="space-y-5 border-t border-slate-200 bg-slate-50 p-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <p className="label">Uraian kegiatan</p>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{report.report_text}</p>
                      </div>
                      <div>
                        <p className="label">Progress pekerjaan</p>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{report.work_progress || '-'}</p>
                        {report.progress_entry && (
                          <p className="mt-2 text-xs font-medium text-cyan-700">
                            Volume {report.progress_entry.quantity_this_report.toLocaleString('id-ID')} | Biaya Rp {report.progress_entry.cost_this_report.toLocaleString('id-ID')}
                          </p>
                        )}
                        <p className="label mt-3">Kendala</p>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{report.issues || 'Tidak ada'}</p>
                      </div>
                    </div>

                    <div>
                      <p className="label">Hasil pemeriksaan sistem</p>
                      {validation ? (
                        <div className="mt-2 grid gap-2 md:grid-cols-2">
                          {validation.items.map((item) => (
                            <div key={item.code} className="flex items-start gap-2 border border-slate-200 bg-white p-3">
                              {item.passed
                                ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                                : <XCircle size={15} className="mt-0.5 shrink-0 text-red-600" />}
                              <div>
                                <p className="text-xs font-semibold text-slate-800">{item.label}</p>
                                <p className="mt-0.5 text-xs text-slate-500">{item.message}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-slate-500">Belum divalidasi.</p>
                      )}
                    </div>

                    <div>
                      <p className="label">Evidence</p>
                      <div className="mt-2 divide-y divide-slate-100 border border-slate-200 bg-white">
                        {report.evidence.map((item) => (
                          <div key={item.id} className="flex items-center justify-between gap-3 p-3">
                            <div className="flex min-w-0 items-center gap-2">
                              {item.evidence_type === 'photo' ? <Image size={15} /> : <FileText size={15} />}
                              <span className="truncate text-xs text-slate-700">{item.file_name}</span>
                            </div>
                            <button onClick={() => downloadEvidence(item.id)} className="btn-ghost p-2" title="Buka evidence">
                              <Download size={14} />
                            </button>
                          </div>
                        ))}
                        {report.evidence.length === 0 && (
                          <p className="p-3 text-xs text-slate-500">Belum ada evidence.</p>
                        )}
                      </div>
                    </div>

                    <div>
                      <p className="label">Riwayat workflow</p>
                      <div className="mt-2 space-y-2">
                        {report.reviews.map((review) => (
                          <div key={review.id} className="flex items-start gap-2 text-xs text-slate-600">
                            <Calendar size={13} className="mt-0.5 shrink-0 text-slate-400" />
                            <span>
                              {review.from_status} → {review.to_status} · {formatDateTime(review.created_at)}
                              {review.note ? ' · ' + review.note : ''}
                            </span>
                          </div>
                        ))}
                        {report.reviews.length === 0 && <p className="text-xs text-slate-500">Belum ada transisi.</p>}
                      </div>
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
