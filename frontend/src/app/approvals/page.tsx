'use client'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { approvalsApi, documentsApi, projectsApi, usersApi } from '@/lib/api'
import { demoApprovals, demoProjects, demoUsers } from '@/lib/demo-data'
import { Approval, ApprovalStatus, DocumentSyncSession, Project, User } from '@/types'
import { formatDate } from '@/lib/utils'
import { CheckCircle2, Clock3, FileCheck2, GitCompareArrows, Loader2, Plus, Send, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import DocumentSyncPanel from '@/components/documents/DocumentSyncPanel'

const STATUS_CLASS: Record<ApprovalStatus, string> = {
  pending: 'bg-amber-50 text-amber-700',
  approved: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-rose-50 text-rose-700',
  cancelled: 'bg-slate-100 text-slate-600',
}

export default function ApprovalsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [syncSession, setSyncSession] = useState<DocumentSyncSession | null>(null)
  const [syncLoadingId, setSyncLoadingId] = useState<number | null>(null)
  const [form, setForm] = useState({
    project_id: '',
    approver_id: '',
    approval_type: 'instruction',
    title: '',
    description: '',
    due_date: '',
  })

  const { data: approvalData } = useQuery<Approval[]>({
    queryKey: ['approvals'],
    queryFn: async () => (await approvalsApi.list()).data,
  })
  const { data: projectData } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  const { data: userData } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: async () => (await usersApi.list()).data,
  })

  const approvals = approvalData?.length ? approvalData : demoApprovals
  const projects = projectData?.length ? projectData : demoProjects
  const users = userData?.length ? userData : demoUsers

  const projectMap = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p])), [projects])
  const userMap = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const pending = approvals.filter((a) => a.status === 'pending')
  const approved = approvals.filter((a) => a.status === 'approved')
  const rejected = approvals.filter((a) => a.status === 'rejected')

  const createApproval = useMutation({
    mutationFn: (data: Record<string, unknown>) => approvalsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['approvals'] })
      setShowForm(false)
      setForm({ project_id: '', approver_id: '', approval_type: 'instruction', title: '', description: '', due_date: '' })
      toast.success('Approval request dibuat')
    },
    onError: () => toast.error('Gagal membuat approval'),
  })

  const decideApproval = useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: ApprovalStatus; note?: string }) =>
      approvalsApi.decide(id, status, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['approvals'] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['controls-summary'] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      toast.success('Keputusan approval tersimpan')
    },
    onError: () => toast.error('Gagal menyimpan keputusan'),
  })

  function submitApproval(e: React.FormEvent) {
    e.preventDefault()
    if (!form.project_id || !form.title) {
      toast.error('Pilih proyek dan isi judul approval')
      return
    }
    createApproval.mutate({
      project_id: Number(form.project_id),
      approver_id: form.approver_id ? Number(form.approver_id) : undefined,
      approval_type: form.approval_type,
      title: form.title,
      description: form.description,
      due_date: form.due_date || undefined,
    })
  }

  function decide(id: number, status: ApprovalStatus) {
    const note = window.prompt(status === 'approved' ? 'Catatan approval' : 'Alasan keputusan') ?? undefined
    decideApproval.mutate({ id, status, note })
  }

  async function reviewDocumentSync(syncId: number) {
    setSyncLoadingId(syncId)
    try {
      const response = await documentsApi.getSync(syncId)
      setSyncSession(response.data)
    } catch {
      toast.error('Detail sinkronisasi tidak dapat dibuka')
    } finally {
      setSyncLoadingId(null)
    }
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Communication control</p>
          <h1 className="page-title">Approval center</h1>
          <p className="text-sm text-slate-500 mt-0.5">Kelola persetujuan instruksi, dokumen, task, dan perubahan scope.</p>
        </div>
        <button onClick={() => setShowForm((v) => !v)} className="btn-primary">
          <Plus size={16} /> Approval Baru
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Pending approval', value: pending.length, icon: Clock3, className: 'bg-amber-50 text-amber-700' },
          { label: 'Approved', value: approved.length, icon: CheckCircle2, className: 'bg-emerald-50 text-emerald-700' },
          { label: 'Rejected', value: rejected.length, icon: XCircle, className: 'bg-rose-50 text-rose-700' },
          { label: 'Total request', value: approvals.length, icon: FileCheck2, className: 'bg-cyan-50 text-cyan-700' },
        ].map((item) => (
          <div key={item.label} className="card p-5">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.className}`}>
              <item.icon size={18} />
            </div>
            <div className="mt-4 text-3xl font-bold text-slate-950">{item.value}</div>
            <p className="mt-1 text-sm text-slate-500">{item.label}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <form onSubmit={submitApproval} className="card p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="label">Proyek</label>
              <select className="input" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })}>
                <option value="">Pilih proyek</option>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.project_name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Approver</label>
              <select className="input" value={form.approver_id} onChange={(e) => setForm({ ...form, approver_id: e.target.value })}>
                <option value="">Auto / belum ditentukan</option>
                {users.filter((u) => ['admin', 'director', 'manager'].includes(u.role)).map((user) => (
                  <option key={user.id} value={user.id}>{user.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Tipe</label>
              <select className="input" value={form.approval_type} onChange={(e) => setForm({ ...form, approval_type: e.target.value })}>
                <option value="instruction">Instruksi</option>
                <option value="document">Dokumen</option>
                <option value="task">Task</option>
                <option value="scope_change">Perubahan scope</option>
                <option value="other">Lainnya</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-[1fr_220px] gap-4">
            <div>
              <label className="label">Judul</label>
              <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Contoh: Approval revisi rute MEP basement" />
            </div>
            <div>
              <label className="label">Due date</label>
              <input type="date" className="input" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Deskripsi</label>
            <textarea className="input min-h-24 resize-none" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <button className="btn-primary" disabled={createApproval.isPending}>
            <Send size={15} /> Kirim Approval
          </button>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100">
              {['Approval', 'Proyek', 'Requester', 'Approver', 'Status', 'Due', 'Aksi'].map((h) => (
                <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {approvals.map((approval) => (
              <tr key={approval.id} className="hover:bg-slate-50 transition">
                <td className="px-5 py-4">
                  <div className="font-semibold text-sm text-slate-900">{approval.title}</div>
                  <p className="mt-1 text-xs text-slate-500 line-clamp-1">{approval.description || 'Tidak ada deskripsi'}</p>
                </td>
                <td className="px-5 py-4 text-sm text-slate-600">{projectMap[approval.project_id]?.project_name || `Project #${approval.project_id}`}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{userMap[approval.requested_by]?.name || `User #${approval.requested_by}`}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{approval.approver_id ? userMap[approval.approver_id]?.name || `User #${approval.approver_id}` : '-'}</td>
                <td className="px-5 py-4">
                  <span className={`${STATUS_CLASS[approval.status]} badge`}>{approval.status}</span>
                </td>
                <td className="px-5 py-4 text-xs text-slate-500">{formatDate(approval.due_date || approval.created_at)}</td>
                <td className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    {approval.related_entity_type === 'document_sync' && approval.related_entity_id && (
                      <button onClick={() => reviewDocumentSync(approval.related_entity_id!)} className="btn-ghost p-2 text-cyan-700" title="Review perubahan dokumen">
                        {syncLoadingId === approval.related_entity_id ? <Loader2 size={15} className="animate-spin" /> : <GitCompareArrows size={15} />}
                      </button>
                    )}
                    {approval.status === 'pending' ? (
                      <>
                      <button onClick={() => decide(approval.id, 'approved')} className="btn-ghost text-emerald-600 px-2 py-1">Approve</button>
                      <button onClick={() => decide(approval.id, 'rejected')} className="btn-ghost text-rose-600 px-2 py-1">Reject</button>
                      </>
                    ) : <span className="text-xs text-slate-400">{approval.decision_note || 'Selesai'}</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {syncSession && <DocumentSyncPanel session={syncSession} onClose={() => setSyncSession(null)} onUpdated={setSyncSession} />}
    </div>
  )
}
