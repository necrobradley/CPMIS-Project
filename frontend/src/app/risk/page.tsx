'use client'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, ArrowUpRight, Bot, CalendarClock, CheckCircle2,
  ClipboardCheck, ShieldAlert, ShieldCheck, Siren,
} from 'lucide-react'
import { projectsApi, reportsApi, tasksApi } from '@/lib/api'
import { demoProjects, demoReports, demoTasks } from '@/lib/demo-data'
import { DailyReport, Project, Task } from '@/types'
import { formatDate, isOverdue, PRIORITY_LABELS, priorityBadgeClass, STATUS_LABELS, statusBadgeClass, timeAgo } from '@/lib/utils'

function riskScore(task: Task) {
  let score = 0
  if (task.priority === 'critical') score += 45
  if (task.priority === 'high') score += 30
  if (task.status === 'blocked') score += 35
  if (isOverdue(task.deadline) && task.status !== 'done') score += 35
  if (task.progress_percent < 50 && task.status !== 'done') score += 10
  return Math.min(100, score)
}

function scoreLabel(score: number) {
  if (score >= 75) return 'Critical'
  if (score >= 50) return 'High'
  if (score >= 25) return 'Medium'
  return 'Low'
}

export default function RiskPage() {
  const { data: projectData } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
    refetchInterval: 15_000,
  })
  const { data: taskData } = useQuery<Task[]>({
    queryKey: ['tasks'],
    queryFn: async () => (await tasksApi.list()).data,
    refetchInterval: 15_000,
  })
  const { data: reportData } = useQuery<DailyReport[]>({
    queryKey: ['reports'],
    queryFn: async () => (await reportsApi.list()).data,
    refetchInterval: 15_000,
  })

  const projects = projectData?.length ? projectData : demoProjects
  const tasks = taskData?.length ? taskData : demoTasks
  const reports = reportData?.length ? reportData : demoReports
  const projectMap = Object.fromEntries(projects.map((project) => [project.id, project]))

  const scoredTasks = tasks
    .map((task) => ({ task, score: riskScore(task), label: scoreLabel(riskScore(task)) }))
    .filter((item) => item.score >= 25)
    .sort((a, b) => b.score - a.score)

  const aiRisks = reports.filter((report) => report.ai_risks)
  const blocked = tasks.filter((task) => task.status === 'blocked')
  const overdue = tasks.filter((task) => isOverdue(task.deadline) && task.status !== 'done')
  const healthyTasks = tasks.filter((task) => task.status === 'done' || riskScore(task) < 25)

  const cards = [
    { label: 'Critical queue', value: scoredTasks.filter((item) => item.label === 'Critical').length, icon: Siren, className: 'bg-rose-50 text-rose-700' },
    { label: 'Blocked task', value: blocked.length, icon: ShieldAlert, className: 'bg-orange-50 text-orange-700' },
    { label: 'Overdue', value: overdue.length, icon: CalendarClock, className: 'bg-amber-50 text-amber-700' },
    { label: 'Healthy items', value: healthyTasks.length, icon: ShieldCheck, className: 'bg-emerald-50 text-emerald-700' },
  ]

  return (
    <div className="space-y-7 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-rose-600">
            <AlertTriangle size={14} />
            Risk intelligence
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Early warning center</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Menggabungkan overdue task, status blocked, prioritas critical, dan risiko dari AI summary laporan harian.
          </p>
        </div>
        <Link href="/tasks" className="btn-primary">
          <ClipboardCheck size={16} />
          Buka Kanban
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="card p-5">
            <div className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${card.className}`}>
              <card.icon size={21} />
            </div>
            <div className="text-3xl font-bold text-slate-950">{card.value}</div>
            <p className="mt-1 text-sm text-slate-500">{card.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Prioritas mitigasi</h2>
            <span className="badge-info">Refresh 15s</span>
          </div>
          <div className="space-y-3">
            {scoredTasks.length ? scoredTasks.map(({ task, score, label }) => {
              const project = projectMap[task.project_id]
              return (
                <div key={task.id} className="rounded-xl border border-slate-100 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={score >= 75 ? 'badge-danger' : score >= 50 ? 'badge-warning' : 'badge-info'}>{label}</span>
                        <span className={priorityBadgeClass(task.priority)}>{PRIORITY_LABELS[task.priority]}</span>
                        <span className={statusBadgeClass(task.status)}>{STATUS_LABELS[task.status]}</span>
                      </div>
                      <h3 className="mt-2 text-sm font-semibold text-slate-900">{task.title}</h3>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-500">{task.description || 'Tidak ada deskripsi task.'}</p>
                      <p className="mt-2 text-xs text-slate-400">
                        {project?.project_name ?? `Project #${task.project_id}`} - Deadline {formatDate(task.deadline)}
                      </p>
                    </div>
                    <div className="w-full lg:w-48">
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="font-medium text-slate-500">Risk score</span>
                        <span className="font-bold text-slate-900">{score}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-rose-500" style={{ width: `${score}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              )
            }) : (
              <div className="rounded-xl bg-emerald-50 p-6 text-center text-emerald-700">
                <CheckCircle2 size={28} className="mx-auto mb-2" />
                Semua item utama dalam kondisi aman.
              </div>
            )}
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">AI risk feed</h2>
            <Bot size={17} className="text-violet-500" />
          </div>
          <div className="space-y-3">
            {aiRisks.map((report) => (
              <Link key={report.id} href="/reports" className="block rounded-xl bg-violet-50 p-4 transition hover:bg-violet-100/70">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-violet-700">Laporan #{report.id}</span>
                  <span className="text-[11px] text-slate-400">{timeAgo(report.report_date)}</span>
                </div>
                <p className="line-clamp-3 text-sm text-slate-700">{report.ai_risks}</p>
                <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-violet-700">
                  Detail laporan <ArrowUpRight size={12} />
                </span>
              </Link>
            ))}
            {!aiRisks.length && <p className="text-sm text-slate-400">Belum ada risiko dari AI.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
