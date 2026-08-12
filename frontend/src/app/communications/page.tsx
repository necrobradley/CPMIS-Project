'use client'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { communicationsApi, projectsApi, tasksApi, usersApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import {
  CommunicationDetail, CommunicationItem, CommunicationStatus, CommunicationType,
  Project, Task, TaskPriority, User,
} from '@/types'
import { formatDate, isOverdue, priorityBadgeClass, PRIORITY_LABELS } from '@/lib/utils'
import {
  AlertTriangle, AtSign, BellRing, CheckCircle2, Clock3, Eye, FileQuestion,
  Filter, Inbox, Loader2, Megaphone, MessageCircle, MessageSquarePlus,
  Paperclip, Plus, Search, Send, UploadCloud, UserRoundCheck, X,
} from 'lucide-react'
import toast from 'react-hot-toast'

const TYPE_LABELS: Record<CommunicationType, string> = {
  rfi: 'RFI',
  submittal: 'Submittal',
  site_instruction: 'Site Instruction',
  issue: 'Issue',
  escalation: 'Escalation',
  meeting_action: 'Meeting Action',
}

const STATUS_LABELS: Record<CommunicationStatus, string> = {
  draft: 'Draft', open: 'Open', in_review: 'In Review', answered: 'Answered', closed: 'Closed', void: 'Void',
}

const STATUS_CLASS: Record<CommunicationStatus, string> = {
  draft: 'bg-slate-100 text-slate-600',
  open: 'bg-amber-50 text-amber-700',
  in_review: 'bg-cyan-50 text-cyan-700',
  answered: 'bg-emerald-50 text-emerald-700',
  closed: 'bg-slate-100 text-slate-500',
  void: 'bg-rose-50 text-rose-700',
}

const MESSAGE_TONE: Record<string, string> = {
  system: 'bg-slate-100 text-slate-600',
  comment: 'bg-cyan-50 text-cyan-700',
  response: 'bg-emerald-50 text-emerald-700',
  attachment: 'bg-violet-50 text-violet-700',
  status_update: 'bg-amber-50 text-amber-700',
  manual_escalation: 'bg-rose-50 text-rose-700',
  auto_escalation: 'bg-rose-50 text-rose-700',
}

const TYPE_OPTIONS: CommunicationType[] = ['rfi', 'submittal', 'site_instruction', 'issue', 'escalation', 'meeting_action']
const STATUS_OPTIONS: CommunicationStatus[] = ['open', 'in_review', 'answered', 'closed']

const EMPTY_FORM = {
  project_id: '', communication_type: 'rfi' as CommunicationType, assigned_to: '', priority: 'high' as TaskPriority,
  related_task_id: '', subject: '', discipline: '', location: '', due_date: '', question: '', description: '',
}

export default function CommunicationsPage() {
  const queryClient = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const isManagement = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const requiresTaskContext = user?.role === 'staff' || user?.role === 'subcontractor'
  const [showForm, setShowForm] = useState(false)
  const [typeFilter, setTypeFilter] = useState<'all' | CommunicationType>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | CommunicationStatus>('all')
  const [mineOnly, setMineOnly] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedItem, setSelectedItem] = useState<CommunicationItem | null>(null)
  const [reply, setReply] = useState('')
  const [replyAsResponse, setReplyAsResponse] = useState(false)
  const [mentionIds, setMentionIds] = useState<string[]>([])
  const [attachmentFile, setAttachmentFile] = useState<File | null>(null)
  const [attachmentCaption, setAttachmentCaption] = useState('')
  const [form, setForm] = useState(EMPTY_FORM)

  const params = useMemo(() => {
    const next: Record<string, unknown> = {}
    if (typeFilter !== 'all') next.communication_type = typeFilter
    if (mineOnly) next.mine = true
    return next
  }, [typeFilter, mineOnly])

  const { data: communicationData, isLoading } = useQuery<CommunicationItem[]>({
    queryKey: ['communications', params],
    queryFn: async () => (await communicationsApi.list(params)).data,
  })
  const { data: projectData } = useQuery<Project[]>({ queryKey: ['projects'], queryFn: async () => (await projectsApi.list()).data })
  const coordinationProjectId = selectedItem?.project_id || (form.project_id ? Number(form.project_id) : undefined)
  const { data: taskData = [] } = useQuery<Task[]>({
    queryKey: ['communication-tasks', form.project_id, requiresTaskContext ? 'division' : 'all'],
    queryFn: async () => form.project_id ? (await tasksApi.list({
      project_id: Number(form.project_id),
      ...(requiresTaskContext ? { scope: 'division' } : {}),
    })).data : [],
    enabled: Boolean(form.project_id),
  })
  const { data: userData } = useQuery<User[]>({
    queryKey: ['users', coordinationProjectId],
    queryFn: async () => (await usersApi.list(coordinationProjectId)).data,
  })
  const { data: detailData, isFetching: detailLoading } = useQuery<CommunicationDetail>({
    queryKey: ['communication-detail', selectedItem?.id],
    queryFn: async () => (await communicationsApi.get(selectedItem!.id)).data,
    enabled: Boolean(selectedItem && communicationData),
    retry: false,
  })

  const communications = communicationData ?? []
  const projects = projectData ?? []
  const tasks = taskData
  const users = userData ?? []
  const projectMap = useMemo(() => Object.fromEntries(projects.map((project) => [project.id, project])) as Record<number, Project>, [projects])
  const userMap = useMemo(() => Object.fromEntries(users.map((user) => [user.id, user])) as Record<number, User>, [users])

  const openItems = communications.filter((item) => ['open', 'in_review'].includes(item.status))
  const answeredItems = communications.filter((item) => item.status === 'answered')
  const overdueItems = communications.filter((item) => ['open', 'in_review'].includes(item.status) && isOverdue(item.due_date))
  const criticalItems = communications.filter((item) => item.priority === 'critical' && !['closed', 'void'].includes(item.status))
  const unreadItems = communications.filter((item) => (item.unread_count || 0) > 0 || (item.mention_count || 0) > 0)
  const normalizedSearch = search.trim().toLowerCase()
  const filteredItems = communications.filter((item) => {
    if (statusFilter !== 'all' && item.status !== statusFilter) return false
    if (!normalizedSearch) return true
    const projectName = projectMap[item.project_id]?.project_name || ''
    const assigneeName = item.assigned_to ? userMap[item.assigned_to]?.name || '' : ''
    return [item.subject, item.discipline, item.location, item.question, item.description, projectName, assigneeName]
      .some((value) => value?.toLowerCase().includes(normalizedSearch))
  })

  const selectedDetail = detailData || (selectedItem ? ({ ...selectedItem, messages: [], attachments: [], mentions: [], read_receipts: [], links: [] } as CommunicationDetail) : null)

  const createItem = useMutation({
    mutationFn: (data: Record<string, unknown>) => communicationsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      setShowForm(false)
      setForm(EMPTY_FORM)
      toast.success('Communication item dibuat')
    },
    onError: () => toast.error('Gagal membuat communication item'),
  })

  const updateItem = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => communicationsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      queryClient.invalidateQueries({ queryKey: ['communication-detail', variables.id] })
      toast.success('Communication item diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui communication item'),
  })

  const replyMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => communicationsApi.message(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      queryClient.invalidateQueries({ queryKey: ['communication-detail', variables.id] })
      setReply('')
      setMentionIds([])
      setReplyAsResponse(false)
      toast.success('Pesan terkirim')
    },
    onError: () => toast.error('Gagal mengirim pesan'),
  })

  const uploadMutation = useMutation({
    mutationFn: ({ id, formData }: { id: number; formData: FormData }) => communicationsApi.uploadAttachment(id, formData),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      queryClient.invalidateQueries({ queryKey: ['communication-detail', variables.id] })
      setAttachmentFile(null)
      setAttachmentCaption('')
      toast.success('Attachment diunggah')
    },
    onError: () => toast.error('Gagal upload attachment'),
  })

  const markReadMutation = useMutation({
    mutationFn: (id: number) => communicationsApi.markRead(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      queryClient.invalidateQueries({ queryKey: ['communication-detail', id] })
    },
  })

  const escalateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) => communicationsApi.escalate(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      queryClient.invalidateQueries({ queryKey: ['communication-detail', variables.id] })
      toast.success('Item dieskalasikan')
    },
    onError: () => toast.error('Gagal melakukan eskalasi'),
  })

  const slaMutation = useMutation({
    mutationFn: () => communicationsApi.runSlaEscalation(),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['communications'] })
      toast.success(`${response.data.escalated || 0} item overdue diproses`)
    },
    onError: () => toast.error('Gagal menjalankan SLA escalation'),
  })

  function submitItem(event: React.FormEvent) {
    event.preventDefault()
    if (!form.project_id || !form.subject) {
      toast.error('Pilih proyek dan isi subject')
      return
    }
    if (requiresTaskContext && !form.related_task_id) {
      toast.error('Staff wajib memilih task terkait')
      return
    }
    createItem.mutate({
      project_id: Number(form.project_id), communication_type: form.communication_type,
      assigned_to: form.assigned_to ? Number(form.assigned_to) : undefined,
      related_task_id: form.related_task_id ? Number(form.related_task_id) : undefined,
      priority: form.priority, subject: form.subject, discipline: form.discipline || undefined,
      location: form.location || undefined,
      due_date: form.due_date ? new Date(`${form.due_date}T17:00:00`).toISOString() : undefined,
      question: form.question || undefined, description: form.description || undefined,
    })
  }

  function openDetail(item: CommunicationItem, asResponse = false) {
    setSelectedItem(item)
    setReplyAsResponse(asResponse)
    if (communicationData) markReadMutation.mutate(item.id)
  }

  function submitReply(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedItem || !reply.trim()) return
    replyMutation.mutate({
      id: selectedItem.id,
      data: {
        message: reply.trim(),
        message_type: replyAsResponse ? 'response' : 'comment',
        mention_user_ids: mentionIds.map(Number),
      },
    })
  }

  function submitAttachment(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedItem || !attachmentFile) return
    const formData = new FormData()
    formData.append('file', attachmentFile)
    if (attachmentCaption.trim()) formData.append('caption', attachmentCaption.trim())
    uploadMutation.mutate({ id: selectedItem.id, formData })
  }

  function escalateItem(item: CommunicationItem) {
    const reason = window.prompt('Alasan eskalasi', `Butuh keputusan/tindak lanjut untuk: ${item.subject}`)
    if (!reason?.trim()) return
    escalateMutation.mutate({ id: item.id, data: { reason: reason.trim(), assigned_to: item.assigned_to } })
  }

  return (
    <div className="space-y-7 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-cyan-700"><Inbox size={14} /> Koordinasi lintas tim</div>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">Communication Hub</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Kelola RFI, submittal, instruksi lapangan, issue, eskalasi, tindak lanjut rapat, thread diskusi, mention, dan evidence dalam satu antrean.</p>
        </div>
        <div className="flex flex-wrap gap-2 self-start xl:self-auto">
          {isManagement && <button type="button" onClick={() => slaMutation.mutate()} disabled={slaMutation.isPending} className="btn-secondary"><BellRing size={16} /> SLA check</button>}
          <button type="button" onClick={() => setShowForm(true)} className="btn-primary"><Plus size={16} /> Item baru</button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        {[
          { label: 'Ball in court', value: openItems.length, helper: 'Perlu tindak lanjut', icon: UserRoundCheck, tone: 'bg-amber-50 text-amber-700' },
          { label: 'Overdue', value: overdueItems.length, helper: 'Melewati tenggat', icon: Clock3, tone: 'bg-rose-50 text-rose-700' },
          { label: 'Unread', value: unreadItems.length, helper: 'Thread/mention baru', icon: MessageCircle, tone: 'bg-violet-50 text-violet-700' },
          { label: 'Answered', value: answeredItems.length, helper: 'Menunggu penutupan', icon: CheckCircle2, tone: 'bg-emerald-50 text-emerald-700' },
          { label: 'Critical open', value: criticalItems.length, helper: 'Prioritas segera', icon: AlertTriangle, tone: 'bg-cyan-50 text-cyan-700' },
        ].map((item) => (
          <div key={item.label} className="card p-5">
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${item.tone}`}><item.icon size={18} /></div>
            <div className="mt-4 text-3xl font-bold text-slate-950">{item.value}</div>
            <p className="mt-1 text-sm font-medium text-slate-700">{item.label}</p>
            <p className="mt-1 text-xs text-slate-400">{item.helper}</p>
          </div>
        ))}
      </div>

      <section className="card overflow-hidden">
        <div className="border-b border-slate-200 p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
            <div className="relative min-w-0 flex-1 xl:max-w-sm">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} className="input pl-9" placeholder="Cari subject, proyek, atau PIC" aria-label="Cari komunikasi" />
            </div>
            <div className="flex min-w-0 items-center gap-2 overflow-x-auto pb-1 xl:pb-0">
              <button type="button" onClick={() => setTypeFilter('all')} className={typeFilter === 'all' ? 'btn-primary whitespace-nowrap py-2' : 'btn-ghost whitespace-nowrap py-2'}>Semua</button>
              {TYPE_OPTIONS.map((type) => <button type="button" key={type} onClick={() => setTypeFilter(type)} className={typeFilter === type ? 'btn-primary whitespace-nowrap py-2' : 'btn-ghost whitespace-nowrap py-2'}>{TYPE_LABELS[type]}</button>)}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500"><Filter size={14} /> Filter antrean</div>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as 'all' | CommunicationStatus)} className="input w-auto py-1.5" aria-label="Filter status">
              <option value="all">Semua status</option>
              {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
            </select>
            <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={mineOnly} onChange={(event) => setMineOnly(event.target.checked)} className="h-4 w-4 accent-brand-500" /> Tugas saya
            </label>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16"><Loader2 size={24} className="animate-spin text-brand-500" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-[1120px] w-full">
              <thead className="bg-slate-50/80">
                <tr className="border-b border-slate-200">
                  {['Item komunikasi', 'Proyek', 'Ball in court', 'Status', 'Prioritas', 'Due', 'Aksi'].map((header) => <th key={header} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{header}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredItems.map((item) => {
                  const itemOverdue = isOverdue(item.due_date) && ['open', 'in_review'].includes(item.status)
                  return (
                    <tr key={item.id} className="transition hover:bg-slate-50">
                      <td className="max-w-[420px] px-5 py-4">
                        <button type="button" onClick={() => openDetail(item)} className="flex w-full items-start gap-3 text-left">
                          <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700"><FileQuestion size={15} /></div>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold text-slate-900">{item.subject}</p>
                              {(item.unread_count || 0) > 0 && <span className="badge-warning">{item.unread_count} baru</span>}
                              {(item.mention_count || 0) > 0 && <span className="badge-info">@{item.mention_count}</span>}
                            </div>
                            <p className="mt-1 text-xs text-slate-500">{TYPE_LABELS[item.communication_type]}{item.discipline ? ` - ${item.discipline}` : ''}{item.location ? ` - ${item.location}` : ''}</p>
                            {(item.question || item.description) && <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.question || item.description}</p>}
                            <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
                              <span className="inline-flex items-center gap-1"><MessageCircle size={12} /> {item.thread_count || 0} thread</span>
                              <span className="inline-flex items-center gap-1"><Paperclip size={12} /> {item.attachment_count || 0} file</span>
                              {item.last_activity_at && <span>Aktif {formatDate(item.last_activity_at)}</span>}
                            </div>
                          </div>
                        </button>
                      </td>
                      <td className="max-w-[180px] px-5 py-4 text-sm text-slate-600">{projectMap[item.project_id]?.project_name || `Project #${item.project_id}`}</td>
                      <td className="px-5 py-4 text-sm font-medium text-slate-700">{item.assigned_to ? userMap[item.assigned_to]?.name || `User #${item.assigned_to}` : <span className="text-slate-400">Belum ditentukan</span>}</td>
                      <td className="px-5 py-4">
                        {isManagement ? (
                          <select value={item.status} onChange={(event) => updateItem.mutate({ id: item.id, data: { status: event.target.value as CommunicationStatus } })} className={`${STATUS_CLASS[item.status]} rounded-full border-0 px-2 py-1 text-xs font-semibold outline-none`} aria-label={`Status ${item.subject}`}>
                            {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
                          </select>
                        ) : (
                          <span className={`${STATUS_CLASS[item.status]} rounded-full px-2 py-1 text-xs font-semibold`}>{STATUS_LABELS[item.status]}</span>
                        )}
                      </td>
                      <td className="px-5 py-4"><span className={priorityBadgeClass(item.priority)}>{PRIORITY_LABELS[item.priority]}</span></td>
                      <td className="px-5 py-4"><span className={`inline-flex items-center gap-1.5 text-xs ${itemOverdue ? 'font-semibold text-rose-600' : 'text-slate-500'}`}>{itemOverdue && <AlertTriangle size={12} />}{item.due_date ? formatDate(item.due_date) : '-'}</span></td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-1">
                          <button type="button" onClick={() => openDetail(item)} className="btn-ghost p-2 text-slate-700" title="Buka detail" aria-label={`Buka detail ${item.subject}`}><Eye size={16} /></button>
                          <button type="button" onClick={() => openDetail(item, true)} className="btn-ghost p-2 text-cyan-700" title="Beri respons" aria-label={`Beri respons untuk ${item.subject}`}><MessageSquarePlus size={16} /></button>
                          <button type="button" onClick={() => escalateItem(item)} className="btn-ghost p-2 text-rose-700" title="Eskalasi" aria-label={`Eskalasi ${item.subject}`}><Megaphone size={16} /></button>
                          {isManagement && !['closed', 'void'].includes(item.status) && <button type="button" onClick={() => updateItem.mutate({ id: item.id, data: { status: 'closed' } })} className="btn-ghost p-2 text-emerald-700" title="Tutup item" aria-label={`Tutup ${item.subject}`}><CheckCircle2 size={16} /></button>}
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {!filteredItems.length && <tr><td colSpan={7} className="px-5 py-14 text-center"><Inbox size={24} className="mx-auto mb-2 text-slate-300" /><p className="text-sm text-slate-500">Tidak ada item yang sesuai dengan filter.</p></td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showForm && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" onClick={() => setShowForm(false)}>
          <aside className="h-full w-full max-w-2xl overflow-y-auto bg-white shadow-2xl" onClick={(event) => event.stopPropagation()} aria-label="Form item komunikasi baru">
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white px-6 py-5">
              <div><p className="text-xs font-semibold uppercase tracking-widest text-cyan-700">Communication register</p><h2 className="mt-1 text-lg font-semibold text-slate-950">Item komunikasi baru</h2></div>
              <button type="button" onClick={() => setShowForm(false)} className="btn-ghost p-2" title="Tutup"><X size={18} /></button>
            </div>
            <form onSubmit={submitItem} className="space-y-5 p-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div><label className="label">Proyek *</label><select required className="input" value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value, related_task_id: '' })}><option value="">Pilih proyek</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.project_name}</option>)}</select></div>
                <div><label className="label">Tipe *</label><select className="input" value={form.communication_type} onChange={(event) => setForm({ ...form, communication_type: event.target.value as CommunicationType })}>{TYPE_OPTIONS.map((type) => <option key={type} value={type}>{TYPE_LABELS[type]}</option>)}</select></div>
                <div><label className="label">Task terkait{requiresTaskContext ? ' *' : ''}</label><select required={requiresTaskContext} className="input" value={form.related_task_id} onChange={(event) => setForm({ ...form, related_task_id: event.target.value })}><option value="">Pilih task</option>{tasks.map((task) => <option key={task.id} value={task.id}>{(task.specification?.wbs_code || task.id) + ' - ' + task.title}</option>)}</select></div>
                <div><label className="label">Ball in court</label><select className="input" value={form.assigned_to} onChange={(event) => setForm({ ...form, assigned_to: event.target.value })}><option value="">Belum ditentukan</option>{users.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}</select></div>
                <div><label className="label">Prioritas</label><select className="input" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as TaskPriority })}><option value="low">Rendah</option><option value="medium">Sedang</option><option value="high">Tinggi</option><option value="critical">Kritis</option></select></div>
              </div>
              <div><label className="label">Subject *</label><input required className="input" value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} placeholder="Contoh: RFI-001 Klarifikasi pile cap zona A" /></div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div><label className="label">Disiplin</label><input className="input" value={form.discipline} onChange={(event) => setForm({ ...form, discipline: event.target.value })} placeholder="MEP" /></div>
                <div><label className="label">Lokasi</label><input className="input" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Basement B2" /></div>
                <div><label className="label">Due date</label><input type="date" className="input" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></div>
              </div>
              <div><label className="label">Question / Permintaan</label><textarea rows={4} className="input resize-none" value={form.question} onChange={(event) => setForm({ ...form, question: event.target.value })} placeholder="Jelaskan pertanyaan atau keputusan yang dibutuhkan." /></div>
              <div><label className="label">Deskripsi pendukung</label><textarea rows={4} className="input resize-none" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Tambahkan konteks, referensi dokumen, atau dampak pekerjaan." /></div>
              <div className="flex justify-end gap-2 border-t border-slate-200 pt-5"><button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Batal</button><button type="submit" disabled={createItem.isPending} className="btn-primary">{createItem.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Kirim item</button></div>
            </form>
          </aside>
        </div>
      )}

      {selectedDetail && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" onClick={() => setSelectedItem(null)}>
          <aside className="h-full w-full max-w-4xl overflow-y-auto bg-white shadow-2xl" onClick={(event) => event.stopPropagation()} aria-label="Detail komunikasi">
            <div className="sticky top-0 z-20 border-b border-slate-200 bg-white px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-widest text-cyan-700">{TYPE_LABELS[selectedDetail.communication_type]}</p>
                  <h2 className="mt-1 text-xl font-bold text-slate-950">{selectedDetail.subject}</h2>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className={STATUS_CLASS[selectedDetail.status] + ' rounded-full px-2 py-1 text-xs font-semibold'}>{STATUS_LABELS[selectedDetail.status]}</span>
                    <span className={priorityBadgeClass(selectedDetail.priority)}>{PRIORITY_LABELS[selectedDetail.priority]}</span>
                    <span className="badge-info"><MessageCircle size={12} /> {selectedDetail.thread_count || selectedDetail.messages.length} thread</span>
                    <span className="badge-info"><Paperclip size={12} /> {selectedDetail.attachment_count || selectedDetail.attachments.length} file</span>
                  </div>
                </div>
                <button type="button" onClick={() => setSelectedItem(null)} className="btn-ghost p-2" title="Tutup"><X size={18} /></button>
              </div>
            </div>

            <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div className="space-y-5">
                <section className="border border-slate-200 bg-white">
                  <div className="border-b border-slate-200 px-4 py-3">
                    <h3 className="font-bold text-slate-900">Thread komunikasi</h3>
                  </div>
                  {detailLoading ? (
                    <div className="flex justify-center py-12"><Loader2 size={22} className="animate-spin text-brand-500" /></div>
                  ) : (
                    <div className="divide-y divide-slate-100">
                      {selectedDetail.messages.map((message) => (
                        <div key={message.id} className="p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">{message.user_id ? userMap[message.user_id]?.name || `User #${message.user_id}` : 'System'}</p>
                              <p className="mt-0.5 text-xs text-slate-400">{formatDate(message.created_at)}</p>
                            </div>
                            <span className={(MESSAGE_TONE[message.message_type] || 'bg-slate-100 text-slate-600') + ' rounded-full px-2 py-1 text-xs font-semibold'}>{message.message_type.replace('_', ' ')}</span>
                          </div>
                          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{message.message}</p>
                          {message.mentions.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {message.mentions.map((mention) => <span key={mention.id} className="badge-info"><AtSign size={12} /> {userMap[mention.mentioned_user_id]?.name || `User #${mention.mentioned_user_id}`}</span>)}
                            </div>
                          )}
                          {message.attachments.length > 0 && (
                            <div className="mt-3 grid gap-2">
                              {message.attachments.map((attachment) => (
                                <a key={attachment.id} href={attachment.download_url || '#'} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                                  <span className="inline-flex min-w-0 items-center gap-2"><Paperclip size={14} className="text-slate-400" /><span className="truncate">{attachment.file_name}</span></span>
                                  <span className="text-xs text-slate-400">{attachment.file_size ? `${Math.round(attachment.file_size / 1024)} KB` : ''}</span>
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                      {!selectedDetail.messages.length && <div className="px-4 py-12 text-center text-sm text-slate-500">Belum ada thread detail untuk item ini.</div>}
                    </div>
                  )}
                </section>

                <form onSubmit={submitReply} className="border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="font-bold text-slate-900">Balas / beri keputusan</h3>
                    <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={replyAsResponse} onChange={(event) => setReplyAsResponse(event.target.checked)} className="h-4 w-4 accent-brand-500" /> Tandai sebagai jawaban</label>
                  </div>
                  <textarea rows={4} value={reply} onChange={(event) => setReply(event.target.value)} className="input mt-3 resize-none" placeholder="Tulis update, klarifikasi, instruksi, atau keputusan." />
                  <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                    <div>
                      <label className="label">Mention user</label>
                      <select multiple value={mentionIds} onChange={(event) => setMentionIds(Array.from(event.target.selectedOptions).map((option) => option.value))} className="input min-h-[92px]">
                        {users.map((user) => <option key={user.id} value={user.id}>{user.name} - {user.role}</option>)}
                      </select>
                    </div>
                    <button type="submit" disabled={replyMutation.isPending || !reply.trim()} className="btn-primary md:mb-0">{replyMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Kirim</button>
                  </div>
                </form>

                <form onSubmit={submitAttachment} className="border border-slate-200 bg-white p-4">
                  <h3 className="font-bold text-slate-900">Attachment / evidence</h3>
                  <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_auto] md:items-end">
                    <div>
                      <label className="label">File</label>
                      <input type="file" onChange={(event) => setAttachmentFile(event.target.files?.[0] || null)} className="input" />
                    </div>
                    <div>
                      <label className="label">Caption</label>
                      <input value={attachmentCaption} onChange={(event) => setAttachmentCaption(event.target.value)} className="input" placeholder="Opsional" />
                    </div>
                    <button type="submit" disabled={uploadMutation.isPending || !attachmentFile} className="btn-secondary">{uploadMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <UploadCloud size={15} />} Upload</button>
                  </div>
                </form>
              </div>

              <aside className="space-y-4">
                <div className="border border-slate-200 bg-white p-4">
                  <h3 className="font-bold text-slate-900">Konteks</h3>
                  <dl className="mt-3 space-y-3 text-sm">
                    <div><dt className="text-xs font-semibold uppercase text-slate-400">Proyek</dt><dd className="mt-1 text-slate-700">{projectMap[selectedDetail.project_id]?.project_name || `Project #${selectedDetail.project_id}`}</dd></div>
                    <div><dt className="text-xs font-semibold uppercase text-slate-400">Ball in court</dt><dd className="mt-1 text-slate-700">{selectedDetail.assigned_to ? userMap[selectedDetail.assigned_to]?.name || `User #${selectedDetail.assigned_to}` : 'Belum ditentukan'}</dd></div>
                    <div><dt className="text-xs font-semibold uppercase text-slate-400">Due date</dt><dd className="mt-1 text-slate-700">{selectedDetail.due_date ? formatDate(selectedDetail.due_date) : '-'}</dd></div>
                    {selectedDetail.related_task_id && <div><dt className="text-xs font-semibold uppercase text-slate-400">Task terkait</dt><dd className="mt-1 text-slate-700">Task #{selectedDetail.related_task_id}</dd></div>}
                    {(selectedDetail.discipline || selectedDetail.location) && <div><dt className="text-xs font-semibold uppercase text-slate-400">Area</dt><dd className="mt-1 text-slate-700">{selectedDetail.discipline || '-'}{selectedDetail.location ? ` - ${selectedDetail.location}` : ''}</dd></div>}
                  </dl>
                </div>

                {(selectedDetail.question || selectedDetail.description || selectedDetail.response) && (
                  <div className="border border-slate-200 bg-white p-4">
                    <h3 className="font-bold text-slate-900">Ringkasan item</h3>
                    {selectedDetail.question && <p className="mt-3 text-sm leading-6 text-slate-700">{selectedDetail.question}</p>}
                    {selectedDetail.description && <p className="mt-3 text-sm leading-6 text-slate-500">{selectedDetail.description}</p>}
                    {selectedDetail.response && <p className="mt-3 border-l-2 border-emerald-300 pl-3 text-sm leading-6 text-emerald-700">{selectedDetail.response}</p>}
                  </div>
                )}

                {selectedDetail.links.length > 0 && (
                  <div className="border border-slate-200 bg-white p-4">
                    <h3 className="font-bold text-slate-900">Auto-source</h3>
                    <div className="mt-3 space-y-2">
                      {selectedDetail.links.map((link) => <div key={link.id} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">{link.source_type} #{link.source_id}</div>)}
                    </div>
                  </div>
                )}

                <div className="border border-slate-200 bg-white p-4">
                  <h3 className="font-bold text-slate-900">Aksi cepat</h3>
                  <div className="mt-3 grid gap-2">
                    <button type="button" onClick={() => markReadMutation.mutate(selectedDetail.id)} className="btn-secondary justify-center"><CheckCircle2 size={15} /> Mark read</button>
                    <button type="button" onClick={() => escalateItem(selectedDetail)} className="btn-secondary justify-center text-rose-700"><Megaphone size={15} /> Eskalasi</button>
                    {isManagement && selectedDetail.status !== 'closed' && <button type="button" onClick={() => updateItem.mutate({ id: selectedDetail.id, data: { status: 'closed' } })} className="btn-secondary justify-center text-emerald-700"><CheckCircle2 size={15} /> Tutup item</button>}
                  </div>
                </div>
              </aside>
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}
