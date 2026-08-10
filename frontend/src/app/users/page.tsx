'use client'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { projectsApi, usersApi } from '@/lib/api'
import { Division, Project, ProjectMemberRoleCatalog, ProjectRolePolicy, User, UserRole } from '@/types'
import { ROLE_LABELS, formatDate } from '@/lib/utils'
import UserAvatar from '@/components/ui/UserAvatar'
import {
  Building2, CheckCircle2, FileSpreadsheet, FolderKanban, KeyRound, Loader2, Mail,
  MessageCircle, Phone, Plus, Shield, Upload, UserPlus, Users,
} from 'lucide-react'

const ROLE_COLORS: Record<string, string> = {
  admin:         'badge-danger',
  director:      'badge-brand',
  manager:       'badge-info',
  staff:         'badge-gray',
  subcontractor: 'badge-warning',
}

const ROLE_OPTIONS: UserRole[] = ['admin', 'director', 'manager', 'staff', 'subcontractor']
const PROJECT_ADMIN_ROLE_CODES = new Set(['project_admin'])
const EMPTY_SETUP_FORM = {
  name: '',
  email: '',
  password: 'dummy1234',
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
  const roleOptions = useMemo(() => {
    const availableRoles = setupForm.role === 'admin'
      ? roleCatalog.filter((role) => !PROJECT_ADMIN_ROLE_CODES.has(role.code))
      : roleCatalog
    if (!selectedProjectId) return availableRoles
    if (!rolePolicy.length) return availableRoles
    const enabled = new Set(rolePolicy.filter((role) => role.enabled).map((role) => role.code))
    return availableRoles.filter((role) => enabled.has(role.code))
  }, [roleCatalog, rolePolicy, selectedProjectId, setupForm.role])
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
      password: setupForm.password,
      role: setupForm.role,
      phone: setupForm.phone.trim() || null,
      telegram_id: setupForm.telegram_id.trim() || null,
      project_id: selectedProjectId || null,
      project_division_id: setupForm.project_division_id ? Number(setupForm.project_division_id) : null,
      project_role: effectiveProjectRoleCode,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      if (selectedProjectId) qc.invalidateQueries({ queryKey: ['project-members', selectedProjectId] })
      setSetupForm({ ...EMPTY_SETUP_FORM })
      setShowSetup(false)
      toast.success('Akun dummy dan assignment proyek dibuat')
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

  function resetSetupForm(mode: SetupMode = setupMode) {
    setSetupMode(mode)
    setSelectedUserId('')
    setSetupForm({ ...EMPTY_SETUP_FORM })
  }

  function selectExistingUser(userId: string) {
    setSelectedUserId(userId)
    const user = users.find((item) => item.id === Number(userId))
    if (!user) return
    setSetupForm({
      ...EMPTY_SETUP_FORM,
      name: user.name,
      email: user.email || '',
      role: user.role,
      phone: user.phone || '',
      telegram_id: user.telegram_id || '',
    })
  }

  function submitSetup(event: React.FormEvent) {
    event.preventDefault()
    if (setupMode === 'new' && (!setupForm.name.trim() || !setupForm.email.trim() || setupForm.password.length < 8)) {
      toast.error('Nama, email, dan password minimal 8 karakter wajib diisi')
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
          <p className="text-sm text-slate-500 mt-0.5">{users.length} pengguna terdaftar. Admin aplikasi membuat akun, RBAC global, dan admin proyek dari sini.</p>
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
              <p className="mt-1 text-xs text-slate-500">Upload CSV dari HR untuk membuat akun internal secara massal. Kolom: name,email,role,phone,telegram_id,password,project_id,project_division_id,project_role.</p>
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
            Jika kolom password kosong, sistem membuat temporary password otomatis. Simpan hasil import sebelum halaman ditutup, lalu minta pegawai mengganti password dari menu Profil Saya.
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
                      <td className="px-4 py-3"><span className={item.status === 'created' ? 'badge-success badge' : item.status === 'skipped' ? 'badge-warning badge' : 'badge-danger badge'}>{item.status}</span></td>
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

      {showSetup && (
        <form onSubmit={submitSetup} className="card overflow-hidden">
          <div className="border-b border-slate-100 p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <Plus size={18} />
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">Wizard setup akun, role, dan proyek</h2>
                <p className="mt-1 text-xs text-slate-500">Pilih mode akun baru atau akun existing, lalu atur RBAC global, Telegram, divisi, dan role proyek. Role admin proyek hanya dapat dibuat oleh admin aplikasi.</p>
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
                      {users.map((user) => (
                        <option key={user.id} value={user.id}>{user.name} - {user.email || ROLE_LABELS[user.role]}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <>
                    <label className="label">Nama<input required className="input mt-1" value={setupForm.name} onChange={(event) => setSetupForm({ ...setupForm, name: event.target.value })} placeholder="Nama staff dummy" /></label>
                    <label className="label">Email<input required type="email" className="input mt-1" value={setupForm.email} onChange={(event) => setSetupForm({ ...setupForm, email: event.target.value })} placeholder="staff.demo@cpmis.id" /></label>
                    <label className="label">Password dummy<input required className="input mt-1" value={setupForm.password} onChange={(event) => setSetupForm({ ...setupForm, password: event.target.value })} /></label>
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
                <label className="label md:col-span-2">Proyek<select className="input mt-1" value={setupForm.project_id} onChange={(event) => setSetupForm({ ...setupForm, project_id: event.target.value, project_division_id: '', project_role: 'staff' })}><option value="">Tanpa assignment proyek dulu</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.project_name}</option>)}</select></label>
                <label className="label">Divisi proyek<select className="input mt-1" value={setupForm.project_division_id} onChange={(event) => setSetupForm({ ...setupForm, project_division_id: event.target.value })} disabled={!selectedProjectId}><option value="">{requiresDivision ? 'Pilih divisi...' : 'Tanpa divisi'}</option>{divisions.map((division) => <option key={division.id} value={division.id}>{division.division_name}</option>)}</select></label>
                <label className="label">Role proyek / penugasan<select className="input mt-1" value={effectiveProjectRoleCode} onChange={(event) => setSetupForm({ ...setupForm, project_role: event.target.value })} disabled={!selectedProjectId}>{roleOptions.map((role) => <option key={role.code} value={role.code}>{role.label}</option>)}</select></label>
              </div>
              {setupForm.role === 'admin' && selectedProjectId && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
                  Admin Aplikasi tidak dirangkap sebagai Admin Proyek. Gunakan role proyek khusus Admin Proyek untuk personel yang mengelola administrasi proyek.
                </div>
              )}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="badge-info"><Building2 size={12} /> {selectedProjectId ? 'Assignment aktif' : 'Akun saja'}</span>
                  {selectedProjectRole && <span className="badge-gray">{selectedProjectRole.can_be_task_pic ? 'Bisa jadi PIC task' : 'Stakeholder/reviewer'}</span>}
                  {requiresDivision && <span className="badge-warning">Wajib divisi</span>}
                </div>
                <p className="mt-3 text-xs leading-5 text-slate-500">
                  {setupMode === 'new'
                    ? 'Akun baru langsung mengikuti RBAC global. Bila proyek dipilih, sistem juga membuat membership proyek agar user muncul di assignment task, laporan, dan komunikasi proyek.'
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
                  {['Pengguna', 'Role', 'Kontak', 'Telegram', 'Status', 'Bergabung'].map((h) => (
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
