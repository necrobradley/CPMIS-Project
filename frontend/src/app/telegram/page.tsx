'use client'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Bell, Bot, CheckCircle2, MessageSquare, Radio, Send,
  Smartphone, UserCheck, Users,
} from 'lucide-react'
import { notificationsApi, systemApi, usersApi } from '@/lib/api'
import { Notification, User } from '@/types'
import { ROLE_LABELS, timeAgo } from '@/lib/utils'

type SystemStatus = {
  services?: Record<string, boolean>
}

export default function TelegramPage() {
  const [message, setMessage] = useState('Reminder: update laporan harian dan foto progress sebelum pukul 17:00 WIB.')
  const { data: userData } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: async () => (await usersApi.list()).data,
    refetchInterval: 30_000,
    retry: 1,
  })
  const { data: notificationData } = useQuery<Notification[]>({
    queryKey: ['notifications'],
    queryFn: async () => (await notificationsApi.list()).data,
    refetchInterval: 15_000,
    retry: 1,
  })
  const { data: systemData } = useQuery<SystemStatus>({
    queryKey: ['system-status'],
    queryFn: async () => (await systemApi.status()).data,
    refetchInterval: 15_000,
    retry: 1,
  })

  const users = userData ?? []
  const notifications = notificationData ?? []
  const connected = users.filter((user) => user.telegram_id)
  const telegramOnline = Boolean(systemData?.services?.telegram)
  const telegramEvents = useMemo(() => (
    notifications.filter((notification) => notification.sent_to_telegram).slice(0, 6)
  ), [notifications])

  return (
    <div className="space-y-7 animate-in">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-cyan-600">
            <MessageSquare size={14} />
            Telegram center
          </div>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Realtime field communication</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
            Monitor koneksi bot, pengguna yang sudah link Telegram, dan notifikasi yang terkirim ke lapangan.
          </p>
        </div>
        <span className={telegramOnline ? 'badge-success' : 'badge-warning'}>
          <Radio size={12} />
          {telegramOnline ? 'Bot online/ready' : 'Token belum diset'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
            <Bot size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{telegramOnline ? 'On' : 'Setup'}</div>
          <p className="mt-1 text-sm text-slate-500">Bot status</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
            <UserCheck size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{connected.length}/{users.length}</div>
          <p className="mt-1 text-sm text-slate-500">User connected</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-violet-700">
            <Bell size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">{telegramEvents.length}</div>
          <p className="mt-1 text-sm text-slate-500">Telegram events</p>
        </div>
        <div className="card p-5">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
            <Smartphone size={21} />
          </div>
          <div className="text-3xl font-bold text-slate-950">/ai</div>
          <p className="mt-1 text-sm text-slate-500">Bot command utama</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Connected users</h2>
            <span className="badge-info">{connected.length} aktif</span>
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {users.map((user) => (
              <div key={user.id} className="rounded-xl border border-slate-100 p-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                    {user.name.charAt(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="truncate text-sm font-semibold text-slate-900">{user.name}</h3>
                      {user.telegram_id ? <span className="badge-success">Linked</span> : <span className="badge-warning">Pending</span>}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{ROLE_LABELS[user.role]} - {user.email}</p>
                    <p className="mt-2 text-xs text-slate-500">Telegram ID: {user.telegram_id || 'belum terhubung'}</p>
                  </div>
                </div>
              </div>
            ))}
            {!users.length && (
              <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-400">
                Belum ada pengguna. Impor dataset MNBC terlebih dahulu.
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Broadcast draft</h2>
              <Send size={17} className="text-slate-300" />
            </div>
            <div className="space-y-3">
              <select className="input">
                <option>Semua user Telegram</option>
                <option>Manager dan director</option>
                <option>Staff lapangan</option>
              </select>
              <textarea
                className="input min-h-32 resize-none"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
              />
              <button
                className="btn-primary w-full justify-center"
                onClick={() => toast.success('Draft siap dikirim lewat workflow Telegram')}
              >
                <Send size={14} />
                Simpan draft
              </button>
            </div>
          </div>

          <div className="card p-6">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Event log</h2>
              <CheckCircle2 size={17} className="text-emerald-500" />
            </div>
            <div className="space-y-3">
              {telegramEvents.map((event) => (
                <div key={event.id} className="rounded-xl bg-slate-50 p-3">
                  <p className="text-sm font-medium text-slate-800">{event.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">{event.message}</p>
                  <p className="mt-2 text-[11px] text-slate-400">{timeAgo(event.created_at)}</p>
                </div>
              ))}
              {!telegramEvents.length && (
                <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-400">
                  Belum ada event Telegram.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
