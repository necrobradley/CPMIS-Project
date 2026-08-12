'use client'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { auditApi, projectsApi, usersApi } from '@/lib/api'
import { AuditLog, Project, User } from '@/types'
import { formatDateTime } from '@/lib/utils'
import { Activity, Database, FileClock, Search, ShieldCheck } from 'lucide-react'

const ACTION_CLASS: Record<string, string> = {
  'approval.created': 'bg-amber-50 text-amber-700',
  'approval.approved': 'bg-emerald-50 text-emerald-700',
  'approval.rejected': 'bg-rose-50 text-rose-700',
  'task.status_changed': 'bg-cyan-50 text-cyan-700',
  'document.qa': 'bg-violet-50 text-violet-700',
}

export default function AuditPage() {
  const [search, setSearch] = useState('')
  const { data: auditData } = useQuery<AuditLog[]>({
    queryKey: ['audit'],
    queryFn: async () => (await auditApi.list({ limit: 200 })).data,
  })
  const { data: projectData } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  const { data: userData } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: async () => (await usersApi.list()).data,
  })

  const auditLogs = auditData ?? []
  const projects = projectData ?? []
  const users = userData ?? []
  const projectMap = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p])), [projects])
  const userMap = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])

  const filtered = auditLogs.filter((log) => {
    const haystack = `${log.action} ${log.entity_type} ${log.summary || ''}`.toLowerCase()
    return haystack.includes(search.toLowerCase())
  })
  const uniqueActors = new Set(auditLogs.map((log) => log.actor_id).filter(Boolean)).size
  const communicationEvents = auditLogs.filter((log) => ['approval', 'document', 'daily_report', 'notification'].includes(log.entity_type)).length

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Governance</p>
          <h1 className="page-title">Audit trail</h1>
          <p className="text-sm text-slate-500 mt-0.5">Jejak aktivitas penting untuk transparansi komunikasi proyek dan bukti validasi tesis.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Total event', value: auditLogs.length, icon: Activity, className: 'bg-cyan-50 text-cyan-700' },
          { label: 'Aktor aktif', value: uniqueActors, icon: ShieldCheck, className: 'bg-emerald-50 text-emerald-700' },
          { label: 'Communication event', value: communicationEvents, icon: FileClock, className: 'bg-amber-50 text-amber-700' },
          { label: 'Entity tracked', value: new Set(auditLogs.map((log) => log.entity_type)).size, icon: Database, className: 'bg-violet-50 text-violet-700' },
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

      <div className="card p-4">
        <div className="relative max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari action, entity, atau ringkasan..." />
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100">
              {['Waktu', 'Action', 'Aktor', 'Proyek', 'Entity', 'Ringkasan'].map((h) => (
                <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {filtered.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50 transition">
                <td className="px-5 py-4 text-xs text-slate-500 whitespace-nowrap">{formatDateTime(log.created_at)}</td>
                <td className="px-5 py-4">
                  <span className={`${ACTION_CLASS[log.action] || 'bg-slate-100 text-slate-700'} badge`}>{log.action}</span>
                </td>
                <td className="px-5 py-4 text-sm text-slate-600">{log.actor_id ? userMap[log.actor_id]?.name || `User #${log.actor_id}` : 'System'}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{log.project_id ? projectMap[log.project_id]?.project_name || `Project #${log.project_id}` : '-'}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{log.entity_type}{log.entity_id ? ` #${log.entity_id}` : ''}</td>
                <td className="px-5 py-4 text-sm text-slate-700">{log.summary || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && <div className="p-10 text-center text-sm text-slate-400">Belum ada audit event.</div>}
      </div>
    </div>
  )
}
