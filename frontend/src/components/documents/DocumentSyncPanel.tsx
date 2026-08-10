'use client'
import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, CheckCircle2, ChevronRight, FileCheck2, GitCompareArrows,
  Loader2, RefreshCw, Send, ShieldCheck, X,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { documentsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { DocumentSyncChange, DocumentSyncSession } from '@/types'

const STATUS_LABEL: Record<DocumentSyncSession['status'], string> = {
  draft: 'Draft preview',
  pending_approval: 'Menunggu approval',
  approved: 'Disetujui',
  applied: 'Sudah diterapkan',
  rejected: 'Ditolak',
  cancelled: 'Dibatalkan',
  failed: 'Gagal diterapkan',
}

const STATUS_CLASS: Record<DocumentSyncSession['status'], string> = {
  draft: 'bg-slate-100 text-slate-700',
  pending_approval: 'bg-amber-50 text-amber-700',
  approved: 'bg-emerald-50 text-emerald-700',
  applied: 'bg-cyan-50 text-cyan-700',
  rejected: 'bg-rose-50 text-rose-700',
  cancelled: 'bg-slate-100 text-slate-500',
  failed: 'bg-rose-50 text-rose-700',
}

function errorDetail(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'Belum ada'
  if (typeof value === 'number') return new Intl.NumberFormat('id-ID').format(value)
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function ChangeItem({
  change, checked, disabled, onToggle,
}: {
  change: DocumentSyncChange
  checked: boolean
  disabled: boolean
  onToggle: () => void
}) {
  return (
    <label className={`block border-b border-slate-100 p-4 last:border-b-0 ${disabled ? '' : 'cursor-pointer hover:bg-slate-50'}`}>
      <div className="flex items-start gap-3">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} className="mt-1 h-4 w-4 accent-brand-500" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">{change.label}</p>
            <span className={change.operation === 'create' ? 'badge-success' : 'badge-info'}>{change.operation === 'create' ? 'Baru' : 'Perbarui'}</span>
            {change.risk === 'high' && <span className="badge-danger">Perlu perhatian</span>}
          </div>
          <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-400">{change.entity}</p>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_20px_1fr] sm:items-stretch">
            <div className="min-w-0 rounded-lg bg-slate-50 p-3">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Data sekarang</p>
              <pre className="max-h-28 overflow-hidden whitespace-pre-wrap break-words font-sans text-xs leading-5 text-slate-600">{formatValue(change.before)}</pre>
            </div>
            <ChevronRight size={15} className="hidden self-center text-slate-300 sm:block" />
            <div className="min-w-0 rounded-lg bg-cyan-50 p-3">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-700">Usulan dokumen</p>
              <pre className="max-h-28 overflow-hidden whitespace-pre-wrap break-words font-sans text-xs leading-5 text-slate-700">{formatValue(change.after)}</pre>
            </div>
          </div>
        </div>
      </div>
    </label>
  )
}

export default function DocumentSyncPanel({
  session, onClose, onUpdated,
}: {
  session: DocumentSyncSession
  onClose: () => void
  onUpdated: (session: DocumentSyncSession) => void
}) {
  const queryClient = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const canApply = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const [selected, setSelected] = useState<string[]>(session.selected_change_ids)
  const locked = session.status !== 'draft'

  useEffect(() => setSelected(session.selected_change_ids), [session])

  const selectedSet = useMemo(() => new Set(selected), [selected])
  const changes = session.plan.changes
  const allSelected = changes.length > 0 && selected.length === changes.length

  const requestApproval = useMutation({
    mutationFn: () => documentsApi.requestSyncApproval(session.id, selected),
    onSuccess: (response) => {
      onUpdated(response.data)
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
      toast.success('Sinkronisasi diajukan ke Approval Center')
    },
    onError: (error) => toast.error(errorDetail(error, 'Gagal mengajukan approval')),
  })

  const refresh = useMutation({
    mutationFn: () => documentsApi.getSync(session.id),
    onSuccess: (response) => onUpdated(response.data),
    onError: (error) => toast.error(errorDetail(error, 'Gagal memperbarui status')),
  })

  const apply = useMutation({
    mutationFn: () => documentsApi.applySync(session.id),
    onSuccess: (response) => {
      onUpdated(response.data)
      for (const key of ['documents', 'projects', 'tasks', 'divisions']) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
      toast.success('Perubahan dokumen berhasil diterapkan')
    },
    onError: (error) => toast.error(errorDetail(error, 'Gagal menerapkan sinkronisasi')),
  })

  function toggle(changeId: string) {
    setSelected((current) => current.includes(changeId) ? current.filter((item) => item !== changeId) : [...current, changeId])
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/45" onClick={onClose}>
      <aside className="h-full w-full max-w-3xl overflow-y-auto bg-white shadow-2xl" onClick={(event) => event.stopPropagation()} aria-label="Sinkronisasi dokumen">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-cyan-700"><GitCompareArrows size={14} /> Sinkronisasi dokumen</span>
              <span className={`badge ${STATUS_CLASS[session.status]}`}>{STATUS_LABEL[session.status]}</span>
            </div>
            <h2 className="mt-2 truncate text-lg font-semibold text-slate-950">{session.plan.document.file_name}</h2>
            <p className="mt-1 text-xs text-slate-500">Versi {session.plan.document.version} untuk {session.plan.project.project_name}</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost p-2" title="Tutup"><X size={18} /></button>
        </div>

        <div className="space-y-5 p-5 sm:p-6">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-5">
            {[
              ['Total', session.plan.summary.total],
              ['Proyek', session.plan.summary.project_updates],
              ['Divisi baru', session.plan.summary.divisions_created],
              ['Task baru', session.plan.summary.tasks_created],
              ['Task berubah', session.plan.summary.tasks_updated],
            ].map(([label, value]) => <div key={label} className="bg-white p-3 text-center"><p className="text-xl font-bold text-slate-950">{value}</p><p className="mt-1 text-[11px] text-slate-500">{label}</p></div>)}
          </div>

          {session.plan.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-800"><AlertTriangle size={16} /> Batasan sinkronisasi</div>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-amber-800/80">{session.plan.warnings.map((warning) => <li key={warning}>- {warning}</li>)}</ul>
            </div>
          )}

          <section className="overflow-hidden rounded-lg border border-slate-200">
            <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
              <div><h3 className="text-sm font-semibold text-slate-900">Preview perubahan</h3><p className="mt-0.5 text-xs text-slate-500">{selected.length} dari {changes.length} perubahan dipilih</p></div>
              {!locked && changes.length > 0 && <button type="button" onClick={() => setSelected(allSelected ? [] : changes.map((item) => item.id))} className="text-xs font-semibold text-brand-600 hover:text-brand-700">{allSelected ? 'Kosongkan' : 'Pilih semua'}</button>}
            </div>
            {changes.map((change) => <ChangeItem key={change.id} change={change} checked={selectedSet.has(change.id)} disabled={locked} onToggle={() => toggle(change.id)} />)}
            {!changes.length && <div className="p-10 text-center"><CheckCircle2 size={25} className="mx-auto mb-2 text-emerald-500" /><p className="text-sm font-medium text-slate-700">Tidak ada perbedaan yang perlu diterapkan.</p></div>}
          </section>

          <div className="rounded-lg border border-cyan-100 bg-cyan-50/60 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-cyan-900"><ShieldCheck size={16} /> Kebijakan aman</div>
            <p className="mt-2 text-xs leading-5 text-cyan-900/70">Pencocokan menggunakan kode WBS. Status, progres, PIC, laporan, foto, dan evidence yang sudah ada tidak dihapus atau ditimpa.</p>
          </div>

          {session.error_message && <div className="rounded-lg bg-rose-50 p-4 text-xs text-rose-700">{session.error_message}</div>}
        </div>

        <div className="sticky bottom-0 flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 bg-white px-5 py-4 sm:px-6">
          {session.status !== 'draft' && session.status !== 'applied' && <button type="button" onClick={() => refresh.mutate()} disabled={refresh.isPending} className="btn-secondary">{refresh.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Refresh</button>}
          {session.status === 'draft' && changes.length > 0 && <button type="button" onClick={() => requestApproval.mutate()} disabled={!selected.length || requestApproval.isPending} className="btn-primary">{requestApproval.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Ajukan approval</button>}
          {session.status === 'pending_approval' && <Link href="/approvals" className="btn-primary"><FileCheck2 size={15} /> Buka Approval Center</Link>}
          {(session.status === 'approved' || session.status === 'failed') && canApply && <button type="button" onClick={() => apply.mutate()} disabled={apply.isPending} className="btn-primary">{apply.isPending ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />} {session.status === 'failed' ? 'Coba terapkan lagi' : 'Terapkan perubahan'}</button>}
          {session.status === 'approved' && !canApply && <p className="text-xs text-slate-500">Menunggu manager menerapkan perubahan.</p>}
          {session.status === 'applied' && <span className="flex items-center gap-2 text-sm font-semibold text-emerald-700"><CheckCircle2 size={17} /> Sinkronisasi selesai</span>}
        </div>
      </aside>
    </div>
  )
}
