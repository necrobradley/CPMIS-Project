'use client'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { projectsApi, settingsApi, systemApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'
import { useAuthStore } from '@/lib/store'
import {
  CommercialPlan, CommercialPlanKey, CommercialReadiness, FeatureFlag, Project,
} from '@/types'
import { cn, formatDateTime } from '@/lib/utils'
import {
  Activity, AlertTriangle, CheckCircle2, Loader2, LockKeyhole,
  PackageCheck, Rocket, Search, ShieldCheck, SlidersHorizontal, ToggleLeft, ToggleRight, UserCog,
  Trash2, X,
} from 'lucide-react'

const CATEGORY_LABEL: Record<string, string> = {
  admin: 'Admin',
  advanced: 'Advanced',
  communication: 'Communication',
  core: 'Core',
  document: 'Document',
  execution: 'Execution',
  governance: 'Governance',
  integration: 'Integration',
  management: 'Management',
  project: 'Project',
}

const PROJECT_STATUS_LABEL: Record<Project['status'], string> = {
  planning: 'Perencanaan',
  active: 'Sedang berjalan',
  on_hold: 'Ditunda',
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

export default function OwnerConsolePage() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [projectPlanChoices, setProjectPlanChoices] = useState<Record<number, CommercialPlanKey>>({})
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [resetOpen, setResetOpen] = useState(false)
  const [resetEmail, setResetEmail] = useState('')
  const [resetPassword, setResetPassword] = useState('')
  const [resetConfirmation, setResetConfirmation] = useState('')
  const isOwner = user?.role === 'owner'

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['owner-projects'],
    queryFn: async () => (await projectsApi.list()).data,
    enabled: isOwner,
    retry: false,
  })
  const runningProjects = useMemo(
    () => projects.filter((project) => project.status === 'active'),
    [projects],
  )
  const otherProjects = useMemo(
    () => projects.filter((project) => project.status !== 'active'),
    [projects],
  )
  const selectedProject = projects.find((project) => project.id === selectedProjectId)
    || runningProjects[0]
    || projects[0]

  const { data: featureFlags = [], isLoading, isError } = useQuery<FeatureFlag[]>({
    queryKey: ['project-feature-flags', selectedProject?.id],
    queryFn: async () => (await settingsApi.projectFeatures(selectedProject!.id)).data,
    enabled: isOwner && Boolean(selectedProject?.id),
    retry: false,
  })
  const { data: commercialPlans = [] } = useQuery<CommercialPlan[]>({
    queryKey: ['commercial-plans'],
    queryFn: async () => (await settingsApi.commercialPlans()).data,
    enabled: isOwner,
    retry: false,
  })
  const { data: commercialReadiness } = useQuery<CommercialReadiness>({
    queryKey: ['commercial-readiness'],
    queryFn: async () => (await settingsApi.commercialReadiness()).data,
    enabled: isOwner,
    retry: false,
  })
  const updateFeature = useMutation({
    mutationFn: ({ featureKey, enabled }: { featureKey: string; enabled: boolean }) =>
      settingsApi.updateProjectFeature(selectedProject!.id, featureKey, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-feature-flags', selectedProject?.id] })
      toast.success('Fitur proyek diperbarui')
    },
    onError: () => toast.error('Gagal mengubah fitur'),
  })
  const applyProjectPlan = useMutation({
    mutationFn: ({ projectId, planKey }: { projectId: number; planKey: CommercialPlanKey }) =>
      settingsApi.applyProjectPlan(projectId, planKey),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['owner-projects'] })
      queryClient.invalidateQueries({ queryKey: ['project-feature-flags', selectedProject?.id] })
      toast.success(`${response.data.plan_name} diterapkan pada proyek`)
    },
    onError: (error: unknown) => toast.error(apiErrorMessage(error, 'Gagal menerapkan paket proyek')),
  })
  const resetOperationalData = useMutation({
    mutationFn: () => systemApi.resetOperationalData({
      owner_email: resetEmail.trim(),
      password: resetPassword,
      confirmation: resetConfirmation.trim(),
    }),
    onSuccess: (response) => {
      queryClient.invalidateQueries()
      setResetOpen(false)
      setResetEmail('')
      setResetPassword('')
      setResetConfirmation('')
      toast.success(response.data.message || 'Data operasional berhasil dikosongkan')
    },
    onError: (error: unknown) => toast.error(apiErrorMessage(error, 'Reset data operasional gagal')),
  })

  const categories = useMemo(
    () => ['all', ...Array.from(new Set(featureFlags.map((flag) => flag.category))).sort()],
    [featureFlags],
  )
  const filteredFlags = useMemo(() => {
    const term = search.trim().toLowerCase()
    return featureFlags.filter((flag) => {
      if (category !== 'all' && flag.category !== category) return false
      if (!term) return true
      return [flag.label, flag.feature_key, flag.description, flag.category]
        .some((value) => value?.toLowerCase().includes(term))
    })
  }, [category, featureFlags, search])

  const activeCount = featureFlags.filter((flag) => flag.enabled).length
  const disabledCount = featureFlags.length - activeCount
  const coreCount = featureFlags.filter((flag) => flag.is_core).length
  const selectedProjectPlanKey = selectedProject
    ? projectPlanChoices[selectedProject.id] || selectedProject.plan_key || 'professional'
    : 'professional'

  const formatCurrency = (value?: number) => (
    typeof value === 'number'
      ? new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(value)
      : 'Custom'
  )
  const readinessStyle = {
    done: 'bg-emerald-50 text-emerald-700',
    partial: 'bg-amber-50 text-amber-700',
    todo: 'bg-slate-100 text-slate-600',
    risk: 'bg-rose-50 text-rose-700',
  } as const

  if (!isOwner) {
    return (
      <div className="space-y-6 animate-in">
        <div className="page-header">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-rose-600">Restricted</p>
            <h1 className="page-title">Admin Owner</h1>
            <p className="text-sm text-slate-500 mt-0.5">Halaman ini hanya tersedia untuk pemilik platform.</p>
          </div>
        </div>
        <div className="card p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
            <LockKeyhole size={22} />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-slate-900">Akses admin diperlukan</h2>
          <p className="mt-2 text-sm text-slate-500">Direktur, manager, staff, dan subkontraktor tidak bisa mengubah struktur menu perusahaan.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Platform governance</p>
          <h1 className="page-title">Admin Owner</h1>
          <p className="text-sm text-slate-500 mt-0.5">Kelola layanan platform dan tentukan fitur yang tersedia untuk setiap proyek.</p>
        </div>
      </div>

      <div className="card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
              <UserCog size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Satu Owner, satu Admin untuk setiap proyek</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Owner mengatur paket dan pilihan fitur. Setiap Admin Proyek hanya mengelola satu proyek beserta pengguna di dalamnya.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-emerald-800">
            <Activity size={17} />
            <div>
              <div className="text-lg font-bold leading-none">{runningProjects.length}</div>
              <div className="mt-1 text-xs font-medium">proyek sedang berjalan</div>
            </div>
          </div>
        </div>
      </div>

      {!selectedProject && (
        <div className="card p-6 text-sm text-slate-500">Belum ada proyek yang dapat dikonfigurasi.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Fitur aktif', value: activeCount, icon: CheckCircle2, className: 'bg-emerald-50 text-emerald-700' },
          { label: 'Fitur nonaktif', value: disabledCount, icon: ToggleLeft, className: 'bg-slate-100 text-slate-700' },
          { label: 'Fitur inti', value: coreCount, icon: LockKeyhole, className: 'bg-amber-50 text-amber-700' },
          { label: 'Kategori', value: Math.max(categories.length - 1, 0), icon: SlidersHorizontal, className: 'bg-cyan-50 text-cyan-700' },
        ].map((item) => (
          <div key={item.label} className="card p-5">
            <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', item.className)}>
              <item.icon size={18} />
            </div>
            <div className="mt-4 text-3xl font-bold text-slate-950">{item.value}</div>
            <p className="mt-1 text-sm text-slate-500">{item.label}</p>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Paket layanan per proyek</p>
          <h2 className="text-xl font-bold text-slate-950">Terapkan paket pada proyek yang dipilih</h2>
          <p className="mt-1 text-sm text-slate-500">Admin Owner memilih proyek aktif maupun proyek lain, lalu menerapkan Starter, Professional, atau Enterprise. Penerapan paket memperbarui entitlement proyek tersebut.</p>
        </div>

        <div className="card border-cyan-200 p-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(220px,0.45fr)_auto] lg:items-end">
            <label className="block">
              <span className="label">Proyek tujuan</span>
              <select className="input bg-white font-medium" value={selectedProject?.id || ''} onChange={(event) => setSelectedProjectId(Number(event.target.value))} disabled={projects.length === 0}>
                {runningProjects.length > 0 && <optgroup label="Sedang berjalan">{runningProjects.map((project) => <option key={project.id} value={project.id}>{project.project_name} · {project.progress_percent}%</option>)}</optgroup>}
                {otherProjects.length > 0 && <optgroup label="Proyek lainnya">{otherProjects.map((project) => <option key={project.id} value={project.id}>{project.project_name} · {PROJECT_STATUS_LABEL[project.status]}</option>)}</optgroup>}
              </select>
            </label>
            <label className="block">
              <span className="label">Paket proyek</span>
              <select className="input bg-white" value={selectedProjectPlanKey} disabled={!selectedProject} onChange={(event) => selectedProject && setProjectPlanChoices((current) => ({ ...current, [selectedProject.id]: event.target.value as CommercialPlanKey }))}>
                {commercialPlans.map((plan) => <option key={plan.plan_key} value={plan.plan_key}>{plan.name}</option>)}
              </select>
            </label>
            <button type="button" className="btn-primary justify-center" disabled={!selectedProject || applyProjectPlan.isPending} onClick={() => selectedProject && applyProjectPlan.mutate({ projectId: selectedProject.id, planKey: selectedProjectPlanKey })}>
              {applyProjectPlan.isPending ? <Loader2 size={16} className="animate-spin" /> : <PackageCheck size={16} />}
              Terapkan paket
            </button>
          </div>
          {selectedProject && <p className="mt-3 text-xs text-slate-500">Paket tersimpan saat ini: <span className="font-semibold text-slate-700">{commercialPlans.find((plan) => plan.plan_key === selectedProject.plan_key)?.name || 'Belum ditetapkan'}</span></p>}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="card p-5 xl:col-span-2">
            <div className="flex items-center gap-2"><Rocket size={18} className="text-cyan-600" /><h3 className="text-base font-semibold text-slate-900">Kesiapan layanan</h3></div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {(commercialReadiness?.checks || []).map((check) => <div key={check.key} className="rounded-lg border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><h4 className="text-sm font-semibold text-slate-900">{check.title}</h4><p className="mt-1 text-xs leading-5 text-slate-500">{check.detail}</p></div><span className={cn('rounded-full px-2.5 py-1 text-[11px] font-bold uppercase', readinessStyle[check.status])}>{check.status}</span></div><p className="mt-3 text-xs font-medium text-slate-600">{check.action}</p></div>)}
              {!commercialReadiness?.checks?.length && <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-400">Readiness belum dimuat.</div>}
            </div>
          </div>
          <div className="card p-5">
            <div className="flex items-center gap-2"><PackageCheck size={18} className="text-cyan-600" /><h3 className="text-base font-semibold text-slate-900">Paket produk</h3></div>
            <div className="mt-4 space-y-3">{commercialPlans.map((plan) => <div key={plan.plan_key} className={cn('rounded-lg border p-4', selectedProjectPlanKey === plan.plan_key ? 'border-cyan-300 bg-cyan-50/50' : 'border-slate-200')}><div className="flex items-center justify-between gap-3"><h4 className="text-sm font-semibold text-slate-900">{plan.name}</h4><span className="badge badge-gray">{plan.enabled_features.includes('all') ? 'Semua fitur' : `${plan.enabled_features.length} fitur`}</span></div><p className="mt-2 text-xs leading-5 text-slate-500">{plan.positioning}</p><p className="mt-3 text-sm font-bold text-slate-900">{formatCurrency(plan.monthly_base_price_min_idr)}{plan.monthly_base_price_max_idr ? ` - ${formatCurrency(plan.monthly_base_price_max_idr)}/bulan` : ''}</p></div>)}</div>
          </div>
        </div>
      </div>

      <div className="card border-cyan-200 bg-gradient-to-r from-white to-cyan-50/60 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Entitlement fitur proyek</p>
            <h2 className="mt-1 text-xl font-bold text-slate-950">Pilihan fitur · {selectedProject?.project_name || 'Belum ada proyek'}</h2>
            <p className="mt-1 text-sm text-slate-500">Perubahan hanya berlaku pada proyek yang dipilih dan seluruh anggota di dalamnya.</p>
            {selectedProject && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <span className={selectedProject.status === 'active' ? 'badge-success' : 'badge-gray'}>
                  {PROJECT_STATUS_LABEL[selectedProject.status]}
                </span>
                <span className="text-slate-500">Progress {selectedProject.progress_percent.toLocaleString('id-ID')}%</span>
              </div>
            )}
          </div>
          <label className="block w-full lg:w-[420px]">
            <span className="label">Pilih proyek yang dikelola</span>
            <select
              className="input bg-white font-medium"
              value={selectedProject?.id || ''}
              onChange={(event) => setSelectedProjectId(Number(event.target.value))}
              disabled={projects.length === 0}
            >
              {runningProjects.length > 0 && (
                <optgroup label="Sedang berjalan">
                  {runningProjects.map((project) => (
                    <option key={project.id} value={project.id}>{project.project_name} · {project.progress_percent}%</option>
                  ))}
                </optgroup>
              )}
              {otherProjects.length > 0 && (
                <optgroup label="Proyek lainnya">
                  {otherProjects.map((project) => (
                    <option key={project.id} value={project.id}>{project.project_name} · {PROJECT_STATUS_LABEL[project.status]}</option>
                  ))}
                </optgroup>
              )}
            </select>
          </label>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full lg:max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="input pl-9 text-sm"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cari fitur atau menu..."
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {categories.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setCategory(item)}
                className={cn(
                  'rounded-lg px-3 py-2 text-xs font-semibold transition',
                  category === item
                    ? 'bg-cyan-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                )}
              >
                {item === 'all' ? 'Semua' : CATEGORY_LABEL[item] || item}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-cyan-600" /></div>
      ) : isError ? (
        <div className="card p-8 text-center">
          <AlertTriangle size={24} className="mx-auto text-amber-500" />
          <p className="mt-3 text-sm text-slate-500">Pengaturan fitur belum bisa dimuat dari API.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {filteredFlags.map((flag) => {
            const isPending = updateFeature.isPending && updateFeature.variables?.featureKey === flag.feature_key
            return (
              <div key={flag.feature_key} className="card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-semibold text-slate-900">{flag.label}</h2>
                      <span className="badge badge-gray">{CATEGORY_LABEL[flag.category] || flag.category}</span>
                      {flag.is_core && <span className="badge badge-warning">Core</span>}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{flag.description || 'Tidak ada deskripsi.'}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                      <span>{flag.feature_key}</span>
                      <span>Update: {formatDateTime(flag.updated_at)}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={flag.is_core || isPending}
                    onClick={() => updateFeature.mutate({ featureKey: flag.feature_key, enabled: !flag.enabled })}
                    className={cn(
                      'flex h-10 min-w-[112px] items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition',
                      flag.enabled
                        ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                      (flag.is_core || isPending) && 'cursor-not-allowed opacity-60',
                    )}
                  >
                    {isPending ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : flag.enabled ? (
                      <ToggleRight size={18} />
                    ) : (
                      <ToggleLeft size={18} />
                    )}
                    {flag.enabled ? 'Aktif' : 'Nonaktif'}
                  </button>
                </div>
                {flag.is_core && (
                  <div className="mt-4 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                    <ShieldCheck size={13} />
                    Fitur inti dikunci agar akses dasar sistem tetap tersedia.
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {!isLoading && !isError && filteredFlags.length === 0 && (
        <div className="card p-8 text-center text-sm text-slate-400">Tidak ada fitur yang cocok dengan filter.</div>
      )}

      <section className="overflow-hidden rounded-xl border border-rose-200 bg-white shadow-card">
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-600"><Trash2 size={20} /></div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-rose-600">Zona pengelolaan data</p>
              <h2 className="mt-1 text-base font-semibold text-slate-900">Kosongkan data operasional</h2>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
                Menghapus seluruh proyek, divisi, tugas, laporan, dokumen, komunikasi, approval, notifikasi, dan audit operasional. Akun pengguna serta konfigurasi platform tetap dipertahankan.
              </p>
            </div>
          </div>
          <button type="button" onClick={() => setResetOpen(true)} className="btn-danger shrink-0 justify-center border border-rose-200">
            <Trash2 size={16} /> Reset data
          </button>
        </div>
      </section>

      {resetOpen && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm" role="presentation">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="reset-data-title">
            <div className="flex items-start justify-between border-b border-slate-100 p-5">
              <div className="flex gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-700"><AlertTriangle size={21} /></div>
                <div>
                  <h2 id="reset-data-title" className="font-bold text-slate-950">Konfirmasi reset data operasional</h2>
                  <p className="mt-1 text-sm leading-5 text-slate-500">Tindakan ini tidak dapat dibatalkan setelah diproses.</p>
                </div>
              </div>
              <button type="button" disabled={resetOperationalData.isPending} onClick={() => setResetOpen(false)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Tutup"><X size={18} /></button>
            </div>
            <div className="space-y-4 p-5">
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                Akun login, paket layanan, entitlement, dan pengaturan fitur tidak akan dihapus. Admin Proyek dapat mengimpor proyek baru setelah reset.
              </div>
              <div>
                <label className="label">Email owner aktif</label>
                <input type="email" className="input" value={resetEmail} onChange={(event) => setResetEmail(event.target.value)} placeholder={user?.email || 'owner@perusahaan.id'} autoComplete="username" />
              </div>
              <div>
                <label className="label">Password owner</label>
                <input type="password" className="input" value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} placeholder="Masukkan password akun aktif" autoComplete="current-password" />
              </div>
              <div>
                <label className="label">Ketik RESET DATA</label>
                <input className="input font-mono" value={resetConfirmation} onChange={(event) => setResetConfirmation(event.target.value)} placeholder="RESET DATA" />
              </div>
            </div>
            <div className="flex flex-col-reverse gap-2 border-t border-slate-100 p-5 sm:flex-row sm:justify-end">
              <button type="button" disabled={resetOperationalData.isPending} onClick={() => setResetOpen(false)} className="btn-secondary justify-center">Batal</button>
              <button
                type="button"
                disabled={resetOperationalData.isPending || resetEmail.trim().toLowerCase() !== user?.email?.toLowerCase() || !resetPassword || resetConfirmation.trim() !== 'RESET DATA'}
                onClick={() => resetOperationalData.mutate()}
                className="btn-danger justify-center bg-rose-600 text-white hover:bg-rose-700"
              >
                {resetOperationalData.isPending ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                {resetOperationalData.isPending ? 'Mengosongkan data...' : 'Ya, kosongkan data'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
