'use client'

import Link from 'next/link'
import { useState } from 'react'
import { CheckCircle2, Database, FileArchive, HardHat, KeyRound, Loader2, Lock, Mail, Send } from 'lucide-react'
import toast from 'react-hot-toast'

import { systemApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'
import { prepareMnbcImportArchive } from '@/lib/mnbc-import'

type SetupResult = {
  project_id: number
  project_name: string
  tasks_upserted: number
  nodes_upserted: number
  relationships_upserted: number
  rules_upserted: number
  reasoning_examples_upserted: number
  telegram_linked: boolean
}

export default function InitialSetupPage() {
  const [dataset, setDataset] = useState<File | null>(null)
  const [bootstrapSecret, setBootstrapSecret] = useState('')
  const [adminEmail, setAdminEmail] = useState('admin.mnbc@demo.local')
  const [adminPassword, setAdminPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [telegramId, setTelegramId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SetupResult | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!dataset) return toast.error('Pilih files.zip MNBC terlebih dahulu')
    if (adminPassword.length < 12) return toast.error('Password admin minimal 12 karakter')
    if (adminPassword !== confirmPassword) return toast.error('Konfirmasi password tidak sama')
    if (!bootstrapSecret.trim()) return toast.error('Bootstrap secret wajib diisi')

    setLoading(true)
    setResult(null)
    try {
      const preparedArchive = await prepareMnbcImportArchive(dataset)
      const formData = new FormData()
      formData.append('dataset', preparedArchive)
      formData.append('admin_email', adminEmail.trim().toLowerCase())
      formData.append('admin_password', adminPassword)
      if (telegramId.trim()) formData.append('telegram_id', telegramId.trim())
      const response = await systemApi.bootstrapMnbc(formData, bootstrapSecret.trim())
      setResult(response.data)
      setBootstrapSecret('')
      setAdminPassword('')
      setConfirmPassword('')
      toast.success('Setup awal dan import MNBC berhasil')
    } catch (error: unknown) {
      toast.error(apiErrorMessage(error, 'Setup awal gagal'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-5 py-10">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white"><HardHat size={22} /></div>
            <div>
              <div className="font-bold text-slate-950">DigiCom PMIS</div>
              <div className="text-xs text-slate-500">Setup awal dataset MNBC</div>
            </div>
          </div>
          <Link href="/login" className="btn-secondary">Kembali ke login</Link>
        </div>

        <div className="card overflow-hidden">
          <div className="border-b border-slate-100 bg-slate-950 p-7 text-white">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/10"><Database size={23} /></div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">First-time setup</p>
                <h1 className="mt-1 text-2xl font-bold">Masukkan proyek MNBC dari website</h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Form ini membuat akun administrator dan mengimpor satu proyek MNBC. Gunakan bootstrap secret yang sama dengan konfigurasi backend.
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={submit} className="space-y-6 p-7">
            <div className="grid gap-5 md:grid-cols-2">
              <label className="block md:col-span-2">
                <span className="label">files.zip MNBC</span>
                <input
                  type="file"
                  accept=".zip,application/zip"
                  className="input"
                  onChange={(event) => setDataset(event.target.files?.[0] || null)}
                  required
                />
                {dataset && <span className="mt-2 flex items-center gap-1.5 text-xs text-slate-500"><FileArchive size={13} />{dataset.name} · {(dataset.size / 1024 / 1024).toFixed(2)} MB</span>}
              </label>

              <label className="block md:col-span-2">
                <span className="label">Bootstrap secret</span>
                <div className="relative">
                  <KeyRound size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input type="password" value={bootstrapSecret} onChange={(event) => setBootstrapSecret(event.target.value)} className="input pl-9" autoComplete="off" required />
                </div>
                <span className="mt-1.5 block text-xs text-slate-400">Nilai ini berasal dari BOOTSTRAP_SECRET backend dan tidak disimpan oleh browser.</span>
              </label>

              <label className="block">
                <span className="label">Email administrator</span>
                <div className="relative">
                  <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input type="email" value={adminEmail} onChange={(event) => setAdminEmail(event.target.value)} className="input pl-9" required />
                </div>
              </label>
              <label className="block">
                <span className="label">Telegram ID staf (opsional)</span>
                <div className="relative">
                  <Send size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input value={telegramId} onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, ''))} inputMode="numeric" className="input pl-9" placeholder="770910605" />
                </div>
              </label>
              <label className="block">
                <span className="label">Password administrator</span>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input type="password" value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} className="input pl-9" minLength={12} required />
                </div>
              </label>
              <label className="block">
                <span className="label">Ulangi password</span>
                <div className="relative">
                  <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="input pl-9" minLength={12} required />
                </div>
              </label>
            </div>

            <div className="rounded-lg border border-cyan-100 bg-cyan-50 p-3 text-xs leading-5 text-cyan-800">
              ZIP asli diproses di browser dan diperkecil otomatis sebelum dikirim. Hanya tiga berkas AI yang dibutuhkan importer yang diunggah.
            </div>

            <button disabled={loading} className="btn-primary w-full justify-center py-3">
              {loading ? <Loader2 size={17} className="animate-spin" /> : <Database size={17} />}
              {loading ? 'Menyiapkan dan mengimpor data...' : 'Buat admin dan import MNBC'}
            </button>
          </form>
        </div>

        {result && (
          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-6">
            <div className="flex gap-3">
              <CheckCircle2 size={24} className="shrink-0 text-emerald-600" />
              <div>
                <h2 className="font-semibold text-emerald-950">Setup berhasil</h2>
                <p className="mt-1 text-sm text-emerald-800">{result.project_name}</p>
                <p className="mt-2 text-xs leading-5 text-emerald-700">
                  {result.tasks_upserted} task · {result.nodes_upserted} node · {result.relationships_upserted} relasi · {result.rules_upserted} rule · {result.reasoning_examples_upserted} reasoning
                </p>
                <Link href="/login" className="btn-primary mt-4 inline-flex">Masuk ke sistem</Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
