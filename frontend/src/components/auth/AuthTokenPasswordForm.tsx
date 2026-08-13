'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { CheckCircle2, Eye, EyeOff, KeyRound, Loader2 } from 'lucide-react'
import { useState } from 'react'

import { authApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'

type Mode = 'invitation' | 'reset'

export default function AuthTokenPasswordForm({ mode }: { mode: Mode }) {
  const searchParams = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState('')

  const title = mode === 'invitation' ? 'Aktifkan Akun' : 'Atur Ulang Password'
  const description = mode === 'invitation'
    ? 'Tetapkan password pribadi untuk menyelesaikan aktivasi akun Rencanix.'
    : 'Buat password baru untuk memulihkan akses akun Anda.'

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    if (!token) return setError('Tautan tidak memiliki token yang valid.')
    if (password !== confirmation) return setError('Konfirmasi password tidak sama.')
    if (password.length < 10 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password)) {
      return setError('Gunakan minimal 10 karakter yang memuat huruf besar, huruf kecil, dan angka.')
    }
    setLoading(true)
    try {
      if (mode === 'invitation') await authApi.acceptInvitation(token, password)
      else await authApi.resetPassword(token, password)
      setComplete(true)
      setPassword('')
      setConfirmation('')
    } catch (requestError: unknown) {
      setError(apiErrorMessage(requestError, 'Tautan tidak valid atau sudah kedaluwarsa.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-md animate-in">
        <div className="mb-8 flex h-16 items-center rounded-xl border border-slate-200 bg-white px-5">
          <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={360} height={110} className="h-auto w-full object-contain" priority />
        </div>
        <div className="card p-6 sm:p-8">
          {complete ? (
            <div className="py-5 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600"><CheckCircle2 size={32} /></div>
              <h1 className="mt-5 text-2xl font-bold text-slate-950">{mode === 'invitation' ? 'Akun Berhasil Diaktifkan' : 'Password Berhasil Diperbarui'}</h1>
              <p className="mt-2 text-sm leading-6 text-slate-500">Silakan masuk menggunakan email dan password baru Anda.</p>
              <Link href="/login" className="btn-primary mt-6 w-full justify-center">Masuk ke Rencanix</Link>
            </div>
          ) : (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-50 text-sky-600"><KeyRound size={22} /></div>
              <h1 className="mt-5 text-2xl font-bold text-slate-950">{title}</h1>
              <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
              {!token && <div className="mt-5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">Token tidak ditemukan. Buka kembali tautan dari email terbaru.</div>}
              <form onSubmit={submit} className="mt-6 space-y-4">
                <div>
                  <label className="label">Password baru</label>
                  <div className="relative">
                    <input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} className="input pr-10" autoComplete="new-password" required />
                    <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" aria-label={showPassword ? 'Sembunyikan password' : 'Tampilkan password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-400">Minimal 10 karakter, dengan huruf besar, huruf kecil, dan angka.</p>
                </div>
                <div>
                  <label className="label">Konfirmasi password</label>
                  <input type={showPassword ? 'text' : 'password'} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="input" autoComplete="new-password" required />
                </div>
                {error && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm leading-5 text-rose-700">{error}</div>}
                <button type="submit" disabled={loading || !token} className="btn-primary w-full justify-center py-2.5">
                  {loading ? <Loader2 size={17} className="animate-spin" /> : <KeyRound size={17} />}
                  {loading ? 'Memproses...' : mode === 'invitation' ? 'Aktifkan akun' : 'Simpan password baru'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
