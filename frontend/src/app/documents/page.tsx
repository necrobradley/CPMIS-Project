'use client'
import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentsApi, projectsApi } from '@/lib/api'
import { Project, Document, DocumentAnswer, DocumentSyncSession } from '@/types'
import { formatDate } from '@/lib/utils'
import {
  Upload, FolderOpen, Loader2, X, FileText, FileSpreadsheet,
  Image, File, Download, Bot, Trash2, Search, Plus, Eye, GitCompareArrows
} from 'lucide-react'
import toast from 'react-hot-toast'
import DocumentSyncPanel from '@/components/documents/DocumentSyncPanel'
import { useAuthStore } from '@/lib/store'

const DOC_TYPES = [
  { value: 'tender',       label: 'Dokumen Tender' },
  { value: 'contract',     label: 'Kontrak' },
  { value: 'daily_report', label: 'Laporan Harian' },
  { value: 'photo',        label: 'Foto' },
  { value: 'drawing',      label: 'Gambar/DED' },
  { value: 'other',        label: 'Lainnya' },
]

const FILE_ICON: Record<string, React.ReactNode> = {
  'application/pdf': <FileText size={20} className="text-red-500" />,
  'image/jpeg': <Image size={20} className="text-blue-500" />,
  'image/png':  <Image size={20} className="text-blue-500" />,
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
    <FileSpreadsheet size={20} className="text-green-500" />,
}

