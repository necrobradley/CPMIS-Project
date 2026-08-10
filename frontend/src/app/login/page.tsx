'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'
import { Building2, Lock, Mail, Loader2, HardHat } from 'lucide-react'

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
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 bg-brand-500 rounded-xl flex items-center justify-center"><HardHat size={22}/></div>
            <div><div className="font-bold text-lg">DigiCom PMIS</div><div className="text-brand-300 text-xs">Communication Control</div></div>
          </div>
          <h1 className="text-4xl font-bold leading-snug mb-4">Pusat Kendali Komunikasi Proyek Konstruksi</h1>
          <p className="text-brand-300 text-base leading-relaxed">Issue, dokumen, approval, audit, AI, n8n, dan laporan Telegram dalam satu PMIS.</p>
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
          <div className="flex items-center gap-3 mb-10 lg:hidden">
            <div className="w-9 h-9 bg-brand-500 rounded-xl flex items-center justify-center text-white"><HardHat size={20}/></div>
            <span className="font-bold text-lg text-slate-900">DigiCom PMIS</span>
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
          </div>
        </div>
      </div>
    </div>
  )
}
