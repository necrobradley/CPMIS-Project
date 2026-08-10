'use client'
import { useState, useRef, useEffect, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Cookies from 'js-cookie'
import { notificationsApi } from '@/lib/api'
import { Notification } from '@/types'
import {
  Bell, X, CheckCheck, AlertTriangle, Info, Clock, AlertCircle,
  AtSign, ClipboardCheck, FileCheck2, MessageSquare, RadioTower, RefreshCw,
} from 'lucide-react'
import { timeAgo } from '@/lib/utils'

const TYPE_ICON: Record<string, ReactNode> = {
  alert:         <AlertCircle size={14} className="text-rose-500" />,
  warning:       <AlertTriangle size={14} className="text-amber-500" />,
  info:          <Info size={14} className="text-cyan-500" />,
  deadline:      <Clock size={14} className="text-orange-500" />,
  communication: <MessageSquare size={14} className="text-cyan-600" />,
  mention:       <AtSign size={14} className="text-violet-500" />,
  approval:      <ClipboardCheck size={14} className="text-emerald-600" />,
  review:        <FileCheck2 size={14} className="text-blue-600" />,
  report_status: <FileCheck2 size={14} className="text-emerald-600" />,
  escalation:    <RadioTower size={14} className="text-rose-500" />,
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const qc  = useQueryClient()
  const hasToken = Boolean(Cookies.get('access_token'))

  const { data: count = 0, isError: countError } = useQuery<number>({
    queryKey: ['notif-count'],
    queryFn: async () => (await notificationsApi.unreadCount()).data.count,
    enabled: hasToken,
    retry: false,
    refetchInterval: 30_000,
  })

  const { data: notifications = [], isError: listError, isLoading } = useQuery<Notification[]>({
    queryKey: ['notifications'],
    queryFn: async () => (await notificationsApi.list()).data,
    enabled: open && hasToken,
    retry: false,
  })

  const markRead = useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notif-count'] })
    },
  })

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      qc.invalidateQueries({ queryKey: ['notif-count'] })
    },
  })

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition"
        aria-label="Buka notifikasi"
        title="Notifikasi"
      >
        <Bell size={18} />
        {hasToken && count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 bg-cyan-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center ring-2 ring-white">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 w-80 bg-white rounded-2xl shadow-2xl border border-slate-100 z-50 animate-in overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <span className="font-semibold text-slate-800 text-sm">Notifikasi</span>
            <div className="flex items-center gap-2">
              {count > 0 && (
                <button
                  onClick={() => markAll.mutate()}
                  className="text-xs text-brand-500 hover:text-brand-700 flex items-center gap-1"
                >
                  <CheckCheck size={12} /> Baca semua
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X size={14} />
              </button>
            </div>
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-slate-50">
            {countError || listError ? (
              <div className="py-10 px-5 text-center text-sm text-slate-500">
                <RefreshCw size={24} className="mx-auto mb-2 text-slate-300" />
                Notifikasi belum tersambung. Coba muat ulang setelah koneksi API aktif.
              </div>
            ) : isLoading ? (
              <div className="py-10 text-center text-sm text-slate-400">
                <RefreshCw size={24} className="mx-auto mb-2 text-slate-300 animate-spin" />
                Memuat notifikasi
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-10 text-center text-sm text-slate-400">
                <Bell size={24} className="mx-auto mb-2 text-slate-300" />
                Tidak ada notifikasi
              </div>
            ) : (
              notifications.map(n => (
                <button
                  key={n.id}
                  onClick={() => { if (!n.is_read) markRead.mutate(n.id) }}
                  className={`w-full text-left px-4 py-3 hover:bg-slate-50 transition flex gap-3 ${!n.is_read ? 'bg-brand-50/50' : ''}`}
                >
                  <div className="mt-0.5 flex-shrink-0">
                    {TYPE_ICON[n.type] ?? <Info size={14} className="text-slate-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-medium truncate ${!n.is_read ? 'text-slate-900' : 'text-slate-600'}`}>
                      {n.title}
                    </div>
                    <div className="text-xs text-slate-400 line-clamp-2 mt-0.5">{n.message}</div>
                    <div className="text-[10px] text-slate-300 mt-1">{timeAgo(n.created_at)}</div>
                  </div>
                  {!n.is_read && <div className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0 mt-1.5" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
