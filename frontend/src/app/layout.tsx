'use client'
import './globals.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { useEffect } from 'react'
import { useAuthStore } from '@/lib/store'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

function AuthLoader({ children }: { children: React.ReactNode }) {
  const fetchMe = useAuthStore((s) => s.fetchMe)
  useEffect(() => { fetchMe() }, [fetchMe])
  return <>{children}</>
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" data-scroll-behavior="smooth">
      <head>
        <title>Rencanix | Intelligent Project Control</title>
        <meta name="description" content="Platform pengendalian proyek, kolaborasi, pelaporan, dan analitik berbasis AI." />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          <AuthLoader>
            {children}
            <Toaster
              position="top-right"
              toastOptions={{
                style: {
                  borderRadius: '10px',
                  fontFamily: 'Sora, sans-serif',
                  fontSize: '14px',
                },
              }}
            />
          </AuthLoader>
        </QueryClientProvider>
      </body>
    </html>
  )
}
