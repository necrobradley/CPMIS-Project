'use client'
import { useState } from 'react'
import { researchApi } from '@/lib/api'
import { BarChart3, Database, Download, FileJson, ShieldCheck, Table } from 'lucide-react'
import toast from 'react-hot-toast'

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function ResearchPage() {
  const [anonymize, setAnonymize] = useState(true)
  const [loading, setLoading] = useState<'json' | 'csv' | null>(null)

  async function exportData(format: 'json' | 'csv') {
    setLoading(format)
    try {
      const res = await researchApi.export(format, anonymize)
      if (format === 'csv') {
        downloadBlob(res.data, 'digicom-pmis-research-export.csv')
      } else {
        const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
        downloadBlob(blob, 'digicom-pmis-research-export.json')
      }
      toast.success(`Export ${format.toUpperCase()} berhasil`)
    } catch {
      toast.error('Export gagal')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Thesis evidence</p>
          <h1 className="page-title">Research export</h1>
          <p className="text-sm text-slate-500 mt-0.5">Ekspor dataset pilot untuk UAT, expert validation, usability testing, dan analisis tesis.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Tasks & issues', icon: BarChart3, className: 'bg-cyan-50 text-cyan-700' },
          { label: 'Reports & AI risks', icon: Database, className: 'bg-amber-50 text-amber-700' },
          { label: 'Approvals & audit', icon: ShieldCheck, className: 'bg-emerald-50 text-emerald-700' },
          { label: 'Documents & events', icon: Table, className: 'bg-violet-50 text-violet-700' },
        ].map((item) => (
          <div key={item.label} className="card p-5">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${item.className}`}>
              <item.icon size={18} />
            </div>
            <p className="mt-4 text-sm font-semibold text-slate-900">{item.label}</p>
            <p className="mt-1 text-xs text-slate-500">Included in export</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <div className="card p-6">
          <h2 className="font-semibold text-slate-900">Export package</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Paket data mencakup proyek, user, task, laporan harian, dokumen, approval, notifikasi, dan audit trail.
            Gunakan mode anonymize untuk menjaga privacy data pilot sebelum dibawa ke analisis penelitian.
          </p>
          <div className="mt-5 rounded-xl border border-slate-100 bg-slate-50 p-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={anonymize}
                onChange={(e) => setAnonymize(e.target.checked)}
                className="rounded border-slate-300 text-brand-500"
              />
              <span className="text-sm font-medium text-slate-700">Anonymize user identity</span>
            </label>
            <p className="mt-2 text-xs text-slate-500">Nama, email, nomor telepon, dan Telegram ID diganti menjadi ID anonim.</p>
          </div>
        </div>

        <div className="card p-6 space-y-3">
          <h2 className="font-semibold text-slate-900">Download</h2>
          <button onClick={() => exportData('json')} disabled={loading !== null} className="btn-primary w-full justify-center">
            {loading === 'json' ? <Download size={15} className="animate-pulse" /> : <FileJson size={15} />}
            Export JSON
          </button>
          <button onClick={() => exportData('csv')} disabled={loading !== null} className="btn-secondary w-full justify-center">
            {loading === 'csv' ? <Download size={15} className="animate-pulse" /> : <Table size={15} />}
            Export CSV
          </button>
        </div>
      </div>
    </div>
  )
}
