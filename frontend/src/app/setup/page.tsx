'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useState } from 'react'
import { CheckCircle2, FolderKanban, KeyRound, Loader2, Lock, Mail, Send, UserCog } from 'lucide-react'
import toast from 'react-hot-toast'

import { systemApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'

type SetupResult = {
  admin_email: string
  project_id: number
  project_name: string
  project_status: string
  plan_key: string | null
  verification_email_sent: boolean
  verification_message: string
}

export default function InitialSetupPage() {
  const [bootstrapSecret, setBootstrapSecret] = useState('')
  const [adminName, setAdminName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [projectName, setProjectName] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [telegramId, setTelegramId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SetupResult | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (adminPassword.length < 12) return toast.error('Password admin minimal 12 karakter')
    if (!/[A-Z]/.test(adminPassword) || !/[a-z]/.test(adminPassword) || !/\d/.test(adminPassword)) return toast.error('Password wajib memiliki huruf besar, huruf kecil, dan angka')
    if (adminPassword !== confirmPassword) return toast.error('Konfirmasi password tidak sama')
    if (!bootstrapSecret.trim()) return toast.error('Bootstrap secret wajib diisi')

    setLoading(true)
    setResult(null)
    try {
      const response = await systemApi.bootstrapProjectAdmin({
        admin_name: adminName.trim(),
        admin_email: adminEmail.trim().toLowerCase(),
        password: adminPassword,
        project_name: projectName.trim(),
        ...(telegramId.trim() ? { telegram_id: telegramId.trim() } : {}),
      }, bootstrapSecret.trim())
      setResult(response.data)
      setBootstrapSecret('')
      setAdminPassword('')
      setConfirmPassword('')
      toast.success('Admin Proyek dan proyek kosong berhasil dibuat')
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Setup Admin Proyek gagal'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-5 py-10">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div className="flex h-16 w-56 items-center rounded-xl border border-slate-200 bg-white px-4">
            <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={360} height={110} className="h-auto w-full max-w-[200px] object-contain" priority />
          </div>
          <Link href="/login" className="btn-secondary">Kembali ke login</Link>
        </div>

        <div className="card overflow-hidden">
          <div className="border-b border-slate-100 bg-slate-950 p-7 text-white">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/10"><UserCog size={23} /></div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">Setup Admin Proyek</p>
                <h1 className="mt-1 text-2xl font-bold">Buat satu admin untuk satu proyek</h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Tahap ini hanya membuat akun Admin Proyek dan proyek kosong. Dataset, dokumen, pegawai, divisi, serta task diimpor setelah admin memverifikasi email dan login ke Admin Console.
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={submit} className="space-y-6 p-7">
            <div className="grid gap-5 md:grid-cols-2">
              <label className="block md:col-span-2"><span className="label">Bootstrap secret</span><div className="relative"><KeyRound size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="password" value={bootstrapSecret} onChange={(event) => setBootstrapSecret(event.target.value)} className="input pl-9" autoComplete="off" required /></div></label>
              <label className="block"><span className="label">Nama Admin Proyek</span><input value={adminName} onChange={(event) => setAdminName(event.target.value)} className="input" placeholder="Nama lengkap" minLength={2} required /></label>
              <label className="block"><span className="label">Email Admin Proyek</span><div className="relative"><Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="email" value={adminEmail} onChange={(event) => setAdminEmail(event.target.value)} className="input pl-9" placeholder="admin@perusahaan.id" required /></div></label>
              <label className="block md:col-span-2"><span className="label">Nama proyek</span><div className="relative"><FolderKanban size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={projectName} onChange={(event) => setProjectName(event.target.value)} className="input pl-9" placeholder="Nama proyek yang diwakili admin" minLength={2} required /></div></label>
              <label className="block"><span className="label">Telegram ID admin (opsional)</span><div className="relative"><Send size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={telegramId} onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, ''))} inputMode="numeric" className="input pl-9" /></div></label>
              <div className="hidden md:block" />
              <label className="block"><span className="label">Password Admin Proyek</span><div className="relative"><Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="password" value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} className="input pl-9" minLength={12} autoComplete="new-password" required /></div></label>
              <label className="block"><span className="label">Ulangi password</span><input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="input" minLength={12} required /></label>
            </div>

            <div className="rounded-lg border border-cyan-100 bg-cyan-50 p-3 text-xs leading-5 text-cyan-800">
              Password hanya untuk Admin Proyek ini. Akun pegawai nantinya menerima undangan email dan membuat password masing-masing.
            </div>
            <button disabled={loading} className="btn-primary w-full justify-center py-3">{loading ? <Loader2 size={17} className="animate-spin" /> : <UserCog size={17} />}{loading ? 'Membuat akun...' : 'Buat Admin Proyek dan proyek kosong'}</button>
          </form>
        </div>

        {result && (
          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-6">
            <div className="flex gap-3"><CheckCircle2 size={24} className="shrink-0 text-emerald-600" /><div><h2 className="font-semibold text-emerald-950">Setup berhasil</h2><p className="mt-1 text-sm text-emerald-800">{result.project_name} · {result.admin_email}</p><p className="mt-2 text-xs leading-5 text-emerald-700">{result.verification_message}. Paket proyek belum ditetapkan; Admin Owner dapat menerapkannya setelah login.</p><Link href="/login" className="btn-primary mt-4 inline-flex">Masuk ke sistem</Link></div></div>
          </div>
        )}
      </div>
    </div>
  )
}
