'use client'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { settingsApi, usersApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import ProjectDatasetImport from '@/components/ProjectDatasetImport'
import {
  CommercialEntitlement, CommercialPlan, CommercialPlanKey, CommercialReadiness,
  CommercialTenant, CommercialUsage, FeatureFlag,
} from '@/types'
import { cn, formatDateTime } from '@/lib/utils'
import {
  Activity, AlertTriangle, Building2, CheckCircle2, FileSpreadsheet, Loader2, LockKeyhole,
  PackageCheck, Rocket, Search, ShieldCheck, SlidersHorizontal, ToggleLeft, ToggleRight, UserCog,
  Upload,
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

type ImportResult = {
  row: number
  email: string
  status: string
  message: string
  temporary_password?: string
  role?: string
}

export default function AdminConsolePage() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [newTenantName, setNewTenantName] = useState('')
  const [newTenantPlan, setNewTenantPlan] = useState<CommercialPlanKey>('professional')
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResults, setImportResults] = useState<ImportResult[]>([])
  const isOwnerAdmin = user?.role === 'admin'

  const { data: featureFlags = [], isLoading, isError } = useQuery<FeatureFlag[]>({
    queryKey: ['feature-flags'],
    queryFn: async () => (await settingsApi.features()).data,
    enabled: isOwnerAdmin,
    retry: false,
  })
  const { data: commercialPlans = [] } = useQuery<CommercialPlan[]>({
    queryKey: ['commercial-plans'],
    queryFn: async () => (await settingsApi.commercialPlans()).data,
    enabled: isOwnerAdmin,
    retry: false,
  })
  const { data: commercialReadiness } = useQuery<CommercialReadiness>({
    queryKey: ['commercial-readiness'],
    queryFn: async () => (await settingsApi.commercialReadiness()).data,
    enabled: isOwnerAdmin,
    retry: false,
  })
  const { data: commercialTenants = [] } = useQuery<CommercialTenant[]>({
    queryKey: ['commercial-tenants'],
    queryFn: async () => (await settingsApi.commercialTenants()).data,
    enabled: isOwnerAdmin,
    retry: false,
  })

  const selectedTenant = useMemo(() => (
    commercialTenants.find((tenant) => tenant.id === selectedTenantId) || commercialTenants[0]
  ), [commercialTenants, selectedTenantId])

  const { data: tenantEntitlements = [] } = useQuery<CommercialEntitlement[]>({
    queryKey: ['commercial-entitlements', selectedTenant?.id],
    queryFn: async () => (await settingsApi.tenantEntitlements(selectedTenant!.id)).data,
    enabled: isOwnerAdmin && Boolean(selectedTenant?.id),
    retry: false,
  })
  const { data: tenantUsage = [] } = useQuery<CommercialUsage[]>({
    queryKey: ['commercial-usage', selectedTenant?.id],
    queryFn: async () => (await settingsApi.tenantUsage(selectedTenant!.id)).data,
    enabled: isOwnerAdmin && Boolean(selectedTenant?.id),
    retry: false,
  })

  const updateFeature = useMutation({
    mutationFn: ({ featureKey, enabled }: { featureKey: string; enabled: boolean }) =>
      settingsApi.updateFeature(featureKey, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feature-flags'] })
      toast.success('Pengaturan fitur diperbarui')
    },
    onError: () => toast.error('Gagal mengubah fitur'),
  })
  const createTenant = useMutation({
    mutationFn: () => settingsApi.createCommercialTenant({
      name: newTenantName.trim(),
      plan_key: newTenantPlan,
      status: 'trial',
      onboarding_stage: 'discovery',
    }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['commercial-tenants'] })
      queryClient.invalidateQueries({ queryKey: ['commercial-readiness'] })
      setSelectedTenantId(response.data.id)
      setNewTenantName('')
      toast.success('Tenant pilot dibuat')
    },
    onError: () => toast.error('Gagal membuat tenant'),
  })
  const updateTenant = useMutation({
    mutationFn: ({ tenantId, data }: { tenantId: number; data: Record<string, unknown> }) =>
      settingsApi.updateCommercialTenant(tenantId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commercial-tenants'] })
      queryClient.invalidateQueries({ queryKey: ['commercial-usage'] })
      queryClient.invalidateQueries({ queryKey: ['commercial-entitlements'] })
      queryClient.invalidateQueries({ queryKey: ['commercial-readiness'] })
      toast.success('Tenant diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui tenant'),
  })
  const updateEntitlement = useMutation({
    mutationFn: ({ tenantId, featureKey, enabled }: { tenantId: number; featureKey: string; enabled: boolean }) =>
      settingsApi.updateTenantEntitlement(tenantId, featureKey, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commercial-entitlements', selectedTenant?.id] })
      queryClient.invalidateQueries({ queryKey: ['commercial-readiness'] })
      toast.success('Entitlement diperbarui')
    },
    onError: () => toast.error('Gagal mengubah entitlement'),
  })
  const importUsers = useMutation({
    mutationFn: () => {
      const formData = new FormData()
      if (importFile) formData.append('file', importFile)
      return usersApi.importCsv(formData)
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setImportResults(response.data.results || [])
      toast.success(`${response.data.created || 0} akun dibuat dari CSV`)
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Gagal import daftar pegawai'),
  })

  function submitImport(event: React.FormEvent) {
    event.preventDefault()
    if (!importFile) {
      toast.error('Pilih file CSV daftar pegawai')
      return
    }
    importUsers.mutate()
  }

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
  const selectedPlan = commercialPlans.find((plan) => plan.plan_key === selectedTenant?.plan_key)

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

  if (!isOwnerAdmin) {
    return (
      <div className="space-y-6 animate-in">
        <div className="page-header">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-rose-600">Restricted</p>
            <h1 className="page-title">Admin Console</h1>
            <p className="text-sm text-slate-500 mt-0.5">Hanya akun Admin Aplikasi yang dapat mengubah fitur menu.</p>
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
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">System governance</p>
          <h1 className="page-title">Admin Console</h1>
          <p className="text-sm text-slate-500 mt-0.5">Kontrol menu aktif, integritas komunikasi, dan akses fitur perusahaan.</p>
        </div>
      </div>

      <div className="card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
              <UserCog size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Admin Aplikasi berbeda dari Admin Proyek</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Admin Aplikasi mengelola sistem, menu, tenant, harga, dan akun. Admin Proyek adalah role proyek tersendiri untuk administrasi proyek di aplikasi, bukan Project Manager.
              </p>
            </div>
          </div>
          <Link href="/users" className="btn-primary justify-center">
            <UserCog size={16} /> Kelola admin proyek
          </Link>
        </div>
      </div>

      <ProjectDatasetImport />

      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
              <FileSpreadsheet size={20} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900">Upload daftar pegawai</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Buat akun massal dari CSV internal HR. Kolom minimal: name,email. Kolom opsional: role,phone,telegram_id,password,project_id,project_division_id,project_role.
              </p>
            </div>
          </div>
        </div>
        <form onSubmit={submitImport} className="grid gap-3 p-5 md:grid-cols-[1fr_auto]">
          <input
            type="file"
            accept=".csv,text/csv"
            className="input"
            onChange={(event) => setImportFile(event.target.files?.[0] || null)}
          />
          <button disabled={importUsers.isPending || !importFile} className="btn-primary justify-center">
            {importUsers.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
            Upload CSV
          </button>
        </form>
        <div className="px-5 pb-5">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">
            Jika kolom password kosong, sistem membuat temporary password otomatis. Simpan hasil upload sebelum meninggalkan halaman, lalu minta pegawai mengganti password di Profil Saya.
          </div>
          {importResults.length > 0 && (
            <div className="mt-4 overflow-x-auto border border-slate-200">
              <table className="min-w-[760px] w-full">
                <thead className="bg-slate-50">
                  <tr>{['Row', 'Email', 'Status', 'Role', 'Temporary password', 'Catatan'].map((header) => <th key={header} className="px-4 py-3 text-left text-xs font-semibold text-slate-500">{header}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {importResults.map((item) => (
                    <tr key={`${item.row}-${item.email}`}>
                      <td className="px-4 py-3 text-xs text-slate-500">{item.row}</td>
                      <td className="px-4 py-3 text-xs font-medium text-slate-800">{item.email}</td>
                      <td className="px-4 py-3">
                        <span className={item.status === 'created' ? 'badge-success badge' : item.status === 'skipped' ? 'badge-warning badge' : 'badge-danger badge'}>{item.status}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">{item.role || '-'}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700">{item.temporary_password || '-'}</td>
                      <td className="px-4 py-3 text-xs text-slate-500">{item.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

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
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Commercial control plane</p>
            <h2 className="text-xl font-bold text-slate-950">Tenant, Paket, Entitlement, dan Readiness</h2>
            <p className="mt-1 text-sm text-slate-500">Fondasi awal untuk pilot berbayar sebelum tenant isolation penuh diterapkan.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              className="input h-10 min-w-[220px] text-sm"
              value={newTenantName}
              onChange={(event) => setNewTenantName(event.target.value)}
              placeholder="Nama tenant pilot"
            />
            <select
              className="input h-10 min-w-[180px] text-sm"
              value={newTenantPlan}
              onChange={(event) => setNewTenantPlan(event.target.value as CommercialPlanKey)}
            >
              {commercialPlans.map((plan) => (
                <option key={plan.plan_key} value={plan.plan_key}>{plan.name}</option>
              ))}
            </select>
            <button
              type="button"
              disabled={newTenantName.trim().length < 2 || createTenant.isPending}
              onClick={() => createTenant.mutate()}
              className="btn-primary h-10 min-w-[136px] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createTenant.isPending ? <Loader2 size={16} className="animate-spin" /> : <Building2 size={16} />}
              Buat tenant
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="card p-5 xl:col-span-2">
            <div className="flex items-center gap-2">
              <Rocket size={18} className="text-cyan-600" />
              <h3 className="text-base font-semibold text-slate-900">Commercial readiness</h3>
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {(commercialReadiness?.checks || []).map((check) => (
                <div key={check.key} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">{check.title}</h4>
                      <p className="mt-1 text-xs leading-5 text-slate-500">{check.detail}</p>
                    </div>
                    <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-bold uppercase', readinessStyle[check.status])}>
                      {check.status}
                    </span>
                  </div>
                  <p className="mt-3 text-xs font-medium text-slate-600">{check.action}</p>
                </div>
              ))}
              {!commercialReadiness?.checks?.length && (
                <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-400">Readiness belum dimuat.</div>
              )}
            </div>
          </div>

          <div className="card p-5">
            <div className="flex items-center gap-2">
              <PackageCheck size={18} className="text-cyan-600" />
              <h3 className="text-base font-semibold text-slate-900">Paket produk</h3>
            </div>
            <div className="mt-4 space-y-3">
              {commercialPlans.map((plan) => (
                <div key={plan.plan_key} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-slate-900">{plan.name}</h4>
                    <span className="badge badge-gray">{plan.enabled_features.includes('all') ? 'All features' : `${plan.enabled_features.length} fitur`}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-500">{plan.positioning}</p>
                  <p className="mt-3 text-sm font-bold text-slate-900">
                    {formatCurrency(plan.monthly_base_price_min_idr)}
                    {plan.monthly_base_price_max_idr ? ` - ${formatCurrency(plan.monthly_base_price_max_idr)}/bulan` : ''}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Tenant pilot</h3>
                <p className="mt-1 text-xs text-slate-500">Pilih tenant untuk melihat limit dan entitlement.</p>
              </div>
              <span className="badge badge-info">{commercialTenants.length} tenant</span>
            </div>
            <div className="mt-4 space-y-2">
              {commercialTenants.map((tenant) => (
                <button
                  key={tenant.id}
                  type="button"
                  onClick={() => setSelectedTenantId(tenant.id)}
                  className={cn(
                    'w-full rounded-lg border p-3 text-left transition',
                    selectedTenant?.id === tenant.id
                      ? 'border-cyan-300 bg-cyan-50'
                      : 'border-slate-200 hover:bg-slate-50',
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-slate-900">{tenant.name}</span>
                    <span className="badge badge-gray">{tenant.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{tenant.slug} · {tenant.plan_key}</p>
                </button>
              ))}
              {commercialTenants.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-400">
                  Belum ada tenant. Buat tenant pilot pertama dari form di atas.
                </div>
              )}
            </div>
          </div>

          <div className="card p-5 xl:col-span-2">
            {selectedTenant ? (
              <div className="space-y-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold text-slate-900">{selectedTenant.name}</h3>
                      <span className="badge badge-info">{selectedPlan?.name || selectedTenant.plan_key}</span>
                      <span className="badge badge-gray">{selectedTenant.onboarding_stage}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      Dibuat {formatDateTime(selectedTenant.created_at)} · Update {formatDateTime(selectedTenant.updated_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <select
                      className="input h-9 w-[170px] text-xs"
                      value={selectedTenant.plan_key}
                      onChange={(event) => updateTenant.mutate({
                        tenantId: selectedTenant.id,
                        data: { plan_key: event.target.value },
                      })}
                    >
                      {commercialPlans.map((plan) => (
                        <option key={plan.plan_key} value={plan.plan_key}>{plan.name}</option>
                      ))}
                    </select>
                    <select
                      className="input h-9 w-[120px] text-xs"
                      value={selectedTenant.status}
                      onChange={(event) => updateTenant.mutate({
                        tenantId: selectedTenant.id,
                        data: { status: event.target.value },
                      })}
                    >
                      {['trial', 'active', 'paused', 'cancelled'].map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
                  {tenantUsage.map((usage) => (
                    <div key={usage.metric_key} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                        <Activity size={13} />
                        {usage.label}
                      </div>
                      <div className="mt-2 text-lg font-bold text-slate-950">
                        {usage.used_value.toLocaleString('id-ID')}
                        <span className="text-xs font-medium text-slate-400"> / {usage.limit_value?.toLocaleString('id-ID') || 'Custom'}</span>
                      </div>
                      <div className="mt-2 h-1.5 rounded-full bg-slate-100">
                        <div
                          className="h-1.5 rounded-full bg-cyan-500"
                          style={{ width: `${Math.min(usage.percent_used || 0, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-900">Entitlement fitur tenant</h4>
                    <span className="text-xs text-slate-400">{tenantEntitlements.filter((item) => item.enabled).length} aktif</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {tenantEntitlements.map((item) => {
                      const isPending = updateEntitlement.isPending && updateEntitlement.variables?.featureKey === item.feature_key
                      return (
                        <div key={item.feature_key} className="rounded-lg border border-slate-200 p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <h5 className="text-sm font-semibold text-slate-900">{item.label}</h5>
                                <span className="badge badge-gray">{item.source}</span>
                                {item.is_core && <span className="badge badge-warning">Core</span>}
                              </div>
                              <p className="mt-1 text-xs text-slate-400">{item.category} · {item.feature_key}</p>
                            </div>
                            <button
                              type="button"
                              disabled={item.is_core || isPending}
                              onClick={() => updateEntitlement.mutate({
                                tenantId: item.tenant_id,
                                featureKey: item.feature_key,
                                enabled: !item.enabled,
                              })}
                              className={cn(
                                'flex h-8 min-w-[86px] items-center justify-center gap-1 rounded-lg px-2 text-xs font-semibold transition',
                                item.enabled
                                  ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                                (item.is_core || isPending) && 'cursor-not-allowed opacity-60',
                              )}
                            >
                              {isPending ? <Loader2 size={13} className="animate-spin" /> : item.enabled ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}
                              {item.enabled ? 'Aktif' : 'Off'}
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-[260px] items-center justify-center text-center text-sm text-slate-400">
                Buat atau pilih tenant untuk mengelola paket dan entitlement.
              </div>
            )}
          </div>
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
    </div>
  )
}