function formatBytes(b?: number) {
  if (!b) return '—'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

const SYNC_LABEL = {
  draft: 'Draft',
  pending_approval: 'Menunggu approval',
  approved: 'Disetujui',
  applied: 'Diterapkan',
  rejected: 'Ditolak',
  cancelled: 'Dibatalkan',
  failed: 'Gagal',
}

export default function DocumentsPage() {
  const qc = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const isManagement = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const isStaff = user?.role === 'staff' || user?.role === 'subcontractor'
  const fileRef = useRef<HTMLInputElement>(null)
  const [projectId, setProjectId] = useState<number | ''>('')
  const [docType, setDocType]     = useState('other')
  const [analyzeAI, setAnalyzeAI] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [search, setSearch] = useState('')
  const [aiModal, setAiModal] = useState<{ id: number; data: Record<string, unknown> } | null>(null)
  const [qaQuestion, setQaQuestion] = useState('')
  const [qaResult, setQaResult] = useState<DocumentAnswer | null>(null)
  const [syncSession, setSyncSession] = useState<DocumentSyncSession | null>(null)
  const [syncLoadingId, setSyncLoadingId] = useState<number | null>(null)

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  const { data: documents = [], isLoading } = useQuery<Document[]>({
    queryKey: ['documents', projectId],
    queryFn: async () => projectId ? (await documentsApi.list(projectId)).data : [],
    enabled: !!projectId,
  })

  const uploadMutation = useMutation({
    mutationFn: (fd: FormData) => documentsApi.upload(fd),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      setShowUpload(false)
      toast.success(res.data.message || 'Upload berhasil!')
    },
    onError: () => toast.error('Upload gagal'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => documentsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      toast.success('Dokumen dihapus')
    },
    onError: () => toast.error('Hapus gagal'),
  })

  const qaMutation = useMutation({
    mutationFn: ({ projectId, question }: { projectId: number; question: string }) =>
      documentsApi.qa(projectId, question),
    onSuccess: (res) => {
      setQaResult(res.data)
      toast.success('Jawaban dokumen siap')
    },
    onError: () => toast.error('Document QA gagal'),
  })

  async function handleDownload(id: number, name: string) {
    try {
      const res = await documentsApi.downloadUrl(id)
      window.open(res.data.download_url, '_blank')
    } catch {
      toast.error('Gagal mendapatkan link download')
    }
  }

  async function handleViewAnalysis(id: number) {
    try {
      const res = await documentsApi.analysis(id)
      setAiModal({ id, data: res.data.analysis })
    } catch {
      toast.error('Analisis AI belum tersedia')
    }
  }

  async function handleOpenSync(document: Document) {
    setSyncLoadingId(document.id)
    try {
      const response = document.latest_sync_id
        ? await documentsApi.getSync(document.latest_sync_id)
        : await documentsApi.previewSync(document.id)
      setSyncSession(response.data)
      qc.invalidateQueries({ queryKey: ['documents'] })
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || 'Preview sinkronisasi gagal dibuat')
    } finally {
      setSyncLoadingId(null)
    }
  }

  function handleFileSubmit(e: React.FormEvent) {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file || !projectId) { toast.error('Pilih proyek dan file'); return }
    const fd = new FormData()
    fd.append('project_id', String(projectId))
    fd.append('doc_type', docType)
    fd.append('analyze_with_ai', String(analyzeAI))
    fd.append('file', file)
    uploadMutation.mutate(fd)
  }

  function handleQaSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!projectId || !qaQuestion.trim()) {
      toast.error('Pilih proyek dan tulis pertanyaan')
      return
    }
    qaMutation.mutate({ projectId: Number(projectId), question: qaQuestion.trim() })
  }

  const filtered = documents.filter(d =>
    d.file_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">{isStaff ? 'Dokumen Kerja' : 'Pusat Dokumen'}</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {isStaff ? 'Dokumen proyek yang tersedia untuk pekerjaan dan divisi Anda' : 'Upload, kelola & analisis dokumen proyek'}
          </p>
        </div>
        <button onClick={() => setShowUpload(true)} className="btn-primary">
          <Plus size={16} /> Upload Dokumen
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex gap-3 flex-wrap">
        <select value={projectId} onChange={e => setProjectId(e.target.value ? Number(e.target.value) : '')} className="input w-56 text-sm">
          <option value="">Pilih Proyek...</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.project_name}</option>)}
        </select>
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari dokumen..." className="input pl-9 text-sm" />
        </div>
      </div>

      {projectId && isManagement && (
        <div className="card p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Bot size={17} className="text-violet-500" />
                <h2 className="font-semibold text-slate-900">Document QA dengan sumber</h2>
              </div>
              <p className="mt-1 text-sm text-slate-500">Tanyakan isi dokumen proyek. Jawaban dibatasi pada project yang dipilih dan menampilkan sumber.</p>
            </div>
          </div>
          <form onSubmit={handleQaSubmit} className="mt-4 grid grid-cols-1 md:grid-cols-[1fr_150px] gap-3">
            <input
              className="input text-sm"
              value={qaQuestion}
              onChange={(e) => setQaQuestion(e.target.value)}
              placeholder="Contoh: Apa risiko utama dari kontrak dan dokumen tender proyek ini?"
            />
            <button className="btn-primary justify-center" disabled={qaMutation.isPending}>
              {qaMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
              Tanya AI
            </button>
          </form>
          {qaResult && (
            <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
              <div className="rounded-xl border border-violet-100 bg-violet-50/60 p-4">
                <p className="text-sm leading-6 text-slate-700 whitespace-pre-line">{qaResult.answer}</p>
                <p className="mt-3 text-xs text-violet-700">{qaResult.governance}</p>
              </div>
              <div className="rounded-xl border border-slate-100 p-4">
                <h3 className="text-sm font-semibold text-slate-900">Sumber</h3>
                <div className="mt-3 space-y-3">
                  {qaResult.sources.map((source) => (
                    <div key={source.document_id} className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-700">#{source.document_id} {source.file_name}</p>
                      <p className="mt-1 text-[11px] text-slate-500">Tipe {source.file_type} - v{source.version}</p>
                      <p className="mt-2 line-clamp-3 text-xs text-slate-500">{source.snippet}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Upload modal */}
      {showUpload && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md animate-in">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">{isStaff ? 'Upload Dokumen Kerja' : 'Upload Dokumen'}</h2>
              <button onClick={() => setShowUpload(false)} className="btn-ghost p-1.5"><X size={16} /></button>
            </div>
            <form onSubmit={handleFileSubmit} className="p-5 space-y-4">
              <div>
                <label className="label">Proyek *</label>
                <select required value={projectId} onChange={e => setProjectId(Number(e.target.value))} className="input">
                  <option value="">Pilih proyek...</option>
                  {projects.map(p => <option key={p.id} value={p.id}>{p.project_name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Tipe Dokumen</label>
                <select value={docType} onChange={e => setDocType(e.target.value)} className="input">
                  {DOC_TYPES.filter((type) => isManagement || !['tender', 'contract'].includes(type.value)).map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="label">File *</label>
                <div
                  className="border-2 border-dashed border-slate-200 rounded-xl p-6 text-center cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload size={24} className="mx-auto text-slate-400 mb-2" />
                  <p className="text-sm text-slate-500">
                    {fileRef.current?.files?.[0]?.name ?? 'Klik untuk memilih file'}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">PDF, DOCX, XLSX, JPG, PNG • Maks 50MB</p>
                  <input ref={fileRef} type="file" className="hidden"
                    accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.webp" />
                </div>
              </div>
              {isManagement && <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={analyzeAI} onChange={e => setAnalyzeAI(e.target.checked)}
                  className="rounded border-slate-300 text-brand-500" />
                <span className="text-sm text-slate-600">Analisis otomatis dengan AI <span className="text-violet-500">(PDF/DOCX)</span></span>
              </label>}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowUpload(false)} className="btn-secondary flex-1 justify-center">Batal</button>
                <button type="submit" disabled={uploadMutation.isPending} className="btn-primary flex-1 justify-center">
                  {uploadMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                  Upload
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AI Analysis Modal */}
      {aiModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-y-auto animate-in">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white">
              <div className="flex items-center gap-2">
                <Bot size={18} className="text-violet-500" />
                <h2 className="font-semibold text-slate-900">Hasil Analisis AI</h2>
              </div>
              <button onClick={() => setAiModal(null)} className="btn-ghost p-1.5"><X size={16} /></button>
            </div>
            <div className="p-5 space-y-4">
              {Object.entries(aiModal.data).map(([k, v]) => (
                <div key={k}>
                  <p className="label">{k.replace(/_/g, ' ')}</p>
                  <div className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3">
                    {Array.isArray(v) ? (
                      <ul className="space-y-1">
                        {(v as string[]).map((item, i) => <li key={i} className="flex gap-2"><span className="text-slate-400">•</span>{String(item)}</li>)}
                      </ul>
                    ) : (
                      <p>{String(v ?? '—')}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Documents list */}
      {!projectId ? (
        <div className="card p-16 text-center">
          <FolderOpen size={40} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">{isStaff ? 'Pilih proyek untuk melihat dokumen kerja' : 'Pilih proyek untuk melihat dokumen'}</p>
        </div>
      ) : isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
      ) : filtered.length === 0 ? (
        <div className="card p-16 text-center">
          <FolderOpen size={40} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">Belum ada dokumen untuk proyek ini</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
          <table className="min-w-[920px] w-full">
            <thead>
              <tr className="border-b border-slate-100">
                {[
                  'Dokumen',
                  'Tipe',
                  'Ukuran',
                  'Versi',
                  ...(isManagement ? ['AI', 'Sinkronisasi'] : []),
                  'Tanggal',
                  'Aksi',
                ].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map(d => (
                <tr key={d.id} className="hover:bg-slate-50 transition">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      {FILE_ICON[d.file_type as string] ?? <File size={20} className="text-slate-400" />}
                      <div>
                        <div className="text-sm font-medium text-slate-800">{d.file_name}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="badge-gray badge">{DOC_TYPES.find(t => t.value === d.file_type)?.label ?? d.file_type}</span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-500">{formatBytes(d.file_size)}</td>
                  <td className="px-5 py-3.5">
                    <span className="badge-brand badge">v{d.version}</span>
                  </td>
                  {isManagement && <td className="px-5 py-3.5">
                    {d.has_ai ? (
                      <button onClick={() => handleViewAnalysis(d.id)} className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 font-medium">
                        <Eye size={12} /> Lihat
                      </button>
                    ) : <span className="text-xs text-slate-300">-</span>}
                  </td>}
                  {isManagement && <td className="px-5 py-3.5">
                    {d.sync_status ? (
                      <span className={d.sync_status === 'applied' ? 'badge-success' : d.sync_status === 'rejected' || d.sync_status === 'failed' ? 'badge-danger' : d.sync_status === 'approved' ? 'badge-info' : 'badge-warning'}>
                        {SYNC_LABEL[d.sync_status]}
                      </span>
                    ) : <span className="text-xs text-slate-300">Belum ada</span>}
                  </td>}
                  <td className="px-5 py-3.5 text-xs text-slate-500">{formatDate(d.created_at)}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      {isManagement && d.has_ai && ['tender', 'contract'].includes(d.file_type) && (
                        <button
                          onClick={() => handleOpenSync(d)}
                          disabled={syncLoadingId === d.id}
                          className="p-1.5 rounded-lg hover:bg-cyan-50 text-slate-500 hover:text-cyan-700 transition"
                          title="Preview sinkronisasi dokumen"
                        >
                          {syncLoadingId === d.id ? <Loader2 size={14} className="animate-spin" /> : <GitCompareArrows size={14} />}
                        </button>
                      )}
                      <button onClick={() => handleDownload(d.id, d.file_name)} className="p-1.5 rounded-lg hover:bg-brand-50 text-slate-500 hover:text-brand-600 transition" title="Download">
                        <Download size={14} />
                      </button>
                      {(isManagement || d.uploaded_by === user?.id) && <button onClick={() => deleteMutation.mutate(d.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-500 hover:text-red-500 transition" title="Hapus">
                        <Trash2 size={14} />
                      </button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}
      {syncSession && <DocumentSyncPanel session={syncSession} onClose={() => setSyncSession(null)} onUpdated={setSyncSession} />}
    </div>
  )
}
