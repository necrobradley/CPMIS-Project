'use client'
import { useState } from 'react'
import Link from 'next/link'
import { HardHat, Mail, Loader2, ArrowLeft, CheckCircle } from 'lucide-react'
import toast from 'react-hot-toast'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    // Simulasi (backend reset password bisa ditambah nanti)
    await new Promise(r => setTimeout(r, 1500))
    setSent(true)
    setLoading(false)
    toast.success('Email reset terkirim!')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-8">
      <div className="w-full max-w-md animate-in">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-9 h-9 bg-brand-500 rounded-xl flex items-center justify-center text-white">
            <HardHat size={20} />
          </div>
          <span className="font-bold text-lg text-slate-900">AI CPMIS</span>
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
            <h3 className="text-xl font-bold text-slate-900 mb-2">Email Terkirim!</h3>
            <p className="text-slate-500 text-sm mb-6">
              Kami telah mengirimkan link reset password ke <strong>{email}</strong>.
              Periksa inbox atau folder spam Anda.
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
