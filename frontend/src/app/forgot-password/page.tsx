'use client'
import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { Mail, Loader2, ArrowLeft, CheckCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { authApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await authApi.forgotPassword(email.trim())
      setSent(true)
      toast.success(response.data.message)
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Permintaan reset password gagal'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-8">
      <div className="w-full max-w-md animate-in">
        <div className="mb-10 flex h-16 items-center rounded-xl border border-slate-200 bg-white px-5">
          <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={360} height={110} className="mx-auto h-auto w-full max-w-[240px] object-contain" priority />
        </div>

        {!sent ? (
          <>
            <h2 className="text-3xl font-bold text-slate-900 mb-1">Lupa Password</h2>
            <p className="text-slate-500 text-sm mb-8">
              Masukkan email Anda dan kami akan mengirimkan link reset password.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Email</label>
                <div className="relative">
                  <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="email" required value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="input pl-9" placeholder="email@perusahaan.id"
                  />
                </div>
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5">
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Mail size={16} />}
                {loading ? 'Mengirim...' : 'Kirim Link Reset'}
              </button>
            </form>
          </>
        ) : (
          <div className="text-center py-8">
            <div className="w-16 h-16 bg-emerald-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <CheckCircle size={32} className="text-emerald-500" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">Periksa Email Anda</h3>
            <p className="text-slate-500 text-sm mb-6">
              Jika <strong>{email}</strong> terdaftar, tautan reset password telah dikirim.
              Periksa inbox dan folder spam Anda.
            </p>
            <p className="text-xs text-slate-400">
              Link berlaku selama 1 jam.
            </p>
          </div>
        )}

        <div className="mt-6 text-center">
          <Link href="/login" className="flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-brand-600 transition">
            <ArrowLeft size={14} /> Kembali ke halaman login
          </Link>
        </div>
      </div>
    </div>
  )
}
