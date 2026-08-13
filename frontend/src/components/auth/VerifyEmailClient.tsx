'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { CheckCircle2, Loader2, MailCheck, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

import { authApi } from '@/lib/api'
import { apiErrorMessage } from '@/lib/api-error'

const verificationRequests = new Map<string, ReturnType<typeof authApi.verifyEmail>>()

export default function VerifyEmailClient() {
  const token = useSearchParams().get('token') || ''
  const [state, setState] = useState<'loading' | 'success' | 'error'>(token ? 'loading' : 'error')
  const [message, setMessage] = useState(token ? 'Memverifikasi alamat email Anda...' : 'Token verifikasi tidak ditemukan pada tautan ini.')

  useEffect(() => {
    if (!token) return
    const request = verificationRequests.get(token) || authApi.verifyEmail(token)
    verificationRequests.set(token, request)
    request
      .then((response) => {
        setState('success')
        setMessage(response.data.message)
      })
      .catch((error: unknown) => {
        setState('error')
        setMessage(apiErrorMessage(error, 'Tautan verifikasi tidak valid atau sudah kedaluwarsa.'))
      })
  }, [token])

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-md animate-in">
        <div className="mb-8 flex h-16 items-center rounded-xl border border-slate-200 bg-white px-5"><Image src="/brand/rencanix-logo.png" alt="Rencanix" width={360} height={110} className="mx-auto h-auto w-full max-w-[240px] object-contain" priority /></div>
        <div className="card p-8 text-center">
          <div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-2xl ${state === 'success' ? 'bg-emerald-100 text-emerald-600' : state === 'error' ? 'bg-rose-100 text-rose-600' : 'bg-sky-100 text-sky-600'}`}>
            {state === 'loading' ? <Loader2 size={31} className="animate-spin" /> : state === 'success' ? <CheckCircle2 size={31} /> : <XCircle size={31} />}
          </div>
          <h1 className="mt-5 text-2xl font-bold text-slate-950">{state === 'loading' ? 'Verifikasi Email' : state === 'success' ? 'Email Terverifikasi' : 'Verifikasi Gagal'}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">{message}</p>
          {state !== 'loading' && <Link href="/login" className="btn-primary mt-6 w-full justify-center"><MailCheck size={17} /> Kembali ke login</Link>}
        </div>
      </div>
    </div>
  )
}
