import AppShell from '@/components/layout/AppShell'

export default function TelegramLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>
}
