'use client'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { settingsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { FeatureFlag } from '@/types'
import { cn, rolePersona } from '@/lib/utils'
import NotificationBell from '@/components/ui/NotificationBell'
import UserAvatar from '@/components/ui/UserAvatar'
import {
  LayoutDashboard, FolderKanban, CheckSquare,
  FileText, Bot, Users, LogOut, ChevronRight,
  FolderOpen, ShieldCheck, Building, GitBranch, AlertTriangle,
  Workflow, MessageSquare, Radio, ClipboardCheck, History, FileDown,
  Inbox,
  ChartNoAxesCombined,
  ListChecks, Menu, Settings, X,
} from 'lucide-react'

type NavItem = {
  href: string
  label: string
  staffLabel?: string
  icon: typeof LayoutDashboard
  featureKey?: string
  projectAdminOnly?: boolean
  ownerOnly?: boolean
  ownerAllowed?: boolean
  executiveOnly?: boolean
  managementOnly?: boolean
  staffOnly?: boolean
  hideForStaff?: boolean
  subOnly?: boolean
  subAllowed?: boolean
}

const navSections: { title: string; items: NavItem[] }[] = [
  {
    title: 'Kerja harian',
    items: [
      { href: '/dashboard',      label: 'Home',            icon: LayoutDashboard, featureKey: 'dashboard', subAllowed: true },
      { href: '/tasks/division', label: 'Tugas Divisi',    icon: ListChecks, featureKey: 'tasks', staffOnly: true },
      { href: '/tasks',          label: 'Tugas',           icon: CheckSquare, featureKey: 'tasks', hideForStaff: true },
      { href: '/reports',        label: 'Laporan',         staffLabel: 'Laporan Saya', icon: FileText, featureKey: 'reports', subAllowed: true },
      { href: '/communications', label: 'Komunikasi',      staffLabel: 'Koordinasi Tugas', icon: Inbox, featureKey: 'communications', subAllowed: true },
      { href: '/approvals',      label: 'Approval',        icon: ClipboardCheck, featureKey: 'approvals', managementOnly: true },
    ],
  },
  {
    title: 'Proyek & data',
    items: [
      { href: '/projects',       label: 'Proyek',          staffLabel: 'Proyek Saya', icon: FolderKanban, featureKey: 'projects', subAllowed: true },
      { href: '/projects/tree',  label: 'Struktur Proyek', staffLabel: 'Struktur Divisi', icon: GitBranch, featureKey: 'project_tree' },
      { href: '/documents',      label: 'Dokumen',         staffLabel: 'Dokumen Kerja', icon: FolderOpen, featureKey: 'documents', subAllowed: true },
    ],
  },
  {
    title: 'Kontrol manager',
    items: [
      { href: '/controls',       label: 'Project Controls', icon: ChartNoAxesCombined, featureKey: 'controls', managementOnly: true },
      { href: '/risk',           label: 'Risiko',           icon: AlertTriangle, featureKey: 'risk', managementOnly: true },
      { href: '/compliance',     label: 'Compliance AI',    icon: ShieldCheck, featureKey: 'compliance', managementOnly: true },
    ],
  },
  {
    title: 'Integrasi & AI',
    items: [
      { href: '/ai-chat',        label: 'AI Assistant',     icon: Bot, featureKey: 'ai_chat', managementOnly: true },
      { href: '/telegram',       label: 'Telegram',         icon: MessageSquare, featureKey: 'telegram', managementOnly: true },
      { href: '/automation',     label: 'Automation',       icon: Workflow, featureKey: 'automation', managementOnly: true },
      { href: '/stakeholders',   label: 'Stakeholders',     icon: Users, featureKey: 'stakeholders', managementOnly: true },
    ],
  },
  {
    title: 'Admin & governance',
    items: [
      { href: '/subcontractor',  label: 'Portal Subkon',    icon: Building, featureKey: 'subcontractor', subOnly: true, subAllowed: true },
      { href: '/users',          label: 'Pengguna',         icon: Users, featureKey: 'users', projectAdminOnly: true },
      { href: '/admin',          label: 'Admin Proyek',     icon: Settings, featureKey: 'admin_console', projectAdminOnly: true },
      { href: '/owner',          label: 'Admin Owner',      icon: ShieldCheck, ownerOnly: true },
      { href: '/audit',          label: 'Audit Trail',      icon: History, featureKey: 'audit', managementOnly: true, ownerAllowed: true },
      { href: '/research',       label: 'Research Export',  icon: FileDown, featureKey: 'research', executiveOnly: true, ownerAllowed: true },
    ],
  },
]

export default function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuthStore()
  const navRef = useRef<HTMLElement>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const isOwner = user?.role === 'owner'
  const isProjectAdmin = user?.role === 'admin'
  const isManagement = isProjectAdmin || user?.role === 'director' || user?.role === 'manager'
  const isStaff = user?.role === 'staff'
  const isSub    = user?.role === 'subcontractor'
  const persona = rolePersona(user?.role)
  const { data: featureFlags = [] } = useQuery<FeatureFlag[]>({
    queryKey: ['feature-flags'],
    queryFn: async () => (await settingsApi.features()).data,
    enabled: Boolean(user),
    staleTime: 60_000,
    retry: false,
  })
  const featureMap = useMemo(
    () => new Map(featureFlags.map((flag) => [flag.feature_key, flag.enabled])),
    [featureFlags],
  )
  const isFeatureVisible = (featureKey?: string) =>
    !featureKey || featureFlags.length === 0 || featureMap.get(featureKey) !== false
  const isNavItemVisible = (item: NavItem) => {
    if (isOwner) return (item.ownerOnly || item.ownerAllowed) && isFeatureVisible(item.featureKey)
    if (item.ownerOnly) return false
    if (item.projectAdminOnly && !isProjectAdmin) return false
    if (item.staffOnly && !isStaff) return false
    if (item.hideForStaff && isStaff) return false
    if (item.executiveOnly && !(isProjectAdmin || user?.role === 'director')) return false
    if (item.managementOnly && !isManagement) return false
    if (item.subOnly && !isSub) return false
    if (isSub && !item.subAllowed) return false
    return isFeatureVisible(item.featureKey)
  }

  useLayoutEffect(() => {
    const savedPosition = sessionStorage.getItem('digicom:sidebar-scroll')
    if (navRef.current && savedPosition) {
      navRef.current.scrollTop = Number(savedPosition)
    }
  }, [])

  const rememberScrollPosition = () => {
    if (navRef.current) {
      sessionStorage.setItem('digicom:sidebar-scroll', String(navRef.current.scrollTop))
    }
  }

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-30 flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 lg:hidden">
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => setMobileOpen(true)} className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white" aria-label="Buka menu">
            <Menu size={20} />
          </button>
          <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={130} height={40} className="h-8 w-auto rounded bg-white px-2 object-contain" priority />
        </div>
        <NotificationBell />
      </header>

      {mobileOpen && <button type="button" className="fixed inset-0 z-40 bg-slate-950/45 lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Tutup menu" />}

      <aside className={cn(
        'fixed left-0 top-0 z-50 flex h-full w-[240px] flex-col bg-slate-900 transition-transform duration-200 lg:z-40 lg:translate-x-0',
        mobileOpen ? 'translate-x-0' : '-translate-x-full',
      )}>
      <div className="border-b border-slate-800 px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-12 min-w-0 flex-1 items-center rounded-xl bg-white px-3 shadow-sm">
            <Image src="/brand/rencanix-logo.png" alt="Rencanix" width={360} height={110} className="h-auto w-full object-contain" priority />
          </div>
          <div className="ml-auto">
            <div className="hidden lg:block"><NotificationBell /></div>
            <button type="button" onClick={() => setMobileOpen(false)} className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-800 hover:text-white lg:hidden" aria-label="Tutup menu">
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-800/70 px-2 py-2 transition hover:bg-slate-800">
          <Link
            href="/profile"
            onClick={() => { rememberScrollPosition(); setMobileOpen(false) }}
            className="group flex min-w-0 flex-1 items-center gap-3 rounded-lg"
            title="Buka profil akun"
          >
            <UserAvatar user={user} size="sm" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-white">{user?.name}</div>
              <div className="truncate text-xs text-slate-400">{user ? persona.title : ''}</div>
            </div>
          </Link>
          <button onClick={logout} className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-700 hover:text-red-400" title="Keluar" aria-label="Keluar">
            <LogOut size={14} />
          </button>
        </div>
      </div>

      <nav
        ref={navRef}
        onScroll={rememberScrollPosition}
        className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto"
      >
        {navSections.map((section) => {
          const visibleItems = section.items.filter(isNavItemVisible)
          if (visibleItems.length === 0) return null
          return (
            <div key={section.title} className="mb-4">
              <p className="px-3 mb-2 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">{section.title}</p>
              <div className="space-y-0.5">
                {visibleItems.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(item.href + '/')
                  const itemLabel = isStaff && item.staffLabel ? item.staffLabel : item.label
                  return (
                    <Link key={item.href} href={item.href} onClick={() => { rememberScrollPosition(); setMobileOpen(false) }}
                      className={cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group',
                        active ? 'bg-brand-500 text-white shadow-glow' : 'text-slate-400 hover:text-white hover:bg-slate-800'
                      )}>
                      <item.icon size={17} className={active ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'} />
                      <span className="flex-1">{itemLabel}</span>
                      {active && <ChevronRight size={14} className="text-brand-200" />}
                    </Link>
                  )
                })}
              </div>
            </div>
          )
        })}
      </nav>

      <div className="px-3 pb-2">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
          <div className="flex items-center gap-2 font-semibold">
            <Radio size={13} className="text-emerald-300" />
            Sistem terhubung
          </div>
          <p className="mt-1 text-[11px] leading-4 text-emerald-100/70">Rencanix memantau layanan inti dan integrasi proyek secara real time.</p>
        </div>
      </div>
      </aside>
    </>
  )
}
