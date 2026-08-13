'use client'
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { projectsApi, usersApi } from '@/lib/api'
import { Division, Project, ProjectMemberRoleCatalog, ProjectRolePolicy, User, UserRole } from '@/types'
import { ROLE_LABELS, formatDate } from '@/lib/utils'
import UserAvatar from '@/components/ui/UserAvatar'
import {
  Building2, CheckCircle2, FileSpreadsheet, FolderKanban, KeyRound, Loader2, Mail,
  MessageCircle, Phone, Plus, Shield, Upload, UserPlus, Users,
  RefreshCw,
} from 'lucide-react'

const ROLE_COLORS: Record<string, string> = {
  admin:         'badge-danger',
  director:      'badge-brand',
  manager:       'badge-info',
  staff:         'badge-gray',
  subcontractor: 'badge-warning',
}

const ROLE_OPTIONS: UserRole[] = ['director', 'manager', 'staff', 'subcontractor']
const PROJECT_ADMIN_ROLE_CODES = new Set(['project_admin'])
const EMPTY_SETUP_FORM = {
  name: '',
  email: '',
  role: 'staff' as UserRole,
  phone: '',
  telegram_id: '',
  project_id: '',
  project_division_id: '',
  project_role: 'staff',
}
type SetupMode = 'new' | 'existing'
type ImportResult = {
  row: number
  email: string
  status: string
  message: string
  temporary_password?: string
  role?: string
}

