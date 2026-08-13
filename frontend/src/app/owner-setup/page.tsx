'use client'

import Image from 'next/image'
import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { CheckCircle2, KeyRound, Loader2, LockKeyhole, Mail, ShieldCheck, UserRound } from 'lucide-react'
import toast from 'react-hot-toast'

import { systemApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'

export default function OwnerSetupPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [bootstrapSecret, setBootstrapSecret] = useState('')
  const [loading, setLoading] = useState(false)
  const [createdEmail, setCreatedEmail] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (password.length < 12 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password)) {
      return toast.error('Password minimal 12 karakter serta memiliki huruf besar, huruf kecil, dan angka')
    }
    if (password !== confirmation) return toast.error('Konfirmasi password tidak sama')
    if (!bootstrapSecret.trim()) return toast.error('Bootstrap secret wajib diisi')

    setLoading(true)
    try {
      const response = await systemApi.bootstrapOwner(
        { name: name.trim(), email: email.trim().toLowerCase(), password },
        bootstrapSecret.trim(),
      )
      setCreatedEmail(response.data.email)
      setPassword('')
      setConfirmation('')
      setBootstrapSecret('')
      toast.success('Admin Owner berhasil dibuat')
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Admin Owner gagal dibuat'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between gap-4">
          <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={170} height={48} className="h-12 w-auto object-contain" priority />
          <Link href="/login" className="text-sm font-semibold text-cyan-700 hover:text-cyan-800">Kembali ke login</Link>
        </div>

        <section className="card overflow-hidden">
          <header className="bg-slate-950 p-7 text-white">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/10"><ShieldCheck size={24} /></div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">One-time platform bootstrap</p>
                <h1 className="mt-1 text-2xl font-bold">Buat Admin Owner</h1>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Hanya satu Admin Owner yang dapat dibuat. Akun ini mengatur paket dan pilihan fitur setiap proyek, tetapi tidak membuat akun pegawai.
                </p>
              </div>
            </div>
          </header>

          {createdEmail ? (
            <div className="p-7">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex gap-3">
                  <CheckCircle2 className="shrink-0 text-emerald-600" size={24} />
                  <div>
                    <h2 className="font-semibold text-emerald-950">Admin Owner berhasil dibuat</h2>
                    <p className="mt-2 text-sm leading-6 text-emerald-800">
                      Tautan verifikasi telah dikirim ke {createdEmail}. Verifikasi email terlebih dahulu, lalu masuk melalui halaman login.
                    </p>
                    <Link href="/login" className="btn-primary mt-4 inline-flex">Buka halaman login</Link>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5 p-7">
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                Email transaksional wajib aktif. Jika pengiriman verifikasi gagal, sistem membatalkan pembuatan akun agar Owner tidak terkunci.
              </div>

              <label className="block">
                <span className="label">Nama Admin Owner</span>
                <div className="relative"><UserRound size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input className="input pl-9" value={name} onChange={(event) => setName(event.target.value)} minLength={2} required /></div>
              </label>
              <label className="block">
                <span className="label">Email</span>
                <div className="relative"><Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="email" className="input pl-9" value={email} onChange={(event) => setEmail(event.target.value)} required /></div>
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block"><span className="label">Password</span><div className="relative"><LockKeyhole size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="password" className="input pl-9" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required /></div></label>
                <label className="block"><span className="label">Konfirmasi password</span><div className="relative"><LockKeyhole size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="password" className="input pl-9" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" required /></div></label>
              </div>
              <label className="block">
                <span className="label">Bootstrap secret</span>
                <div className="relative"><KeyRound size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="password" className="input pl-9" value={bootstrapSecret} onChange={(event) => setBootstrapSecret(event.target.value)} autoComplete="off" required /></div>
                <span className="mt-1.5 block text-xs text-slate-400">Secret hanya dikirim ke backend melalui koneksi HTTPS dan tidak disimpan oleh browser.</span>
              </label>

              <button className="btn-primary w-full justify-center" disabled={loading}>
                {loading ? <Loader2 size={17} className="animate-spin" /> : <ShieldCheck size={17} />}
                {loading ? 'Memeriksa dan mengirim verifikasi...' : 'Buat Admin Owner satu kali'}
              </button>
            </form>
          )}
        </section>
      </div>
    </main>
  )
}
