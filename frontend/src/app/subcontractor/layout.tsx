'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/lib/store'
import Sidebar from '@/components/layout/Sidebar'
import { Loader2 } from 'lucide-react'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthStore()
  const router = useRouter()
  useEffect(() => { if (!loading && !user) router.replace('/login') }, [user, loading, router])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <Loader2 size={32} className="animate-spin text-brand-500" />
    </div>
  )
  if (!user) return null

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-h-screen min-w-0 w-full bg-slate-50 pt-16 lg:ml-[240px] lg:w-[calc(100%_-_240px)] lg:pt-0">
        <div className="p-6 lg:p-8 max-w-[1400px] mx-auto">{children}</div>
      </main>
    </div>
  )
}
