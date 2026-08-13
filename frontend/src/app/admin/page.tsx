'use client'

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  Bot, CheckCircle2, FolderKanban, MessageSquare, ShieldCheck, Users, Workflow,
} from 'lucide-react'

import ProjectDatasetImport from '@/components/ProjectDatasetImport'
import { projectsApi, settingsApi, systemApi, usersApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { FeatureFlag, Project, User } from '@/types'

type SystemStatus = {
  services?: Record<string, boolean | object | string>
}

export default function ProjectAdminPage() {
  const user = useAuthStore((state) => state.user)
  const isProjectAdmin = user?.role === 'admin'
  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['project-admin-project'],
    queryFn: async () => (await projectsApi.list()).data,
    enabled: isProjectAdmin,
    retry: false,
  })
  const project = projects[0]
  const { data: users = [] } = useQuery<User[]>({
    queryKey: ['users', project?.id],
    queryFn: async () => (await usersApi.list(project?.id)).data,
    enabled: isProjectAdmin && Boolean(project?.id),
    retry: false,
  })
  const { data: features = [] } = useQuery<FeatureFlag[]>({
    queryKey: ['feature-flags', project?.id],
    queryFn: async () => (await settingsApi.features(project?.id)).data,
    enabled: isProjectAdmin && Boolean(project?.id),
    retry: false,
  })
  const { data: status } = useQuery<SystemStatus>({
    queryKey: ['system-status'],
    queryFn: async () => (await systemApi.status()).data,
    enabled: isProjectAdmin,
    refetchInterval: 60_000,
    retry: false,
  })

  if (!isProjectAdmin) {
    return (
      <div className="card p-8 text-center">
        <ShieldCheck size={26} className="mx-auto text-rose-600" />
        <h1 className="mt-4 text-xl font-bold text-slate-950">Halaman Admin Proyek</h1>
        <p className="mt-2 text-sm text-slate-500">Akun ini tidak memiliki role Admin Proyek.</p>
      </div>
    )
  }

  const serviceReady = (key: string) => status?.services?.[key] === true
  const activeFeatures = features.filter((feature) => feature.enabled).length

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Administrasi satu proyek</p>
          <h1 className="page-title">Admin Proyek</h1>
          <p className="mt-1 text-sm text-slate-500">
            {project ? `Mengelola ${project.project_name}` : 'Akun belum terhubung ke proyek.'}
          </p>
        </div>
        {project && <span className="badge badge-info">1 admin · 1 proyek</span>}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-5">
          <FolderKanban size={19} className="text-cyan-600" />
          <div className="mt-4 text-2xl font-bold text-slate-950">{projects.length}</div>
          <p className="mt-1 text-sm text-slate-500">Proyek yang diwakili</p>
        </div>
        <div className="card p-5">
          <Users size={19} className="text-violet-600" />
          <div className="mt-4 text-2xl font-bold text-slate-950">{users.length}</div>
          <p className="mt-1 text-sm text-slate-500">Akun dalam proyek</p>
        </div>
        <div className="card p-5">
          <CheckCircle2 size={19} className="text-emerald-600" />
          <div className="mt-4 text-2xl font-bold text-slate-950">{activeFeatures}/{features.length}</div>
          <p className="mt-1 text-sm text-slate-500">Fitur diaktifkan Owner</p>
        </div>
      </div>

      <div className="card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="font-semibold text-slate-950">Pengguna dan akun proyek</h2>
            <p className="mt-1 text-sm text-slate-500">Pembuatan akun manual maupun upload CSV dilakukan pada satu tempat, khusus anggota proyek ini.</p>
          </div>
          <Link href="/users" className="btn-primary justify-center"><Users size={16} /> Kelola Pengguna</Link>
        </div>
      </div>

      <ProjectDatasetImport />

      <div className="grid gap-4 lg:grid-cols-3">
        {[
          { key: 'ai', label: 'AI proyek', description: 'Analisis dokumen dan pembagian task.', href: '/ai-chat', icon: Bot },
          { key: 'telegram', label: 'Telegram', description: 'Update progres staf dari bot proyek.', href: '/telegram', icon: MessageSquare },
          { key: 'database', label: 'Database', description: 'Data proyek tersimpan pada database online.', href: '/projects', icon: Workflow },
        ].map((item) => (
          <Link key={item.key} href={item.href} className="card p-5 transition hover:-translate-y-0.5 hover:border-cyan-200">
            <div className="flex items-center justify-between">
              <item.icon size={19} className="text-cyan-600" />
              <span className={serviceReady(item.key) ? 'badge badge-success' : 'badge badge-warning'}>
                {serviceReady(item.key) ? 'Aktif' : 'Perlu konfigurasi'}
              </span>
            </div>
            <h2 className="mt-4 font-semibold text-slate-950">{item.label}</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">{item.description}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
