'use client'
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Camera, KeyRound, Loader2, Save, Upload, UserCircle } from 'lucide-react'
import { usersApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { ROLE_LABELS, rolePersona } from '@/lib/utils'
import UserAvatar from '@/components/ui/UserAvatar'

export default function ProfilePage() {
  const { user, fetchMe } = useAuthStore()
  const persona = rolePersona(user?.role)
  const [profileForm, setProfileForm] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    telegram_id: user?.telegram_id || '',
  })
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [avatarPreview, setAvatarPreview] = useState('')

  useEffect(() => {
    if (!user) return
    setProfileForm({
      name: user.name || '',
      phone: user.phone || '',
      telegram_id: user.telegram_id || '',
    })
  }, [user])

  useEffect(() => {
    if (!avatarFile) {
      setAvatarPreview('')
      return
    }
    const objectUrl = URL.createObjectURL(avatarFile)
    setAvatarPreview(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [avatarFile])

  const updateProfile = useMutation({
    mutationFn: () => usersApi.update(user!.id, {
      name: profileForm.name.trim(),
      phone: profileForm.phone.trim() || null,
      telegram_id: profileForm.telegram_id.trim() || null,
    }),
    onSuccess: async () => {
      await fetchMe()
      toast.success('Profil diperbarui')
    },
    onError: () => toast.error('Gagal memperbarui profil'),
  })

  const changePassword = useMutation({
    mutationFn: () => usersApi.changeMyPassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    }),
    onSuccess: () => {
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' })
      toast.success('Password diperbarui')
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Gagal mengganti password'),
  })

  const uploadAvatar = useMutation({
    mutationFn: () => {
      const formData = new FormData()
      formData.append('file', avatarFile!)
      return usersApi.uploadMyAvatar(formData)
    },
    onSuccess: async () => {
      setAvatarFile(null)
      await fetchMe()
      toast.success('Foto profil diperbarui')
    },
    onError: (error: { response?: { data?: { detail?: string } } }) =>
      toast.error(error.response?.data?.detail || 'Gagal upload foto profil'),
  })

  function submitProfile(event: React.FormEvent) {
    event.preventDefault()
    if (!user || !profileForm.name.trim()) return
    updateProfile.mutate()
  }

  function submitPassword(event: React.FormEvent) {
    event.preventDefault()
    if (passwordForm.new_password.length < 8) {
      toast.error('Password baru minimal 8 karakter')
      return
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error('Konfirmasi password tidak cocok')
      return
    }
    changePassword.mutate()
  }

  function submitAvatar(event: React.FormEvent) {
    event.preventDefault()
    if (!avatarFile) {
      toast.error('Pilih foto profil dahulu')
      return
    }
    uploadAvatar.mutate()
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-600">Account profile</p>
          <h1 className="page-title">Profil Saya</h1>
          <p className="mt-0.5 text-sm text-slate-500">Kelola kontak pribadi dan password akun internal.</p>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.85fr_1fr]">
        <section className="card p-5">
          <div className={`rounded-2xl bg-gradient-to-br ${persona.gradient} p-5 text-white`}>
            <div className="flex items-start gap-4">
              {avatarPreview ? (
                <span className="h-24 w-24 shrink-0 rounded-full bg-cover bg-center ring-4 ring-white/25" style={{ backgroundImage: `url(${avatarPreview})` }} />
              ) : (
                <UserAvatar user={user} size="xl" className="ring-4 ring-white/25" />
              )}
              <div className="min-w-0 pt-1">
                <p className="text-xs font-semibold uppercase tracking-widest text-white/70">{user ? ROLE_LABELS[user.role] : 'Akun'}</p>
                <h2 className="mt-1 truncate text-xl font-bold">{user?.name || 'Profil pengguna'}</h2>
                <p className="mt-2 inline-flex rounded-full border border-white/25 bg-white/15 px-3 py-1 text-xs font-semibold">{persona.title}</p>
              </div>
            </div>
            <p className="mt-5 text-sm leading-6 text-white/80">{persona.cue}</p>
          </div>

          <form onSubmit={submitAvatar} className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-cyan-700">
                <Camera size={19} />
              </div>
              <div>
                <h3 className="font-semibold text-slate-900">Foto profil</h3>
                <p className="text-xs text-slate-500">JPG, PNG, atau WebP. Maksimal 2MB.</p>
              </div>
            </div>
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-4 py-4 text-sm font-medium text-slate-600 transition hover:border-cyan-300 hover:text-cyan-700">
              <Upload size={16} />
              {avatarFile ? avatarFile.name : 'Pilih foto'}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="sr-only"
                onChange={(event) => setAvatarFile(event.target.files?.[0] || null)}
              />
            </label>
            <button disabled={!avatarFile || uploadAvatar.isPending} className="btn-primary mt-4 w-full justify-center">
              {uploadAvatar.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
              Upload foto
            </button>
          </form>
        </section>

        <div className="grid gap-5">
        <form onSubmit={submitProfile} className="card p-5">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
              <UserCircle size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">Data profil</h2>
              <p className="text-xs text-slate-500">Email dan role dikendalikan admin aplikasi.</p>
            </div>
          </div>
          <div className="space-y-4">
            <label className="label">Nama
              <input className="input mt-1" value={profileForm.name} onChange={(event) => setProfileForm({ ...profileForm, name: event.target.value })} />
            </label>
            <label className="label">Email
              <input className="input mt-1 bg-slate-100 text-slate-500" value={user?.email || ''} disabled />
            </label>
            <label className="label">No. HP
              <input className="input mt-1" value={profileForm.phone} onChange={(event) => setProfileForm({ ...profileForm, phone: event.target.value })} />
            </label>
            <label className="label">Telegram ID
              <input className="input mt-1" value={profileForm.telegram_id} onChange={(event) => setProfileForm({ ...profileForm, telegram_id: event.target.value })} />
            </label>
          </div>
          <button disabled={updateProfile.isPending} className="btn-primary mt-5">
            {updateProfile.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Simpan profil
          </button>
        </form>

        <form onSubmit={submitPassword} className="card p-5">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
              <KeyRound size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">Ganti password</h2>
              <p className="text-xs text-slate-500">Gunakan setelah menerima temporary password dari admin.</p>
            </div>
          </div>
          <div className="space-y-4">
            <label className="label">Password lama
              <input type="password" className="input mt-1" value={passwordForm.current_password} onChange={(event) => setPasswordForm({ ...passwordForm, current_password: event.target.value })} />
            </label>
            <label className="label">Password baru
              <input type="password" className="input mt-1" value={passwordForm.new_password} onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })} />
            </label>
            <label className="label">Konfirmasi password baru
              <input type="password" className="input mt-1" value={passwordForm.confirm_password} onChange={(event) => setPasswordForm({ ...passwordForm, confirm_password: event.target.value })} />
            </label>
          </div>
          <button disabled={changePassword.isPending} className="btn-primary mt-5">
            {changePassword.isPending ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
            Ganti password
          </button>
        </form>
        </div>
      </div>
    </div>
  )
}
