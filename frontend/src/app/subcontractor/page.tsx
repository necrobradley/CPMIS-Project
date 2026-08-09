'use client'
import { useQuery } from '@tanstack/react-query'
import { tasksApi, reportsApi, projectsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Task, DailyReport, Project } from '@/types'
import {
  STATUS_LABELS, PRIORITY_LABELS, statusBadgeClass,
  priorityBadgeClass, formatDate, isOverdue, timeAgo
} from '@/lib/utils'
import { Building, CheckSquare, FileText, AlertTriangle, Calendar, Loader2, MessageCircle } from 'lucide-react'

export default function SubcontractorPage() {
  const user = useAuthStore(s => s.user)

  const { data: tasks = [], isLoading: tLoading } = useQuery<Task[]>({
    queryKey: ['my-tasks', user?.id],
    queryFn: async () => (await tasksApi.list({ assigned_to: user?.id })).data,
    enabled: !!user,
  })

  const { data: reports = [], isLoading: rLoading } = useQuery<DailyReport[]>({
    queryKey: ['my-reports', user?.id],
    queryFn: async () => (await reportsApi.list({ user_id: user?.id })).data,
    enabled: !!user,
  })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  const doneTasks    = tasks.filter(t => t.status === 'done').length
  const overdueTasks = tasks.filter(t => isOverdue(t.deadline) && t.status !== 'done').length
  const projectMap   = Object.fromEntries(projects.map(p => [p.id, p.project_name]))

  return (
    <div className="space-y-6 animate-in">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Building size={24} className="text-brand-500" /> Portal Subkontraktor
        </h1>
        <p className="text-sm text-slate-500 mt-1">Selamat datang, <strong>{user?.name}</strong> — kelola task dan laporan Anda di sini.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Task',    value: tasks.length,   icon: CheckSquare,   color: 'text-brand-500',   bg: 'bg-brand-50' },
          { label: 'Selesai',       value: doneTasks,      icon: CheckSquare,   color: 'text-emerald-500', bg: 'bg-emerald-50' },
          { label: 'Terlambat',     value: overdueTasks,   icon: AlertTriangle, color: 'text-red-500',     bg: 'bg-red-50' },
          { label: 'Total Laporan', value: reports.length, icon: FileText,      color: 'text-violet-500',  bg: 'bg-violet-50' },
        ].map(s => (
          <div key={s.label} className="card p-4">
            <div className={`w-9 h-9 ${s.bg} rounded-xl flex items-center justify-center mb-3`}>
              <s.icon size={18} className={s.color} />
            </div>
            <div className="text-2xl font-bold text-slate-900">{s.value}</div>
            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* My Tasks */}
        <div className="card p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Task Saya</h2>
          {tLoading ? (
            <div className="flex justify-center py-8"><Loader2 size={22} className="animate-spin text-brand-500" /></div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-10 text-slate-400 text-sm">Belum ada task yang ditugaskan</div>
          ) : (
            <div className="space-y-3">
              {tasks.slice(0, 8).map(t => (
                <div key={t.id} className="flex items-start gap-3 p-3 rounded-xl hover:bg-slate-50 transition">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-medium text-slate-800 truncate">{t.title}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={statusBadgeClass(t.status) + ' badge'}>{STATUS_LABELS[t.status]}</span>
                      <span className={priorityBadgeClass(t.priority) + ' badge'}>{PRIORITY_LABELS[t.priority]}</span>
                      {t.deadline && (
                        <span className={`flex items-center gap-1 text-xs ${isOverdue(t.deadline) && t.status !== 'done' ? 'text-red-500' : 'text-slate-400'}`}>
                          <Calendar size={10} /> {formatDate(t.deadline)}
                          {isOverdue(t.deadline) && t.status !== 'done' && <AlertTriangle size={10} />}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-sm font-semibold text-slate-700">{t.progress_percent}%</div>
                    <div className="w-16 h-1 bg-slate-100 rounded-full mt-1">
                      <div className="h-full bg-brand-400 rounded-full" style={{ width: `${t.progress_percent}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* My Reports */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-900">Laporan Saya</h2>
            <a href="/reports" className="text-xs text-brand-500 hover:text-brand-700 font-medium">+ Buat laporan →</a>
          </div>
          {rLoading ? (
            <div className="flex justify-center py-8"><Loader2 size={22} className="animate-spin text-brand-500" /></div>
          ) : reports.length === 0 ? (
            <div className="text-center py-10 text-slate-400 text-sm">Belum ada laporan yang dibuat</div>
          ) : (
            <div className="space-y-3">
              {reports.slice(0, 6).map(r => (
                <div key={r.id} className="p-3 rounded-xl hover:bg-slate-50 transition">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-xs font-medium text-brand-600">{projectMap[r.project_id] ?? `Proyek #${r.project_id}`}</span>
                    <span className="text-xs text-slate-400">{timeAgo(r.report_date)}</span>
                  </div>
                  <p className="text-sm text-slate-600 line-clamp-2">{r.report_text}</p>
                  {r.ai_summary && (
                    <p className="text-xs text-slate-400 italic mt-1 line-clamp-1">🤖 {r.ai_summary}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Telegram info */}
      <div className="card p-5 bg-gradient-to-r from-brand-50 to-violet-50 border-brand-200">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 bg-brand-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <MessageCircle size={20} className="text-brand-600" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-800 mb-1">Laporan via Telegram Bot</h3>
            <p className="text-sm text-slate-600 mb-3">
              Kirim laporan harian langsung dari lapangan menggunakan Telegram Bot AI CPMIS.
              Cukup ketik teks bebas — AI akan otomatis memproses dan menyimpan laporan Anda.
            </p>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-500">Telegram ID Anda:</span>
              {user?.telegram_id ? (
                <code className="bg-white px-2 py-0.5 rounded-lg text-brand-600 font-mono text-xs border border-brand-200">
                  {user.telegram_id}
                </code>
              ) : (
                <span className="text-amber-600 text-xs font-medium">⚠️ Belum terhubung — hubungi admin</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
