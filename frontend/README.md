# 🖥️ AI CPMIS — Frontend Dashboard

Dashboard UI Next.js untuk sistem manajemen proyek konstruksi.

---

## 📁 Struktur Halaman

```
src/app/
├── login/          → Halaman login
├── dashboard/      → Overview: stats, charts, ringkasan
├── projects/       → Daftar proyek + detail proyek
│   └── [id]/       → Detail proyek, divisi, tasks
├── tasks/          → Kanban board semua task
├── reports/        → Laporan harian + AI summarize
├── ai-chat/        → Chat bebas dengan AI
└── users/          → Manajemen pengguna (admin/director)
```

---

## 🚀 Cara Menjalankan

```bash
# 1. Install dependencies
npm install

# 2. Setup environment
cp .env.local.example .env.local
# Isi: NEXT_PUBLIC_API_URL=http://localhost:8000

# 3. Jalankan backend dulu (pastikan berjalan di port 8000)

# 4. Jalankan frontend
npm run dev

# Buka: http://localhost:3000
```

---

## ✨ Fitur UI

### Login Page
- Split layout: branding kiri + form kanan
- One-click demo credentials
- Auto-redirect jika sudah login

### Dashboard Overview
- Stat cards: total proyek, task, overdue, laporan
- Bar chart progress per proyek (Recharts)
- Pie chart distribusi status task
- Tabel proyek terkini + laporan terbaru

### Kanban Board
- 5 kolom: Belum Mulai → Dikerjakan → Tinjauan → Selesai → Terhambat
- Pindah status task langsung dari kartu
- Filter per proyek
- Badge AI Generated untuk task otomatis
- Indikator overdue merah

### Manajemen Proyek
- Grid card dengan progress bar
- Search & filter
- Modal buat proyek baru
- Halaman detail: info, divisi, semua task

### Laporan Harian
- Form lengkap: cuaca, pekerja, progress, kendala
- Ringkas dengan AI (satu klik)
- Tampil AI summary + deteksi risiko inline

### AI Chat
- Interface chat modern
- Pilih konteks proyek
- Suggestion prompts untuk konstruksi
- Typing indicator animasi

### Manajemen Pengguna
- Tabel lengkap: nama, role, kontak, status telegram
- Stat cards: total, aktif, terhubung Telegram

---

## 🔧 Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Styling:** Tailwind CSS
- **State:** Zustand (auth)
- **Data Fetching:** TanStack Query (React Query)
- **Charts:** Recharts
- **HTTP:** Axios (auto token refresh)
- **Auth:** JWT via cookies
- **Toast:** react-hot-toast
- **Icons:** Lucide React
- **Font:** Sora (Google Fonts)

---

## 🎨 Design System

```css
/* Warna utama */
--c-brand:   #0ea5e9   /* sky blue */
--c-success: #10b981   /* emerald */
--c-warning: #f59e0b   /* amber */
--c-danger:  #ef4444   /* red */

/* Komponen siap pakai (globals.css) */
.btn-primary    /* tombol utama */
.btn-secondary  /* tombol sekunder */
.card           /* container putih */
.input          /* input field */
.label          /* label form */
.badge-*        /* badge status */
```

---

## 📱 Responsif
- Sidebar fixed 240px di desktop
- Grid 1 kolom → 2 → 3 sesuai lebar layar
- Kanban board: horizontal scroll di mobile
