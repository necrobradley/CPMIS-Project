'use client'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  AlertTriangle, Bot, CheckCircle2, CheckSquare, Clock, FileText,
  FolderKanban, GitBranch, MessageSquare, Radio, ShieldCheck,
  Sparkles, TrendingUp, Users, Workflow, ClipboardCheck, Inbox,
  HardHat, ArrowRight,
} from 'lucide-react'
import {
  approvalsApi, auditApi, communicationsApi, controlsApi, notificationsApi, projectsApi, reportsApi, systemApi, tasksApi, usersApi,
} from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { formatDate, formatNumber, isOverdue, STATUS_LABELS, timeAgo } from '@/lib/utils'
import { Approval, AuditLog, CommunicationItem, DailyReport, Notification, Project, Task, User } from '@/types'

type SystemStatus = {
  services?: Record<string, boolean>
  workflows?: { id: string; name: string; schedule: string; status: string }[]
}

type MyWorkSummary = {
  role: string
  tasks: { id: number; title: string; status: string; deadline?: string; priority: string; progress_percent: number; gate: { can_start: boolean; start_blockers: unknown[] } }[]
  reports: { id: number; status: string }[]
  ncrs: { id: number; status: string }[]
}

const COLORS = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function useLiveQuery<T>(key: string, queryFn: () => Promise<T>) {
  return useQuery<T>({
    queryKey: [key],
    queryFn,
    refetchInterval: 15_000,
    retry: 1,
  })
}

