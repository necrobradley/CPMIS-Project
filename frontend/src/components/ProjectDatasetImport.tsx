'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bot, Building2, CheckCircle2, Database, FileArchive, Loader2, Upload, UserCheck } from 'lucide-react'
import toast from 'react-hot-toast'

import { documentsApi, systemApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'
import { extractProjectSourceDocuments, prepareProjectDatasetArchive } from '@/lib/project-dataset-import'

type ProjectDatasetImportResult = {
  project_id: number
  project_name: string
  project_code?: string
  field_user_email: string
  telegram_linked: boolean
  tasks_upserted: number
  nodes_upserted: number
  relationships_upserted: number
  rules_upserted: number
  reasoning_examples_upserted: number
  generated_accounts?: Array<{
    email: string
    role: string
    project_role: string
    project_role_label?: string
    can_be_task_pic?: boolean
    created: boolean
    temporary_password?: string | null
  }>
  assignment_counts?: Record<string, number>
  role_assignment_counts?: Record<string, number>
  project_roles_created?: number
  ai_role_tasks?: number
  demo_features_seeded?: boolean
  demo_reports?: number
  demo_documents?: number
  demo_approvals?: number
  demo_communications?: number
  demo_notifications?: number
  demo_vendors?: number
  source_documents_total?: number
  source_documents_uploaded?: number
  source_documents_analyzed?: number
  source_documents_skipped?: number
  source_documents_failed?: number
}

const MAX_SOURCE_BYTES = 25 * 1024 * 1024

function formatBytes(value: number) {
  return `${(value / 1024 / 1024).toFixed(2)} MB`
}

function documentTypeFor(filename: string) {
  const value = filename.toLowerCase()
  if (value.includes('tender')) return 'tender'
  if (value.includes('contract')) return 'contract'
  if (value.includes('report') || value.includes('laporan')) return 'daily_report'
  if (value.includes('drawing') || value.includes('gambar')) return 'drawing'
  return 'other'
}

function supportsAiAnalysis(file: File) {
  return file.type === 'application/pdf'
    || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    || file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

export default function ProjectDatasetImport() {
  const queryClient = useQueryClient()
  const [dataset, setDataset] = useState<File | null>(null)
  const [telegramId, setTelegramId] = useState('')
  const [result, setResult] = useState<ProjectDatasetImportResult | null>(null)
  const [processSourceDocuments, setProcessSourceDocuments] = useState(true)
  const [sourceProgress, setSourceProgress] = useState({ current: '', completed: 0, total: 0 })

  const importDataset = useMutation({
    mutationFn: async () => {
      if (!dataset) throw new Error('Pilih paket data proyek berformat ZIP terlebih dahulu.')
      if (dataset.size > MAX_SOURCE_BYTES) {
        throw new Error(`Ukuran ZIP maksimal ${formatBytes(MAX_SOURCE_BYTES)}.`)
      }

      const preparedArchive = await prepareProjectDatasetArchive(dataset)
      const formData = new FormData()
      formData.append('dataset', preparedArchive)
      if (telegramId.trim()) formData.append('telegram_id', telegramId.trim())
      const response = await systemApi.importProjectDataset(formData)
      if (!processSourceDocuments) return response

      const sourceDocuments = await extractProjectSourceDocuments(dataset)
      setSourceProgress({ current: '', completed: 0, total: sourceDocuments.length })
      const existingResponse = await documentsApi.list(response.data.project_id)
      const existingNames = new Set<string>(
        existingResponse.data.map((document: { file_name: string }) => document.file_name.toLowerCase()),
      )
      let uploaded = 0
      let analyzed = 0
      let skipped = 0
      let failed = 0

      for (const sourceDocument of sourceDocuments) {
        if (existingNames.has(sourceDocument.name.toLowerCase())) {
          skipped += 1
          setSourceProgress((current) => ({
            current: sourceDocument.name,
            completed: current.completed + 1,
            total: current.total,
          }))
          continue
        }
        setSourceProgress((current) => ({ ...current, current: sourceDocument.name }))
        const documentForm = new FormData()
        documentForm.append('project_id', String(response.data.project_id))
        documentForm.append('doc_type', documentTypeFor(sourceDocument.name))
        documentForm.append('analyze_with_ai', String(supportsAiAnalysis(sourceDocument)))
        documentForm.append('file', sourceDocument)
        try {
          const uploadResponse = await documentsApi.upload(documentForm)
          uploaded += 1
          if (uploadResponse.data.ai_analysis_complete) analyzed += 1
          existingNames.add(sourceDocument.name.toLowerCase())
        } catch {
          failed += 1
        }
        setSourceProgress((current) => ({
          current: sourceDocument.name,
          completed: current.completed + 1,
          total: current.total,
        }))
      }

      response.data = {
        ...response.data,
        source_documents_total: sourceDocuments.length,
        source_documents_uploaded: uploaded,
        source_documents_analyzed: analyzed,
        source_documents_skipped: skipped,
        source_documents_failed: failed,
      }
      return response
    },
    onMutate: () => setSourceProgress({ current: '', completed: 0, total: 0 }),
    onSuccess: (response) => {
      setResult(response.data)
      for (const queryKey of ['projects', 'tasks', 'users', 'controls', 'digital-twin']) {
        queryClient.invalidateQueries({ queryKey: [queryKey] })
      }
      toast.success('Paket data proyek berhasil dimasukkan ke sistem')
    },
    onError: (error: unknown) => {
      toast.error(apiErrorMessage(error, 'Import paket data proyek gagal'))
    },
  })

  function submit(event: React.FormEvent) {
    event.preventDefault()
    setResult(null)
    importDataset.mutate()
  }

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-100 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-700">
            <Database size={20} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Import paket data proyek</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              Dataset terstruktur membuat proyek, akun, task/WBS, Digital Twin, rule, dan reasoning.
              Dokumen sumber di dalam ZIP dapat diunggah dan dianalisis AI sebagai tahap terpisah yang terlihat.
            </p>
            <a
              href="/demo/CPMIS_Demo_Pusat_Inovasi_2026.zip"
              download
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-violet-700 hover:text-violet-900"
            >
              <FileArchive size={13} /> Download paket dummy semua fitur
            </a>
          </div>
        </div>
      </div>

      <form onSubmit={submit} className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(240px,0.55fr)_auto] lg:items-end">
        <div className="block">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Paket data proyek</span>
          <input
            type="file"
            accept=".zip,application/zip"
            className="input"
            onChange={(event) => {
              setDataset(event.target.files?.[0] || null)
              setResult(null)
            }}
          />
          <label className="mt-3 flex cursor-pointer items-start gap-2 rounded-lg border border-violet-100 bg-violet-50/60 p-3">
            <input
              type="checkbox"
              checked={processSourceDocuments}
              onChange={(event) => setProcessSourceDocuments(event.target.checked)}
              className="mt-0.5 rounded border-slate-300 text-violet-600"
            />
            <span>
              <span className="block text-xs font-semibold text-violet-900">Proses dokumen sumber dengan AI</span>
              <span className="mt-0.5 block text-[11px] leading-4 text-violet-700">PDF/DOCX dianalisis Nemotron; XLSX disimpan sebagai dokumen proyek.</span>
            </span>
          </label>
        </div>
        <label className="block">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Telegram ID staf (opsional)</span>
          <input
            value={telegramId}
            onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, ''))}
            inputMode="numeric"
            className="input"
            placeholder="Contoh: 770910605"
          />
        </label>
        <button disabled={importDataset.isPending || !dataset} className="btn-primary justify-center lg:min-w-44">
          {importDataset.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
          {importDataset.isPending
            ? sourceProgress.total > 0
              ? `Dokumen ${sourceProgress.completed}/${sourceProgress.total}`
              : 'Mengimpor struktur...'
            : 'Import proyek'}
        </button>
      </form>

      <div className="px-5 pb-5">
        <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600 sm:flex-row sm:items-center sm:justify-between">
          <span>
            Dataset terstruktur diproses lebih dulu. Dokumen sumber dikirim satu per satu agar progres AI terlihat dan kegagalan satu file tidak membatalkan proyek.
          </span>
          {dataset && (
            <span className="inline-flex shrink-0 items-center gap-1.5 font-semibold text-slate-700">
              <FileArchive size={13} /> {dataset.name} · {formatBytes(dataset.size)}
            </span>
          )}
        </div>

        {importDataset.isPending && sourceProgress.total > 0 && (
          <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-violet-900">
              <Bot size={16} className="animate-pulse" /> Nemotron memproses dokumen sumber
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-violet-100">
              <div
                className="h-full rounded-full bg-violet-600 transition-all"
                style={{ width: `${Math.round((sourceProgress.completed / sourceProgress.total) * 100)}%` }}
              />
            </div>
            <p className="mt-2 truncate text-xs text-violet-700">
              {sourceProgress.current || 'Menyiapkan dokumen'} · {sourceProgress.completed}/{sourceProgress.total}
            </p>
          </div>
        )}

        {result && (
          <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50/60 p-5">
            <div className="flex items-start gap-3">
              <CheckCircle2 size={22} className="mt-0.5 shrink-0 text-emerald-600" />
              <div className="min-w-0">
                <h3 className="font-semibold text-emerald-900">Import berhasil</h3>
                <p className="mt-1 text-sm text-emerald-800">{result.project_name}</p>
                <p className="mt-1 text-xs text-emerald-700">
                  Project ID #{result.project_id}{result.project_code ? ` · ${result.project_code}` : ''}
                </p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
              {[
                { label: 'Task/WBS', value: result.tasks_upserted, icon: Building2 },
                { label: 'Node', value: result.nodes_upserted, icon: Database },
                { label: 'Relasi', value: result.relationships_upserted, icon: Database },
                { label: 'Rule', value: result.rules_upserted, icon: CheckCircle2 },
                { label: 'Reasoning', value: result.reasoning_examples_upserted, icon: UserCheck },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-white p-3 shadow-sm">
                  <item.icon size={14} className="text-emerald-600" />
                  <div className="mt-2 text-xl font-bold text-slate-900">{item.value.toLocaleString('id-ID')}</div>
                  <div className="text-xs text-slate-500">{item.label}</div>
                </div>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="badge-info">Akun staf utama: {result.field_user_email}</span>
              <span className="badge-info">{result.project_roles_created || 0} role proyek</span>
              <span className="badge-success">{result.ai_role_tasks || 0} task demo AI ber-PIC</span>
              <span className={result.telegram_linked ? 'badge-success' : 'badge-warning'}>
                Telegram {result.telegram_linked ? 'terhubung' : 'belum diisi'}
              </span>
            </div>
            {result.demo_features_seeded && (
              <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 p-3 text-xs text-violet-800">
                Data presentasi aktif: {result.demo_documents || 0} dokumen, {result.demo_reports || 0} laporan, {result.demo_approvals || 0} approval, {result.demo_communications || 0} komunikasi, {result.demo_notifications || 0} notifikasi, dan {result.demo_vendors || 0} vendor.
              </div>
            )}
            {typeof result.source_documents_total === 'number' && (
              <div className="mt-4 rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-xs leading-5 text-cyan-900">
                Dokumen sumber: {result.source_documents_uploaded || 0} tersimpan, {result.source_documents_analyzed || 0} dianalisis Nemotron,
                {' '}{result.source_documents_skipped || 0} dilewati karena sudah ada, dan {result.source_documents_failed || 0} gagal.
              </div>
            )}
            {result.generated_accounts && result.generated_accounts.length > 0 && (
              <div className="mt-4 overflow-x-auto rounded-lg border border-emerald-200 bg-white">
                <table className="w-full min-w-[700px] text-left text-xs">
                  <thead className="bg-emerald-50 text-emerald-900"><tr>{['Akun', 'Role aplikasi', 'Role proyek', 'Task', 'Password awal'].map((item) => <th key={item} className="px-3 py-2">{item}</th>)}</tr></thead>
                  <tbody className="divide-y divide-emerald-100">
                    {result.generated_accounts.map((account) => (
                      <tr key={account.email}>
                        <td className="px-3 py-2 font-medium text-slate-800">{account.email}</td>
                        <td className="px-3 py-2 text-slate-600">{account.role}</td>
                        <td className="px-3 py-2 text-slate-600">{account.project_role_label || account.project_role}{account.can_be_task_pic === false ? ' (reviewer)' : ''}</td>
                        <td className="px-3 py-2 text-slate-600">{result.role_assignment_counts?.[account.project_role] || 0}</td>
                        <td className="px-3 py-2 font-mono text-slate-700">{account.temporary_password || 'Tidak diubah'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
