'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Building2, CheckCircle2, Database, FileArchive, Loader2, Upload, UserCheck } from 'lucide-react'
import toast from 'react-hot-toast'

import { systemApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'
import { prepareMnbcImportArchive } from '@/lib/mnbc-import'

type MnbcImportResult = {
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
}

const MAX_SOURCE_BYTES = 25 * 1024 * 1024

function formatBytes(value: number) {
  return `${(value / 1024 / 1024).toFixed(2)} MB`
}

export default function MnbcDatasetImport() {
  const queryClient = useQueryClient()
  const [dataset, setDataset] = useState<File | null>(null)
  const [telegramId, setTelegramId] = useState('')
  const [result, setResult] = useState<MnbcImportResult | null>(null)

  const importDataset = useMutation({
    mutationFn: async () => {
      if (!dataset) throw new Error('Pilih files.zip MNBC terlebih dahulu.')
      if (dataset.size > MAX_SOURCE_BYTES) {
        throw new Error(`Ukuran ZIP maksimal ${formatBytes(MAX_SOURCE_BYTES)}.`)
      }

      const preparedArchive = await prepareMnbcImportArchive(dataset)
      const formData = new FormData()
      formData.append('dataset', preparedArchive)
      if (telegramId.trim()) formData.append('telegram_id', telegramId.trim())
      return systemApi.importMnbc(formData)
    },
    onSuccess: (response) => {
      setResult(response.data)
      for (const queryKey of ['projects', 'tasks', 'users', 'controls', 'digital-twin']) {
        queryClient.invalidateQueries({ queryKey: [queryKey] })
      }
      toast.success('Dataset MNBC berhasil dimasukkan ke sistem')
    },
    onError: (error: unknown) => {
      toast.error(apiErrorMessage(error, 'Import dataset MNBC gagal'))
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
            <h2 className="text-base font-semibold text-slate-900">Import dataset proyek MNBC</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              Pilih <strong>files.zip</strong> yang diberikan. Sistem akan membuat atau memperbarui satu proyek MNBC,
              task/WBS, Digital Twin, rule, dan data reasoning tanpa menggandakan proyek.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={submit} className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(240px,0.55fr)_auto] lg:items-end">
        <label className="block">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">Dataset MNBC</span>
          <input
            type="file"
            accept=".zip,application/zip"
            className="input"
            onChange={(event) => {
              setDataset(event.target.files?.[0] || null)
              setResult(null)
            }}
          />
        </label>
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
          {importDataset.isPending ? 'Sedang mengimpor...' : 'Import MNBC'}
        </button>
      </form>

      <div className="px-5 pb-5">
        <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600 sm:flex-row sm:items-center sm:justify-between">
          <span>
            Browser hanya mengirim tiga berkas AI yang digunakan importer; Excel, DOCX, PDF, dan P6 di dalam ZIP tidak diunggah.
          </span>
          {dataset && (
            <span className="inline-flex shrink-0 items-center gap-1.5 font-semibold text-slate-700">
              <FileArchive size={13} /> {dataset.name} · {formatBytes(dataset.size)}
            </span>
          )}
        </div>

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
              <span className="badge-info">Staf: {result.field_user_email}</span>
              <span className={result.telegram_linked ? 'badge-success' : 'badge-warning'}>
                Telegram {result.telegram_linked ? 'terhubung' : 'belum diisi'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
