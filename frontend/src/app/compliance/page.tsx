'use client'
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { complianceApi, projectsApi } from '@/lib/api'
import { Project, ComplianceResult } from '@/types'
import { ShieldCheck, Loader2, AlertTriangle, CheckCircle, XCircle, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react'
import toast from 'react-hot-toast'

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444'
  const r = 44, c = 2 * Math.PI * r
  const dash = (score / 100) * c
  return (
    <div className="relative w-32 h-32">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${c}`} strokeLinecap="round" className="transition-all duration-700" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-slate-800">{score}</span>
        <span className="text-xs text-slate-400">/ 100</span>
      </div>
    </div>
  )
}

export default function CompliancePage() {
  const [projectId, setProjectId] = useState<number | ''>('')
  const [result, setResult] = useState<ComplianceResult | null>(null)
  const [expanded, setExpanded] = useState<string | null>('missing')

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  const checkMutation = useMutation({
    mutationFn: (id: number) => complianceApi.check(id),
    onSuccess: (res) => {
      setResult(res.data)
      toast.success('Compliance check selesai!')
    },
    onError: () => toast.error('Compliance check gagal'),
  })

  function handleCheck() {
    if (!projectId) { toast.error('Pilih proyek dulu'); return }
    checkMutation.mutate(Number(projectId))
  }

  const statusColor: Record<string, string> = {
    compliant:     'text-emerald-600',
    partial:       'text-amber-600',
    non_compliant: 'text-red-600',
    error:         'text-slate-500',
    no_contract:   'text-slate-500',
  }
  const statusLabel: Record<string, string> = {
    compliant:     'Patuh',
    partial:       'Sebagian Patuh',
    non_compliant: 'Tidak Patuh',
    error:         'Error',
    no_contract:   'Tidak Ada Kontrak',
  }

  const Section = ({ id, label, items, icon, color }: { id: string; label: string; items: string[]; icon: React.ReactNode; color: string }) => (
    <div className="card overflow-hidden">
      <button onClick={() => setExpanded(expanded === id ? null : id)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition">
        <div className="flex items-center gap-3">
          {icon}
          <span className="font-semibold text-slate-800">{label}</span>
          <span className={`badge ${color}`}>{items.length}</span>
        </div>
        {expanded === id ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>
      {expanded === id && items.length > 0 && (
        <div className="px-4 pb-4 space-y-2">
          {items.map((item, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-slate-600 bg-slate-50 rounded-lg px-3 py-2">
              <span className="text-slate-400 mt-0.5">•</span> {item}
            </div>
          ))}
        </div>
      )}
      {expanded === id && items.length === 0 && (
        <div className="px-4 pb-4 text-sm text-slate-400 italic">Tidak ada item</div>
      )}
    </div>
  )

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <ShieldCheck size={24} className="text-brand-500" /> Compliance AI
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Cek kepatuhan proyek terhadap kontrak & deliverables</p>
        </div>
      </div>

      {/* Selector */}
      <div className="card p-5 flex flex-col sm:flex-row gap-4 items-end">
        <div className="flex-1">
          <label className="label">Pilih Proyek</label>
          <select value={projectId} onChange={e => setProjectId(e.target.value ? Number(e.target.value) : '')} className="input">
            <option value="">Pilih proyek...</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.project_name}</option>)}
          </select>
        </div>
        <button onClick={handleCheck} disabled={checkMutation.isPending || !projectId} className="btn-primary px-6">
          {checkMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
          {checkMutation.isPending ? 'Menganalisis...' : 'Cek Compliance'}
        </button>
      </div>

      {checkMutation.isPending && (
        <div className="card p-12 flex flex-col items-center gap-4">
          <Loader2 size={36} className="animate-spin text-brand-500" />
          <p className="text-slate-500">AI sedang menganalisis kepatuhan proyek terhadap kontrak...</p>
          <p className="text-xs text-slate-400">Proses ini membutuhkan 10-30 detik</p>
        </div>
      )}

      {result && !checkMutation.isPending && (
        <div className="space-y-5 animate-in">
          {/* Score overview */}
          <div className="card p-6">
            <div className="flex flex-col sm:flex-row items-center gap-8">
              {result.compliance_score != null ? (
                <ScoreRing score={result.compliance_score} />
              ) : (
                <div className="w-32 h-32 flex items-center justify-center rounded-full bg-slate-100">
                  <AlertCircle size={36} className="text-slate-400" />
                </div>
              )}
              <div className="flex-1 text-center sm:text-left">
                <div className={`text-2xl font-bold mb-1 ${statusColor[result.status]}`}>
                  {statusLabel[result.status] ?? result.status}
                </div>
                <p className="text-slate-600 text-sm leading-relaxed mb-4">{result.summary}</p>
                <div className="flex flex-wrap gap-4 justify-center sm:justify-start">
                  {[
                    { label: 'Kontrak Diperiksa', value: result.contracts_checked },
                    { label: 'Total Task',         value: result.total_tasks },
                    { label: 'Item Selesai',       value: result.completed_items?.length ?? 0, color: 'text-emerald-600' },
                    { label: 'Belum Ada',          value: result.missing_deliverables?.length ?? 0, color: 'text-red-500' },
                  ].map(s => (
                    <div key={s.label} className="text-center">
                      <div className={`text-xl font-bold ${s.color ?? 'text-slate-700'}`}>{s.value}</div>
                      <div className="text-xs text-slate-400">{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Milestone status */}
          {result.milestone_status?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-slate-800 mb-4">Status Milestone</h3>
              <div className="space-y-2">
                {result.milestone_status.map((m, i) => {
                  const ms: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
                    completed: { label: 'Selesai', color: 'badge-success', icon: <CheckCircle size={12} /> },
                    on_track:  { label: 'On Track', color: 'badge-info', icon: <CheckCircle size={12} /> },
                    delayed:   { label: 'Terlambat', color: 'badge-danger', icon: <AlertTriangle size={12} /> },
                  }
                  const s = ms[m.status] ?? { label: m.status, color: 'badge-gray', icon: null }
                  return (
                    <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                      <span className="text-sm text-slate-700">{m.name}</span>
                      <span className={`badge ${s.color} flex items-center gap-1`}>{s.icon}{s.label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Sections */}
          <Section id="missing" label="Deliverables Belum Ada"
            items={result.missing_deliverables ?? []}
            icon={<XCircle size={18} className="text-red-500" />}
            color="badge-danger" />
          <Section id="risk" label="Item Berisiko"
            items={result.at_risk_items ?? []}
            icon={<AlertTriangle size={18} className="text-amber-500" />}
            color="badge-warning" />
          <Section id="done" label="Item Selesai"
            items={result.completed_items ?? []}
            icon={<CheckCircle size={18} className="text-emerald-500" />}
            color="badge-success" />

          {/* Recommendations */}
          {result.recommendations?.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
                <ShieldCheck size={16} className="text-brand-500" /> Rekomendasi AI
              </h3>
              <div className="space-y-2">
                {result.recommendations.map((r, i) => (
                  <div key={i} className="flex gap-3 text-sm text-slate-600 bg-brand-50 rounded-xl p-3">
                    <span className="text-brand-500 font-bold flex-shrink-0">{i + 1}.</span> {r}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