function percent(value: number, total: number) {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const isManagement = user?.role === 'admin' || user?.role === 'director' || user?.role === 'manager'
  const taskHref = user?.role === 'staff' ? '/tasks/division' : '/tasks'
  const projectsQuery = useLiveQuery<Project[]>('projects', async () => (await projectsApi.list()).data)
  const tasksQuery = useLiveQuery<Task[]>('tasks', async () => (await tasksApi.list()).data)
  const reportsQuery = useLiveQuery<DailyReport[]>('reports', async () => (await reportsApi.list()).data)
  const usersQuery = useLiveQuery<User[]>('users', async () => (await usersApi.list()).data)
  const notificationsQuery = useLiveQuery<Notification[]>('notifications', async () => (await notificationsApi.list()).data)
  const approvalsQuery = useLiveQuery<Approval[]>('approvals', async () => (await approvalsApi.list()).data)
  const communicationsQuery = useLiveQuery<CommunicationItem[]>('communications', async () => (await communicationsApi.list()).data)
  const auditQuery = useLiveQuery<AuditLog[]>('recent-audit', async () => (await auditApi.recent(10)).data)
  const systemQuery = useLiveQuery<SystemStatus>('system-status', async () => (await systemApi.status()).data)
  const myWorkQuery = useLiveQuery<MyWorkSummary>('my-work', async () => (await controlsApi.myWork()).data)

  const projects = projectsQuery.data ?? []
  const tasks = tasksQuery.data ?? []
  const reports = reportsQuery.data ?? []
  const users = usersQuery.data ?? []
  const notifications = notificationsQuery.data ?? []
  const approvals = approvalsQuery.data ?? []
  const communications = communicationsQuery.data ?? []
  const auditLogs = auditQuery.data ?? []
  const systemStatus = systemQuery.data
  const myWork = myWorkQuery.data

  const hasDataError = [projectsQuery, tasksQuery, reportsQuery].some((q) => q.isError)

  const activeProjects = projects.filter((p) => p.status === 'active').length
  const doneTasks = tasks.filter((t) => t.status === 'done').length
  const blockedTasks = tasks.filter((t) => t.status === 'blocked').length
  const overdueTasks = tasks.filter((t) => isOverdue(t.deadline) && t.status !== 'done')
  const criticalTasks = tasks.filter((t) => t.priority === 'critical' && t.status !== 'done')
  const aiReports = reports.filter((r) => r.ai_summary || r.ai_risks)
  const telegramUsers = users.filter((u) => Boolean(u.telegram_id)).length
  const avgProgress = Math.round(projects.reduce((sum, p) => sum + p.progress_percent, 0) / Math.max(projects.length, 1))
  const healthScore = projects.length || tasks.length
    ? Math.max(0, Math.min(98, avgProgress + doneTasks * 3 - overdueTasks.length * 9 - blockedTasks * 7))
    : 0
  const unreadNotifications = notifications.filter((n) => !n.is_read).length
  const pendingApprovals = approvals.filter((a) => a.status === 'pending').length
  const openCommunications = communications.filter((item) => ['open', 'in_review'].includes(item.status))
  const overdueCommunications = openCommunications.filter((item) => isOverdue(item.due_date))

  const taskStatusData = ['todo', 'in_progress', 'review', 'done', 'blocked'].map((status) => ({
    name: STATUS_LABELS[status],
    value: tasks.filter((t) => t.status === status).length,
  })).filter((item) => item.value > 0)

  const projectBarData = projects.slice(0, 6).map((project) => ({
    name: project.project_name.length > 18 ? `${project.project_name.slice(0, 18)}...` : project.project_name,
    progress: project.progress_percent,
  }))

  const riskItems = [
    ...overdueTasks.slice(0, 3).map((task) => ({
      title: task.title,
      meta: `Deadline ${formatDate(task.deadline)}`,
      level: task.priority === 'critical' ? 'Critical' : 'High',
      href: '/tasks',
    })),
    ...reports.filter((report) => report.ai_risks).slice(0, 2).map((report) => ({
      title: report.ai_risks ?? 'Risiko dari laporan harian',
      meta: `Laporan ${timeAgo(report.report_date)}`,
      level: 'AI',
      href: '/reports',
    })),
  ].slice(0, 5)

  const statCards = [
    {
      label: 'Project health',
      value: `${healthScore}%`,
      sub: `${activeProjects} proyek aktif`,
      icon: ShieldCheck,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      href: '/projects',
    },
    {
      label: 'Task selesai',
      value: `${doneTasks}/${tasks.length}`,
      sub: `${percent(doneTasks, tasks.length)}% completion`,
      icon: CheckSquare,
      color: 'text-sky-600',
      bg: 'bg-sky-50',
      href: taskHref,
    },
    {
      label: 'Risiko aktif',
      value: overdueTasks.length + blockedTasks,
      sub: `${criticalTasks.length} critical task`,
      icon: AlertTriangle,
      color: 'text-rose-600',
      bg: 'bg-rose-50',
      href: '/risk',
      managementOnly: true,
    },
    {
      label: 'AI insight',
      value: aiReports.length,
      sub: `${reports.length} laporan dianalisis`,
      icon: Bot,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
      href: '/reports',
    },
    {
      label: 'Comms open',
      value: openCommunications.length,
      sub: `${overdueCommunications.length} overdue item`,
      icon: Inbox,
      color: 'text-cyan-600',
      bg: 'bg-cyan-50',
      href: '/communications',
    },
    {
      label: 'Pending approval',
      value: pendingApprovals,
      sub: `${auditLogs.length} recent audit event`,
      icon: ClipboardCheck,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
      href: '/approvals',
    },
  ].filter((stat) => !stat.managementOnly || isManagement)

  const services = systemStatus?.services ?? {
    api: !systemQuery.isError,
    database: true,
    scheduler: true,
    telegram: telegramUsers > 0,
    n8n: true,
    ai: aiReports.length > 0,
  }

  const workflows = systemStatus?.workflows ?? [
    { id: 'daily-report', name: 'Daily report AI summary', schedule: 'Realtime webhook', status: 'ready' },
    { id: 'tender-analysis', name: 'Tender analysis and task generation', schedule: 'On document upload', status: 'ready' },
    { id: 'deadline-alert', name: 'Deadline reminder', schedule: 'Daily 08:00 WIB', status: 'ready' },
    { id: 'approval-routing', name: 'Approval routing and escalation', schedule: 'On approval request', status: 'ready' },
    { id: 'weekly-summary', name: 'Weekly executive summary', schedule: 'Friday 17:00 WIB', status: 'ready' },
  ]

  return (
    <div className="space-y-7 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-brand-600">
            <Radio size={14} />
            Realtime command center
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
            Selamat datang, {user?.name?.split(' ')[0] ?? 'Project Team'}
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Rencanix menyatukan pengendalian proyek, kolaborasi lintas peran, pelaporan lapangan,
            dan analitik AI dalam satu ruang kerja yang terhubung secara real time.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {hasDataError && (
            <span className="badge-warning">Sebagian data API gagal dimuat</span>
          )}
          <span className="badge-success">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Live refresh 15s
          </span>
          {isManagement && <Link href="/automation" className="btn-secondary">
            <Workflow size={15} />
            Workflow status
          </Link>}
        </div>
      </div>

      {myWork && (
        <section className="border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700"><HardHat size={19} /></div>
              <div><h2 className="font-bold text-slate-900">Prioritas Kerja Hari Ini</h2><p className="text-xs font-medium uppercase text-slate-400">{myWork.role}</p></div>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge-info">{myWork.tasks.length} task</span>
              <span className="badge-warning">{myWork.reports.length} report queue</span>
              <span className="badge-danger">{myWork.ncrs.length} NCR</span>
              {isManagement ? (
                <Link href="/controls" className="btn-ghost px-2 py-1 text-xs">Buka controls <ArrowRight size={13} /></Link>
              ) : (
                <Link href={taskHref} className="btn-ghost px-2 py-1 text-xs">Lihat tugas <ArrowRight size={13} /></Link>
              )}
            </div>
          </div>
          <div className="grid divide-y divide-slate-100 md:grid-cols-2 md:divide-x md:divide-y-0 xl:grid-cols-4">
            {myWork.tasks.slice(0, 4).map((task) => <Link key={task.id} href={`/tasks/${task.id}`} className="flex min-w-0 items-center gap-3 px-5 py-4 hover:bg-slate-50"><span className={`h-2.5 w-2.5 shrink-0 rounded-full ${task.gate.can_start ? 'bg-emerald-500' : 'bg-rose-500'}`} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-800">{task.title}</p><p className="mt-0.5 text-xs text-slate-500">{task.progress_percent}% | {task.gate.start_blockers.length} blocker</p></div></Link>)}
            {!myWork.tasks.length && <p className="px-5 py-6 text-sm text-slate-500">Tidak ada pekerjaan aktif.</p>}
          </div>
        </section>
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-6">
        {statCards.map((stat) => (
          <Link key={stat.label} href={stat.href} className="card card-hover p-5">
            <div className="mb-4 flex items-start justify-between">
              <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${stat.bg}`}>
                <stat.icon size={21} className={stat.color} />
              </div>
              <TrendingUp size={15} className="text-slate-300" />
            </div>
            <div className="text-3xl font-bold text-slate-950">{stat.value}</div>
            <div className="mt-1 text-sm text-slate-500">{stat.label}</div>
            <div className="mt-0.5 text-xs text-slate-400">{stat.sub}</div>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-900">Progress proyek</h2>
              <p className="mt-0.5 text-xs text-slate-400">Ringkasan progres seluruh proyek berdasarkan data operasional terbaru</p>
            </div>
            <FolderKanban size={18} className="text-slate-300" />
          </div>
          <ResponsiveContainer width="100%" height={245}>
            <BarChart data={projectBarData} barSize={30}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} domain={[0, 100]} unit="%" />
              <Tooltip
                contentStyle={{ borderRadius: 10, border: 'none', boxShadow: '0 4px 16px rgb(0 0 0 / 0.1)', fontSize: 12 }}
                formatter={(value: number) => [`${value}%`, 'Progress']}
              />
              <Bar dataKey="progress" fill="#0ea5e9" radius={[7, 7, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-900">Distribusi task</h2>
              <p className="mt-0.5 text-xs text-slate-400">Komposisi tugas berdasarkan status pelaksanaan saat ini</p>
            </div>
            <CheckCircle2 size={18} className="text-slate-300" />
          </div>
          <ResponsiveContainer width="100%" height={170}>
            <PieChart>
              <Pie data={taskStatusData} cx="50%" cy="50%" innerRadius={50} outerRadius={76} paddingAngle={3} dataKey="value">
                {taskStatusData.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 10, border: 'none', fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-3 space-y-2">
            {taskStatusData.map((item, index) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: COLORS[index % COLORS.length] }} />
                  <span className="text-slate-600">{item.name}</span>
                </div>
                <span className="font-semibold text-slate-800">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900">
              <AlertTriangle size={16} className="text-rose-500" />
              Risk intelligence
            </h2>
            {isManagement && <Link href="/risk" className="text-xs font-medium text-brand-600 hover:text-brand-700">Buka</Link>}
          </div>
          <div className="space-y-3">
            {riskItems.length ? riskItems.map((item, index) => (
              <Link key={`${item.title}-${index}`} href={item.href} className="block rounded-xl border border-slate-100 bg-slate-50 p-3 transition hover:bg-white">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-rose-600">{item.level}</span>
                  <span className="text-[11px] text-slate-400">{item.meta}</span>
                </div>
                <p className="line-clamp-2 text-sm font-medium text-slate-800">{item.title}</p>
              </Link>
            )) : (
              <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-sm text-emerald-700">
                Tidak ada risiko terbuka.
              </div>
            )}
          </div>
        </div>

        <div className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900">
              <Workflow size={16} className="text-orange-500" />
              Automation health
            </h2>
            {isManagement && <Link href="/automation" className="text-xs font-medium text-brand-600 hover:text-brand-700">Detail</Link>}
          </div>
          <div className="space-y-2">
            {Object.entries(services).map(([name, online]) => (
              <div key={name} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
                <span className="text-sm font-medium capitalize text-slate-700">{name}</span>
                <span className={online ? 'badge-success' : 'badge-warning'}>
                  {online ? 'Online' : 'Needs setup'}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl border border-slate-100 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-400">Integrasi operasional</div>
            <div className="text-2xl font-bold text-slate-950">{formatNumber(workflows.length)}</div>
          </div>
        </div>

        <div className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900">
              <MessageSquare size={16} className="text-cyan-500" />
              Komunikasi lapangan
            </h2>
            <Link href="/telegram" className="text-xs font-medium text-brand-600 hover:text-brand-700">Telegram</Link>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-cyan-50 p-4">
              <div className="text-2xl font-bold text-cyan-700">{telegramUsers}/{users.length}</div>
              <p className="mt-1 text-xs text-cyan-700/70">User terhubung Telegram</p>
            </div>
            <div className="rounded-xl bg-amber-50 p-4">
              <div className="text-2xl font-bold text-amber-700">{unreadNotifications}</div>
              <p className="mt-1 text-xs text-amber-700/70">Notifikasi belum dibaca</p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {notifications.slice(0, 3).map((notification) => (
              <div key={notification.id} className="rounded-xl border border-slate-100 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-slate-800">{notification.title}</p>
                  {notification.sent_to_telegram && <span className="badge-info">TG</span>}
                </div>
                <p className="mt-1 line-clamp-1 text-xs text-slate-400">{notification.message}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">AI insight terbaru</h2>
            <Link href="/reports" className="text-xs font-medium text-brand-600 hover:text-brand-700">Lihat laporan</Link>
          </div>
          <div className="space-y-3">
            {reports.slice(0, 4).map((report) => (
              <div key={report.id} className="rounded-xl bg-violet-50 p-4">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-violet-700">
                  <Sparkles size={13} />
                  Laporan #{report.id} - {timeAgo(report.report_date)}
                </div>
                <p className="line-clamp-2 text-sm text-slate-700">{report.ai_summary || report.report_text}</p>
                {report.ai_risks && (
                  <p className="mt-2 line-clamp-1 text-xs text-amber-700">Risk: {report.ai_risks}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Stakeholder watchlist</h2>
            <Link href="/stakeholders" className="text-xs font-medium text-brand-600 hover:text-brand-700">Kelola</Link>
          </div>
          <div className="space-y-3">
            {users.slice(0, 4).map((stakeholder) => (
              <div key={stakeholder.id} className="flex items-start gap-3 rounded-xl border border-slate-100 p-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
                  <Users size={17} className="text-slate-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-semibold text-slate-800">{stakeholder.name}</p>
                    <span className={stakeholder.is_active ? 'badge-success' : 'badge-warning'}>{stakeholder.is_active ? 'Aktif' : 'Nonaktif'}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-400">{stakeholder.role} - {stakeholder.email}</p>
                  <p className="mt-1 line-clamp-1 text-xs text-slate-500">{stakeholder.telegram_id ? 'Telegram terhubung' : 'Telegram belum terhubung'}</p>
                </div>
              </div>
            ))}
            {!users.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-400">Belum ada pengguna/stakeholder.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
