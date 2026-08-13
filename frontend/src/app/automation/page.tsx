'use client'
import type { ElementType } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, BellRing, Bot, CheckCircle2, Clock3, FileSearch,
  Radio, RefreshCcw, Server, Workflow,
} from 'lucide-react'
import { systemApi } from '@/lib/api'

type WorkflowStatus = {
  id: string
  name: string
  schedule: string
  status: string
}

type SystemStatus = {
  status?: string
  services?: Record<string, boolean>
  workflows?: WorkflowStatus[]
}

const fallbackWorkflows: WorkflowStatus[] = [
  { id: 'daily-report', name: 'Daily report AI summary', schedule: 'Realtime webhook', status: 'ready' },
  { id: 'tender-analysis', name: 'Tender analysis and task generation', schedule: 'On document upload', status: 'ready' },
  { id: 'deadline-alert', name: 'Deadline reminder', schedule: 'Daily 08:00 WIB', status: 'ready' },
  { id: 'weekly-summary', name: 'Weekly executive summary', schedule: 'Friday 17:00 WIB', status: 'ready' },
]

const workflowIcons: Record<string, ElementType> = {
  'daily-report': BellRing,
  'tender-analysis': FileSearch,
  'deadline-alert': Clock3,
  'weekly-summary': Bot,
}

export default function AutomationPage() {
  const { data, isError, isFetching, dataUpdatedAt } = useQuery<SystemStatus>({
    queryKey: ['system-status'],
    queryFn: async () => (await systemApi.status()).data,
    refetchInterval: 15_000,
    retry: 1,
  })

  const services = data?.services ?? {
    api: !isError,
    database: true,
    scheduler: true,
    telegram: false,
    n8n: true,
    ai: false,
  }
  const workflows = data?.workflows ?? fallbackWorkflows
  const onlineServices = Object.values(services).filter(Boolean).length
  const lastSync = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'menunggu'

  return (
    <div className="space-y-7 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-orange-600">
            <Workflow size={14} />
            Automation center
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Otomasi alur kerja terintegrasi</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Panel ini memantau API, scheduler, Telegram, AI, dan webhook n8n dari backend CPMIS.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={isError ? 'badge-warning' : 'badge-success'}>
            {isError ? 'Fallback mode' : 'Backend online'}
          </span>
          <span className="badge-info">
            <RefreshCcw size={12} className={isFetching ? 'animate-spin' : ''} />
            Sync {lastSync}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
            <Server size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{onlineServices}/{Object.keys(services).length}</div>
          <p className="mt-1 text-sm text-slate-500">Service online</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-orange-50 text-orange-700">
            <Workflow size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{workflows.length}</div>
          <p className="mt-1 text-sm text-slate-500">Alur kerja aktif dan siap mendukung proses operasional</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <Radio size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">15s</div>
          <p className="mt-1 text-sm text-slate-500">Refresh interval dashboard</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Workflow map</h2>
            <span className="badge-success">Ready</span>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {workflows.map((workflow) => {
              const Icon = workflowIcons[workflow.id] ?? Workflow
              return (
                <div key={workflow.id} className="rounded-xl border border-slate-100 p-4">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-50 text-orange-600">
                      <Icon size={18} />
                    </div>
                    <span className="badge-success">{workflow.status}</span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{workflow.name}</h3>
                  <p className="mt-1 text-xs text-slate-400">{workflow.schedule}</p>
                  <div className="mt-4 h-2 rounded-full bg-slate-100">
                    <div className="h-full w-full rounded-full bg-emerald-500" />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Service readiness</h2>
            <Activity size={17} className="text-slate-300" />
          </div>
          <div className="space-y-3">
            {Object.entries(services).map(([name, online]) => (
              <div key={name} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={15} className={online ? 'text-emerald-500' : 'text-amber-500'} />
                  <span className="text-sm font-medium capitalize text-slate-700">{name}</span>
                </div>
                <span className={online ? 'badge-success' : 'badge-warning'}>{online ? 'Online' : 'Setup'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
