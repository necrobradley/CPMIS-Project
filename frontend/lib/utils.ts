import { clsx, type ClassValue } from 'clsx'
import { format, formatDistanceToNow, isAfter } from 'date-fns'
import { id } from 'date-fns/locale'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return '—'
  return format(new Date(date), 'dd MMM yyyy', { locale: id })
}

export function formatDateTime(date: string | Date | null | undefined): string {
  if (!date) return '—'
  return format(new Date(date), 'dd MMM yyyy, HH:mm', { locale: id })
}

export function timeAgo(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true, locale: id })
}

export function isOverdue(deadline: string | Date | null | undefined): boolean {
  if (!deadline) return false
  return isAfter(new Date(), new Date(deadline))
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '—'
  return new Intl.NumberFormat('id-ID', {
    style: 'currency', currency: 'IDR', maximumFractionDigits: 0,
  }).format(value)
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('id-ID').format(n)
}

export function apiAssetUrl(path: string | null | undefined): string {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
}

export const STATUS_LABELS: Record<string, string> = {
  todo:        'Belum Mulai',
  in_progress: 'Sedang Dikerjakan',
  review:      'Tinjauan',
  done:        'Selesai',
  blocked:     'Terhambat',
  planning:    'Perencanaan',
  active:      'Aktif',
  on_hold:     'Ditahan',
  completed:   'Selesai',
  cancelled:   'Dibatalkan',
}

export const PRIORITY_LABELS: Record<string, string> = {
  low:      'Rendah',
  medium:   'Sedang',
  high:     'Tinggi',
  critical: 'Kritis',
}

export const ROLE_LABELS: Record<string, string> = {
  admin:          'Admin Aplikasi',
  director:       'Direktur',
  manager:        'Manajer',
  staff:          'Staff',
  subcontractor:  'Subkontraktor',
}

export const ROLE_PERSONAS: Record<string, { title: string; cue: string; gradient: string; badge: string }> = {
  admin: {
    title: 'System Owner',
    cue: 'Mengatur tenant, menu, akun, keamanan, dan konfigurasi aplikasi.',
    gradient: 'from-slate-800 via-cyan-700 to-emerald-600',
    badge: 'bg-cyan-50 text-cyan-700 border-cyan-100',
  },
  director: {
    title: 'Executive Sponsor',
    cue: 'Melihat keputusan besar, risiko, biaya, progres, dan eskalasi.',
    gradient: 'from-indigo-700 via-sky-600 to-emerald-500',
    badge: 'bg-indigo-50 text-indigo-700 border-indigo-100',
  },
  manager: {
    title: 'Project Command Lead',
    cue: 'Mengatur pekerjaan, approval, kontrol proyek, dan komunikasi lintas tim.',
    gradient: 'from-sky-700 via-blue-600 to-teal-500',
    badge: 'bg-sky-50 text-sky-700 border-sky-100',
  },
  staff: {
    title: 'Field Reporter',
    cue: 'Mengerjakan task, mengirim laporan harian, bukti foto, dan update blocker.',
    gradient: 'from-emerald-700 via-teal-600 to-cyan-500',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  },
  subcontractor: {
    title: 'External Work Partner',
    cue: 'Melaporkan progres paket kerja, dokumen, inspeksi, dan isu koordinasi.',
    gradient: 'from-amber-700 via-orange-600 to-rose-500',
    badge: 'bg-amber-50 text-amber-700 border-amber-100',
  },
}

export function rolePersona(role: string | null | undefined) {
  return ROLE_PERSONAS[role || 'staff'] ?? ROLE_PERSONAS.staff
}

export function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    todo:        'badge-gray',
    in_progress: 'badge-info',
    review:      'badge-warning',
    done:        'badge-success',
    blocked:     'badge-danger',
    active:      'badge-success',
    planning:    'badge-info',
    on_hold:     'badge-warning',
    completed:   'badge-success',
    cancelled:   'badge-danger',
  }
  return map[status] ?? 'badge-gray'
}

export function priorityBadgeClass(priority: string): string {
  const map: Record<string, string> = {
    low:      'badge-gray',
    medium:   'badge-info',
    high:     'badge-warning',
    critical: 'badge-danger',
  }
  return map[priority] ?? 'badge-gray'
}
