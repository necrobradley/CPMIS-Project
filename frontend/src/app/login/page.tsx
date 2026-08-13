'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Image from 'next/image'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'
import { Building2, Lock, Mail, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const login  = useAuthStore(s => s.login)
  const router = useRouter()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await login(email, password)
      toast.success('Berhasil masuk!')
      router.push('/dashboard')
    } catch (err: unknown) {
      const msg = (err as {response?:{data?:{detail?:string}}})?.response?.data?.detail ?? 'Login gagal.'
      toast.error(msg)
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex flex-col justify-between w-[480px] bg-brand-900 p-12 text-white relative overflow-hidden">
        <div className="absolute inset-0 opacity-10" style={{backgroundImage:'radial-gradient(circle at 20% 50%, #38bdf8 0%, transparent 60%)'}} />
        <div className="relative">
          <div className="mb-16 flex h-20 items-center rounded-2xl bg-white px-6 shadow-lg shadow-slate-950/20">
            <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={440} height={135} className="h-auto w-full object-contain" priority />
          </div>
          <h1 className="mb-4 text-4xl font-bold leading-snug">Kendali Proyek yang Terhubung dan Terukur</h1>
          <p className="text-base leading-relaxed text-brand-200">Kelola pekerjaan, dokumen, persetujuan, komunikasi lapangan, dan analitik AI dalam satu ruang kerja yang terintegrasi.</p>
        </div>
        <div className="relative grid grid-cols-2 gap-4">
          {[{label:'Proyek Aktif',value:'12+'},{label:'Laporan AI',value:'340+'},{label:'Task Otomatis',value:'1.2k+'},{label:'Efisiensi',value:'40%↑'}].map(s=>(
            <div key={s.label} className="bg-white/10 rounded-xl p-4 backdrop-blur-sm">
              <div className="text-2xl font-bold">{s.value}</div>
              <div className="text-brand-300 text-xs mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <div className="w-full max-w-md animate-in">
          <div className="mb-10 flex h-16 items-center rounded-xl border border-slate-200 bg-white px-4 lg:hidden">
            <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={360} height={110} className="h-auto w-full object-contain" priority />
          </div>
          <h2 className="text-3xl font-bold text-slate-900 mb-1">Masuk</h2>
          <p className="text-slate-500 text-sm mb-8">Masukkan kredensial akun Anda</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="label">Email</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
                <input type="email" value={email} onChange={e=>setEmail(e.target.value)} className="input pl-9" placeholder="email@perusahaan.id" required/>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="label mb-0">Password</label>
                <Link href="/forgot-password" className="text-xs text-brand-500 hover:text-brand-700">Lupa password?</Link>
              </div>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
                <input type="password" value={password} onChange={e=>setPassword(e.target.value)} className="input pl-9" placeholder="••••••••" required/>
              </div>
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-2.5 text-base">
              {loading ? <Loader2 size={18} className="animate-spin"/> : <Building2 size={18}/>}
              {loading ? 'Memproses...' : 'Masuk'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm font-medium text-slate-600">Akun dibuat oleh admin aplikasi perusahaan.</p>
            <p className="mt-1 text-xs text-slate-400">Hubungi admin untuk aktivasi akun atau reset temporary password.</p>
            <Link href="/setup" className="mt-4 inline-flex text-sm font-semibold text-brand-600 hover:text-brand-700">
              Setup awal dan import paket data proyek
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