export default function UsersPage() {
  const qc = useQueryClient()
  const [showSetup, setShowSetup] = useState(false)
  const [setupMode, setSetupMode] = useState<SetupMode>('new')
  const [selectedUserId, setSelectedUserId] = useState('')
  const [setupForm, setSetupForm] = useState({ ...EMPTY_SETUP_FORM })
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importResults, setImportResults] = useState<ImportResult[]>([])
  const { data: users = [], isLoading } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: async () => (await usersApi.list()).data,
  })
  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  useEffect(() => {
    if (!setupForm.project_id && projects[0]) {
      setSetupForm((current) => ({ ...current, project_id: String(projects[0].id) }))
    }
  }, [projects, setupForm.project_id])
  const selectedProjectId = setupForm.project_id ? Number(setupForm.project_id) : undefined
  const { data: divisions = [] } = useQuery<Division[]>({
    queryKey: ['project-divisions', selectedProjectId],
    queryFn: async () => (await projectsApi.divisions(selectedProjectId!)).data,
    enabled: Boolean(selectedProjectId),
  })
  const { data: roleCatalog = [] } = useQuery<ProjectMemberRoleCatalog[]>({
    queryKey: ['project-member-roles'],
    queryFn: async () => (await projectsApi.memberRoles()).data,
  })
  const { data: rolePolicy = [] } = useQuery<ProjectRolePolicy[]>({
    queryKey: ['project-role-policy', selectedProjectId],
    queryFn: async () => (await projectsApi.rolePolicy(selectedProjectId!)).data,
    enabled: Boolean(selectedProjectId),
  })

  const activeUsers   = users.filter((u) => u.is_active)
  const withTelegram  = users.filter((u) => u.telegram_id)
  const selectedUser = useMemo(
    () => users.find((user) => user.id === Number(selectedUserId)),
    [selectedUserId, users]
  )
  const manageableUsers = users.filter((user) => user.role !== 'admin' && user.role !== 'owner')
  const roleOptions = useMemo(() => {
    const availableRoles = roleCatalog.filter((role) => !PROJECT_ADMIN_ROLE_CODES.has(role.code))
    if (!selectedProjectId) return availableRoles
    if (!rolePolicy.length) return availableRoles
    const enabled = new Set(rolePolicy.filter((role) => role.enabled).map((role) => role.code))
    return availableRoles.filter((role) => enabled.has(role.code))
  }, [roleCatalog, rolePolicy, selectedProjectId])
  const effectiveProjectRoleCode = useMemo(() => {
    if (!selectedProjectId) return setupForm.project_role
    if (roleOptions.some((role) => role.code === setupForm.project_role)) return setupForm.project_role
    return roleOptions[0]?.code || setupForm.project_role
  }, [roleOptions, selectedProjectId, setupForm.project_role])
  const selectedProjectRole = roleCatalog.find((role) => role.code === effectiveProjectRoleCode)
  const requiresDivision = Boolean(selectedProjectId && selectedProjectRole?.requires_division)

  const createSetup = useMutation({
    mutationFn: () => usersApi.setup({
      name: setupForm.name.trim(),
      email: setupForm.email.trim(),
      role: setupForm.role,
      phone: setupForm.phone.trim() || null,
      telegram_id: setupForm.telegram_id.trim() || null,
      project_id: selectedProjectId || null,
      project_division_id: setupForm.project_division_id ? Number(setupForm.project_division_id) : null,
      project_role: effectiveProjectRoleCode,
    }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ['users'] })
      if (selectedProjectId) qc.invalidateQueries({ queryKey: ['project-members', selectedProjectId] })
      setSetupForm({ ...EMPTY_SETUP_FORM, project_id: projects[0] ? String(projects[0].id) : '' })
      setShowSetup(false)
      toast.success(response.data.invitation_sent ? 'Akun dibuat dan undangan email terkirim' : 'Akun dibuat; email perlu dikirim ulang setelah layanan email aktif')
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Gagal membuat setup akun'),
  })

  const updateSetup = useMutation({
    mutationFn: () => usersApi.updateSetup(Number(selectedUserId), {
      role: setupForm.role,
      phone: setupForm.phone.trim() || null,
      telegram_id: setupForm.telegram_id.trim() || null,
      project_id: selectedProjectId || null,
      project_division_id: setupForm.project_division_id ? Number(setupForm.project_division_id) : null,
      project_role: selectedProjectId ? effectiveProjectRoleCode : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      if (selectedProjectId) qc.invalidateQueries({ queryKey: ['project-members', selectedProjectId] })
      toast.success('Setup akun existing diperbarui')
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Gagal memperbarui setup akun'),
  })
  const importUsers = useMutation({
    mutationFn: () => {
      const formData = new FormData()
      if (importFile) formData.append('file', importFile)
      return usersApi.importCsv(formData)
    },
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setImportResults(response.data.results || [])
      toast.success(`${response.data.created || 0} akun dibuat dari CSV`)
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Gagal import daftar pegawai'),
  })
  const resendInvitation = useMutation({
    mutationFn: (userId: number) => usersApi.resendInvitation(userId),
    onSuccess: (response) => toast.success(response.data.message),
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Undangan belum dapat dikirim ulang'),
  })

  function resetSetupForm(mode: SetupMode = setupMode) {
    setSetupMode(mode)
    setSelectedUserId('')
    setSetupForm({ ...EMPTY_SETUP_FORM, project_id: projects[0] ? String(projects[0].id) : '' })
  }

  function selectExistingUser(userId: string) {
    setSelectedUserId(userId)
    const user = users.find((item) => item.id === Number(userId))
    if (!user) return
    setSetupForm({
      ...EMPTY_SETUP_FORM,
      project_id: projects[0] ? String(projects[0].id) : '',
      name: user.name,
      email: user.email || '',
      role: user.role,
      phone: user.phone || '',
      telegram_id: user.telegram_id || '',
    })
  }

  function submitSetup(event: React.FormEvent) {
    event.preventDefault()
    if (setupMode === 'new' && (!setupForm.name.trim() || !setupForm.email.trim())) {
      toast.error('Nama dan email wajib diisi')
      return
    }
    if (setupMode === 'existing' && !selectedUserId) {
      toast.error('Pilih akun existing yang akan diatur')
      return
    }
    if (selectedProjectId && roleOptions.length === 0) {
      toast.error('Belum ada role proyek aktif untuk proyek ini')
      return
    }
    if (requiresDivision && !setupForm.project_division_id) {
      toast.error('Role proyek ini wajib ditempatkan pada divisi')
      return
    }
    if (setupMode === 'new') createSetup.mutate()
    else updateSetup.mutate()
  }

  function submitImport(event: React.FormEvent) {
    event.preventDefault()
    if (!importFile) {
      toast.error('Pilih file CSV daftar pegawai')
      return
    }
    importUsers.mutate()
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
          <div>
            <h1 className="page-title">Pengguna</h1>
          <p className="text-sm text-slate-500 mt-0.5">{users.length} pengguna terdaftar pada {projects[0]?.project_name || 'proyek ini'}. Admin Proyek membuat dan mengatur akun tim dari sini.</p>
        </div>
        <button type="button" onClick={() => setShowSetup((value) => !value)} className="btn-primary">
          <UserPlus size={16} /> Setup Akun
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Pengguna', value: users.length, icon: Users, color: 'text-brand-500', bg: 'bg-brand-50' },
          { label: 'Aktif',          value: activeUsers.length, icon: Shield, color: 'text-emerald-500', bg: 'bg-emerald-50' },
          { label: 'Terhubung Telegram', value: withTelegram.length, icon: MessageCircle, color: 'text-violet-500', bg: 'bg-violet-50' },
        ].map((s) => (
          <div key={s.label} className="card p-5 flex items-center gap-4">
            <div className={`w-10 h-10 ${s.bg} rounded-xl flex items-center justify-center`}>
              <s.icon size={20} className={s.color} />
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-900">{s.value}</div>
              <div className="text-xs text-slate-500">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
              <FileSpreadsheet size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">Import daftar pegawai</h2>
              <p className="mt-1 text-xs text-slate-500">Upload CSV untuk membuat akun tim secara massal. Semua akun dibatasi ke proyek Admin ini. Kolom: name,email,role,phone,telegram_id,project_division_id,project_role.</p>
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
            Import CSV
          </button>
        </form>
        <div className="px-5 pb-5">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">
            Sistem tidak membuat atau menampilkan password pegawai. Setiap pegawai menerima tautan aktivasi pribadi melalui email untuk menetapkan password sendiri.
          </div>
          {importResults.length > 0 && (
            <div className="mt-4 overflow-x-auto border border-slate-200">
              <table className="min-w-[760px] w-full">
                <thead className="bg-slate-50">
                  <tr>{['Row', 'Email', 'Status', 'Role', 'Catatan'].map((header) => <th key={header} className="px-4 py-3 text-left text-xs font-semibold text-slate-500">{header}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {importResults.map((item) => (
                    <tr key={`${item.row}-${item.email}`}>
                      <td className="px-4 py-3 text-xs text-slate-500">{item.row}</td>
                      <td className="px-4 py-3 text-xs font-medium text-slate-800">{item.email}</td>
                      <td className="px-4 py-3"><span className={item.status === 'invited' ? 'badge-success badge' : item.status === 'created' || item.status === 'skipped' ? 'badge-warning badge' : 'badge-danger badge'}>{item.status}</span></td>
                      <td className="px-4 py-3 text-xs text-slate-500">{item.role || '-'}</td>
                      <td className="px-4 py-3 text-xs text-slate-500">{item.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showSetup && (
        <form onSubmit={submitSetup} className="card overflow-hidden">
          <div className="border-b border-slate-100 p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <Plus size={18} />
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">Wizard setup akun, role, dan proyek</h2>
                <p className="mt-1 text-xs text-slate-500">Pilih mode akun baru atau akun existing, lalu atur Telegram, divisi, dan tanggung jawab proyek. Akun yang dibuat otomatis dibatasi pada proyek ini.</p>
              </div>
            </div>
            <div className="mt-5 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
              {[
                { key: 'new' as SetupMode, label: 'Akun Baru' },
                { key: 'existing' as SetupMode, label: 'Akun Existing' },
              ].map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => resetSetupForm(item.key)}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                    setupMode === item.key ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-5 p-5 xl:grid-cols-[1fr_1fr]">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                <KeyRound size={13} /> Akun & RBAC global
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {setupMode === 'existing' ? (
                  <label className="label md:col-span-2">
                    Pilih akun existing
                    <select className="input mt-1" value={selectedUserId} onChange={(event) => selectExistingUser(event.target.value)} required>
                      <option value="">Pilih user yang sudah ada...</option>
                      {manageableUsers.map((user) => (
                        <option key={user.id} value={user.id}>{user.name} - {user.email || ROLE_LABELS[user.role]}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <>
                    <label className="label">Nama<input required className="input mt-1" value={setupForm.name} onChange={(event) => setSetupForm({ ...setupForm, name: event.target.value })} placeholder="Nama lengkap pegawai" /></label>
                    <label className="label">Email perusahaan<input required type="email" className="input mt-1" value={setupForm.email} onChange={(event) => setSetupForm({ ...setupForm, email: event.target.value })} placeholder="pegawai@perusahaan.id" /></label>
                  </>
                )}
                <label className="label">Role aplikasi / organisasi<select className="input mt-1" value={setupForm.role} onChange={(event) => setSetupForm({ ...setupForm, role: event.target.value as UserRole })}>{ROLE_OPTIONS.map((role) => <option key={role} value={role}>{ROLE_LABELS[role]}</option>)}</select></label>
                <label className="label">No. HP<input className="input mt-1" value={setupForm.phone} onChange={(event) => setSetupForm({ ...setupForm, phone: event.target.value })} placeholder="Opsional" /></label>
                <label className="label">Telegram ID<input className="input mt-1" value={setupForm.telegram_id} onChange={(event) => setSetupForm({ ...setupForm, telegram_id: event.target.value })} placeholder="Opsional untuk bot" /></label>
                {setupMode === 'existing' && selectedUser && (
                  <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                    Mengatur akun <span className="font-semibold text-slate-700">{selectedUser.name}</span>. Data historis laporan, task, dan komunikasi tetap melekat ke user yang sama.
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                <FolderKanban size={13} /> Assignment proyek
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="label md:col-span-2">Proyek<select className="input mt-1" value={setupForm.project_id} disabled>{projects.map((project) => <option key={project.id} value={project.id}>{project.project_name}</option>)}</select></label>
                <label className="label">Divisi proyek<select className="input mt-1" value={setupForm.project_division_id} onChange={(event) => setSetupForm({ ...setupForm, project_division_id: event.target.value })} disabled={!selectedProjectId}><option value="">{requiresDivision ? 'Pilih divisi...' : 'Tanpa divisi'}</option>{divisions.map((division) => <option key={division.id} value={division.id}>{division.division_name}</option>)}</select></label>
                <label className="label">Role proyek / penugasan<select className="input mt-1" value={effectiveProjectRoleCode} onChange={(event) => setSetupForm({ ...setupForm, project_role: event.target.value })} disabled={!selectedProjectId}>{roleOptions.map((role) => <option key={role.code} value={role.code}>{role.label}</option>)}</select></label>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="badge-info"><Building2 size={12} /> Assignment proyek aktif</span>
                  {selectedProjectRole && <span className="badge-gray">{selectedProjectRole.can_be_task_pic ? 'Bisa jadi PIC task' : 'Stakeholder/reviewer'}</span>}
                  {requiresDivision && <span className="badge-warning">Wajib divisi</span>}
                </div>
                <p className="mt-3 text-xs leading-5 text-slate-500">
                  {setupMode === 'new'
                    ? 'Akun baru menerima undangan aktivasi melalui email. Setelah menetapkan password, user mengikuti RBAC global dan assignment proyek yang dipilih.'
                    : 'Mode existing tidak membuat akun baru. Sistem memperbarui RBAC global dan mengaktifkan atau mengubah membership proyek untuk user yang dipilih.'}
                </p>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-100 p-5">
            <button type="button" onClick={() => { setShowSetup(false); resetSetupForm('new') }} className="btn-secondary">Batal</button>
            <button disabled={createSetup.isPending || updateSetup.isPending} className="btn-primary">
              {createSetup.isPending || updateSetup.isPending ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              {setupMode === 'new' ? 'Buat Setup' : 'Update Setup'}
            </button>
          </div>
        </form>
      )}

      {/* Users table */}
      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-100">
                  {['Pengguna', 'Role', 'Kontak', 'Telegram', 'Verifikasi', 'Status', 'Bergabung'].map((h) => (
                    <th key={h} className="text-left px-5 py-3.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50 transition">
                    <td className="px-5 py-4">
                      {u.must_set_password ? (
                        <div className="space-y-2">
                          <span className="badge-warning badge">Menunggu aktivasi</span>
                          <button type="button" disabled={resendInvitation.isPending} onClick={() => resendInvitation.mutate(u.id)} className="flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:text-brand-700"><RefreshCw size={11} /> Kirim ulang</button>
                        </div>
                      ) : u.email_verified_at || !u.email_verification_required ? (
                        <span className="badge-success badge">Terverifikasi</span>
                      ) : (
                        <span className="badge-warning badge">Belum verifikasi</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <UserAvatar user={u} size="md" />
                        <div>
                          <div className="text-sm font-semibold text-slate-800">{u.name}</div>
                          <div className="text-xs text-slate-400 flex items-center gap-1">
                            <Mail size={10} /> {u.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className={ROLE_COLORS[u.role] + ' badge'}>{ROLE_LABELS[u.role]}</span>
                    </td>
                    <td className="px-5 py-4">
                      {u.phone ? (
                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                          <Phone size={11} /> {u.phone}
                        </div>
                      ) : <span className="text-slate-300 text-xs">—</span>}
                    </td>
                    <td className="px-5 py-4">
                      {u.telegram_id ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-emerald-400" />
                          <span className="text-xs text-slate-500">Terhubung</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <div className="w-2 h-2 rounded-full bg-slate-200" />
                          <span className="text-xs text-slate-400">Belum</span>
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      {u.is_active ? (
                        <span className="badge-success badge">Aktif</span>
                      ) : (
                        <span className="badge-danger badge">Nonaktif</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-xs text-slate-400">{formatDate(u.created_at)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
