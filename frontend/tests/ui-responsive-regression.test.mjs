import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('Project Controls tidak memaksa delapan KPI pada lebar desktop biasa', () => {
  const controls = source('src/app/controls/page.tsx')
  assert.doesNotMatch(controls, /2xl:grid-cols-8/)
})

test('nilai KPI mempunyai perlindungan overflow untuk angka panjang', () => {
  const controls = source('src/app/controls/page.tsx')
  assert.match(controls, /metric-value/)
})

test('panel notifikasi desktop membuka ke area konten dan mobile dibatasi viewport', () => {
  const notifications = source('src/components/ui/NotificationBell.tsx')
  assert.doesNotMatch(notifications, /absolute right-0 top-10 w-80/)
  assert.match(notifications, /lg:left-full/)
  assert.match(notifications, /max-w-\[calc\(100vw-2rem\)\]/)
})

test('tautan bootstrap Admin Owner satu kali tidak ditampilkan pada setup proyek', () => {
  const setup = source('src/app/setup/page.tsx')
  assert.doesNotMatch(setup, /Bootstrap Admin Owner satu kali/)
})

test('semua logo halaman autentikasi mempunyai batas lebar konsisten', () => {
  const files = [
    'src/app/login/page.tsx',
    'src/app/forgot-password/page.tsx',
    'src/app/setup/page.tsx',
    'src/components/auth/AuthTokenPasswordForm.tsx',
    'src/components/auth/VerifyEmailClient.tsx',
    'src/components/ui/BrandLoadingScreen.tsx',
  ]

  for (const file of files) {
    assert.doesNotMatch(source(file), /className="h-auto w-full object-contain"/, file)
  }
})
