'use client'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Building2, CheckCircle2, Mail, MessageSquare, Phone, Search,
  Send, UserCheck, Users,
} from 'lucide-react'
import { projectsApi, usersApi } from '@/lib/api'
import { demoProjects, demoStakeholders, demoUsers } from '@/lib/demo-data'
import { Project, User } from '@/types'
import { ROLE_LABELS } from '@/lib/utils'

export default function StakeholdersPage() {
  const [search, setSearch] = useState('')
  const { data: projectData } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
    refetchInterval: 30_000,
  })
  const { data: userData } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: async () => (await usersApi.list()).data,
    refetchInterval: 30_000,
    retry: 1,
  })

  const projects = projectData?.length ? projectData : demoProjects
  const users = userData?.length ? userData : demoUsers
  const stakeholders = useMemo(() => (
    demoStakeholders.filter((stakeholder) => {
      const q = search.toLowerCase()
      return [stakeholder.name, stakeholder.type, stakeholder.project, stakeholder.contact]
        .some((value) => value.toLowerCase().includes(q))
    })
  ), [search])

  const connectedUsers = users.filter((user) => user.telegram_id).length
  const followUps = stakeholders.filter((stakeholder) => stakeholder.health !== 'Aktif').length

  return (
    <div className="space-y-7 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-cyan-600">
            <Users size={14} />
            Stakeholder command
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Stakeholder & communication hub</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Menggabungkan daftar stakeholder Kimi dengan user, proyek, Telegram, dan notifikasi CPMIS.
          </p>
        </div>
        <div className="relative w-full xl:w-80">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="input pl-9"
            placeholder="Cari stakeholder..."
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <Building2 size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{projects.length}</div>
          <p className="mt-1 text-sm text-slate-500">Project aktif/terdaftar</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
            <UserCheck size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{connectedUsers}/{users.length}</div>
          <p className="mt-1 text-sm text-slate-500">User terhubung Telegram</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-violet-700">
            <Users size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{stakeholders.length}</div>
          <p className="mt-1 text-sm text-slate-500">Stakeholder utama</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
            <MessageSquare size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{followUps}</div>
          <p className="mt-1 text-sm text-slate-500">Butuh follow-up</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Stakeholder list</h2>
            <span className="badge-info">{stakeholders.length} kontak</span>
          </div>
          <div className="space-y-3">
            {stakeholders.map((stakeholder) => (
              <div key={stakeholder.name} className="rounded-xl border border-slate-100 p-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100">
                      <Building2 size={18} className="text-slate-500" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-slate-900">{stakeholder.name}</h3>
                        <span className={stakeholder.health === 'Aktif' ? 'badge-success' : 'badge-warning'}>{stakeholder.health}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{stakeholder.type} - {stakeholder.project}</p>
                      <p className="mt-2 text-sm text-slate-600">{stakeholder.lastUpdate}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className="badge-gray"><Mail size={12} /> {stakeholder.contact}</span>
                    <span className="badge-info"><MessageSquare size={12} /> {stakeholder.telegram}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-6">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Internal roles</h2>
              <CheckCircle2 size={17} className="text-emerald-500" />
            </div>
            <div className="space-y-3">
              {users.slice(0, 5).map((user) => (
                <div key={user.id} className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                    {user.name.charAt(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-800">{user.name}</p>
                    <p className="text-xs text-slate-400">{ROLE_LABELS[user.role]}</p>
                  </div>
                  {user.telegram_id ? <span className="badge-success">TG</span> : <span className="badge-warning">No TG</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Quick broadcast</h2>
              <Send size={17} className="text-slate-300" />
            </div>
            <div className="space-y-3">
              <select className="input">
                <option>Management + owner</option>
                <option>Lapangan + subkontraktor</option>
                <option>Semua stakeholder</option>
              </select>
              <textarea className="input min-h-28 resize-none" defaultValue="Update: mohon konfirmasi status task critical hari ini sebelum pukul 17:00 WIB." />
              <div className="grid grid-cols-2 gap-2">
                <button className="btn-secondary justify-center"><Phone size={14} /> Draft call</button>
                <button className="btn-primary justify-center"><Send size={14} /> Kirim</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
