# Rencanix (Construction Project Management Information System)

Rencanix adalah platform pengendalian proyek konstruksi berbasis web yang
menyatukan struktur proyek, WBS, pembagian tugas, pelaporan lapangan,
persetujuan, dokumen, komunikasi, pengendalian biaya, integrasi Telegram, dan
analitik berbantuan AI dalam satu sistem multi-proyek.

Repository resmi:

**[github.com/necrobradley/CPMIS-Project](https://github.com/necrobradley/CPMIS-Project)**

## Aplikasi online

- Frontend: [cpmis-frontend.vercel.app](https://cpmis-frontend.vercel.app)
- Backend API: [cpmisbackend.vercel.app](https://cpmisbackend.vercel.app)
- API documentation: [cpmisbackend.vercel.app/docs](https://cpmisbackend.vercel.app/docs)
- Telegram webhook health: [cpmisbackend.vercel.app/api/v1/telegram/webhook/health](https://cpmisbackend.vercel.app/api/v1/telegram/webhook/health)

> Alamat deployment dapat berubah jika project Vercel dipindahkan. Gunakan
> `PUBLIC_BASE_URL`, `FRONTEND_URL`, dan `NEXT_PUBLIC_API_URL` untuk menyesuaikan
> alamat tanpa mengubah source code.

## Tujuan sistem

Rencanix dirancang agar pekerjaan operasional tetap berjalan ketika layanan AI
tidak tersedia. Data inti disimpan di database dan dihitung secara
deterministik. AI berperan sebagai lapisan analisis dan rekomendasi, bukan
sebagai satu-satunya mesin operasional sistem.

Kemampuan utama meliputi:

- pengelolaan banyak proyek dengan isolasi data dan entitlement fitur;
- struktur WBS, divisi, task, requirement, material, dependency, dan baseline;
- pengaturan satu Admin Proyek untuk satu proyek;
- pengelolaan paket dan fitur proyek oleh satu Admin Owner;
- import dataset proyek terstruktur melalui website;
- import daftar pegawai, rekomendasi role, dan pembuatan akun proyek;
- register kredensial anggota dalam dokumen Word dengan password acak;
- assignment task kepada PIC oleh pihak yang berwenang;
- laporan harian melalui website dan Telegram;
- unggah foto dan dokumen sebagai evidence task;
- validasi, revisi, review, approval, dan audit trail;
- Project Controls, progress, cost, material approval, inspection, NCR, dan
  closeout;
- pusat dokumen, RAG, analisis dokumen, compliance, dan AI Assistant;
- dashboard berbasis data database dengan pembaruan berkala.

## Model akses dan peran

| Peran | Tanggung jawab utama |
|---|---|
| Admin Owner | Mengelola paket, entitlement, feature flag, kesiapan layanan, proyek aktif, dan reset data. Hanya ada satu akun. |
| Admin Proyek | Mewakili tepat satu proyek serta mengelola dataset, divisi, akun, dan administrasi proyek tersebut. |
| Director/Management | Memantau kinerja lintas area, risiko, komunikasi, dan approval sesuai akses proyek. |
| Ketua Divisi/Manager | Mengatur pekerjaan divisi, menentukan PIC, meninjau laporan, dan melakukan keputusan operasional. |
| Staff/PIC | Menjalankan task yang di-assign dan mengirim progres beserta evidence. |
| Subcontractor | Melaporkan pekerjaan yang menjadi assignment langsungnya sesuai batas akses. |

Role aplikasi dan role proyek merupakan dua konsep berbeda. Role aplikasi
menentukan tingkat akses umum, sedangkan role proyek menjelaskan jabatan dan
tanggung jawab seseorang dalam proyek tertentu.

## Data deterministik dan fitur AI

### Proses yang tidak membutuhkan AI

- import ZIP dataset proyek terstruktur;
- pembuatan struktur proyek, WBS, divisi, task, dan requirement dari dataset;
- autentikasi dan pembatasan hak akses;
- assignment task dan workflow approval;
- perhitungan dashboard, progres, biaya, overdue, dan Project Controls;
- penyimpanan laporan, foto, dokumen, dan audit trail;
- fallback pemetaan posisi dan parser laporan Telegram berbasis aturan.

### Proses yang menggunakan model AI

- analisis teks dokumen PDF, DOCX, dan XLSX;
- ekstraksi scope, milestone, requirement, risiko, dan konteks kontrak;
- rekomendasi task dari hasil analisis dokumen;
- rekomendasi role proyek berdasarkan posisi pegawai;
- ringkasan dan deteksi risiko laporan;
- compliance analysis;
- AI Assistant dan pembacaan laporan Telegram berformat bebas.

Import dataset tidak sama dengan inferensi AI. Dataset sudah dinormalisasi dan
diimpor secara deterministik. Task yang benar-benar dibuat dari hasil model
memiliki penanda sumber AI/dokumen agar dapat dibedakan dari Dataset Import.

Foto Telegram saat ini disimpan sebagai evidence. Analisis isi visual foto,
face detection, OCR untuk PDF hasil scan, dan analisis video memerlukan model
vision/OCR tambahan.

## Arsitektur

```text
Browser / Telegram
        |
        v
Next.js frontend ---- FastAPI backend ---- PostgreSQL / SQLite
                            |                    |
                            |                    +-- data proyek dan audit
                            |
                            +-- Object storage (Vercel Blob / MinIO)
                            +-- AI provider (MLAPI/Nemotron atau provider lain)
                            +-- Email provider (Resend atau SMTP)
                            +-- Telegram Bot API
                            +-- n8n (opsional)
```

Production menggunakan dua project Vercel terpisah untuk frontend dan backend.
Database PostgreSQL dan object storage persisten harus digunakan agar data
tidak bergantung pada filesystem serverless.

## Teknologi

### Backend

- Python 3.14
- FastAPI 0.141
- SQLAlchemy 2
- PostgreSQL/Neon untuk production dan SQLite untuk pengembangan lokal
- Pydantic 2
- python-telegram-bot
- OpenAI-compatible client dan adapter endpoint MLAPI
- PyPDF, python-docx, dan parser XLSX untuk ekstraksi dokumen
- Pytest untuk pengujian

### Frontend

- Next.js 16 (App Router)
- React 19 dan TypeScript
- Tailwind CSS
- TanStack Query
- Zustand
- Axios
- Recharts
- React Hook Form dan Zod

## Struktur repository

```text
CPMIS-Project/
├── backend/          # FastAPI, model database, service, endpoint, dan tests
├── frontend/         # Next.js UI, komponen, API client, dan UI tests
├── n8n/              # Workflow integrasi opsional
├── README.md         # Dokumentasi utama
├── DEPLOYMENT.md     # Catatan deployment dan demo
├── CONTEXT.md        # Glosarium serta konteks domain pengembangan
└── .gitignore
```

## Prasyarat lokal

- Git
- Python 3.14
- [uv](https://docs.astral.sh/uv/) atau `pip`
- Node.js 20 atau lebih baru
- npm
- PostgreSQL jika ingin meniru production; SQLite cukup untuk pengembangan
  dasar

Docker tidak wajib. Dockerfile disediakan untuk lingkungan yang memilih
container, sedangkan pengembangan dan deployment Vercel dapat dilakukan tanpa
Docker.

## Instalasi

### 1. Clone repository

```bash
git clone https://github.com/necrobradley/CPMIS-Project.git
cd CPMIS-Project
```

### 2. Jalankan backend

PowerShell:

```powershell
cd backend
Copy-Item .env.example .env
uv sync --dev
uv run uvicorn app.main:app --reload --port 8000
```

Alternatif menggunakan `pip`:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend tersedia di `http://localhost:8000` dan dokumentasi OpenAPI tersedia di
`http://localhost:8000/docs`.

### 3. Jalankan frontend

Buka terminal baru:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Frontend tersedia di `http://localhost:3000`.

`node_modules`, `.next`, `.venv`, dan cache tidak perlu disalin atau dimasukkan
ke repository karena semuanya dapat dibuat ulang dari lockfile.

## Environment Variables

Salin `backend/.env.example` menjadi `backend/.env` untuk lokal. Jangan commit
file `.env` asli.

### Backend inti

```env
DEBUG=true
SECRET_KEY=CHANGE_ME_TO_A_LONG_RANDOM_SECRET
PUBLIC_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
ALLOWED_ORIGINS=["http://localhost:3000"]
DATABASE_URL=sqlite:///./cpmis_demo.db
DATABASE_INIT_ON_STARTUP=true
```

Production wajib menggunakan secret acak yang kuat serta database PostgreSQL
persisten.

### Frontend

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Jangan pernah memasukkan API key privat ke variabel `NEXT_PUBLIC_*`, karena
nilainya akan dikirim ke browser.

### Model AI melalui MLAPI

```env
AI_DEFAULT_PROVIDER=mlapi
AI_DEFAULT_MODEL=nemotron-3-ultra
AI_FALLBACK_PROVIDER=openai
AI_TIMEOUT_SECONDS=90

MLAPI_API_KEY=
MLAPI_MODEL=nemotron-3-ultra
MLAPI_BASE_URL=https://mlapi.run/ENDPOINT_MODEL_AKTIF
MLAPI_MODELS_JSON={"nemotron-3-ultra":{"label":"Nemotron 3 Ultra","url":"https://mlapi.run/ENDPOINT_MODEL_AKTIF","payload_style":"messages","include_model":false}}
MLAPI_PAYLOAD_STYLE=messages
MLAPI_INCLUDE_MODEL=false
```

API key hanya disimpan di backend. Status `AI configured` berarti konfigurasi
tersedia; kesiapan model tetap harus diverifikasi melalui inferensi nyata.
Endpoint yang merespons `404 Model not found` tidak dapat dipakai walaupun API
key valid.

Provider OpenAI-compatible lain tersedia melalui variabel `OPENAI_*`,
`GROQ_*`, `OPENROUTER_*`, `NVIDIA_*`, `GEMINI_*`, dan provider lain yang
terdaftar pada backend. Runtime failover harus diuji sebelum dipakai untuk
production.

### Telegram

```env
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_AI_PARSE_ENABLED=true
TELEGRAM_WEBHOOK_SECRET=CHANGE_ME_TO_A_RANDOM_SECRET
BACKGROUND_WORKERS_ENABLED=true
```

- Lokal: `BACKGROUND_WORKERS_ENABLED=true` dapat menggunakan polling.
- Vercel: gunakan webhook dan set `BACKGROUND_WORKERS_ENABLED=false`.

Webhook production:

```text
https://cpmisbackend.vercel.app/api/v1/telegram/webhook
```

### Email transaksional

Gunakan Resend dengan domain terverifikasi atau SMTP menggunakan App Password.
Jangan memakai password utama akun email.

```env
RESEND_API_KEY=
EMAIL_FROM=Rencanix <noreply@example.com>

# Alternatif SMTP
SMTP_HOST=
SMTP_PORT=465
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_SSL=true
SMTP_FROM=
```

### Penyimpanan file

Pengembangan lokal dapat menggunakan MinIO. Production menggunakan object
storage persisten, misalnya Vercel Blob, melalui token yang disimpan di ENV
backend.

## Setup dan alur data proyek

### 1. Admin Owner

Admin Owner adalah akun tunggal untuk mengelola paket dan fitur per proyek.
Akun ini tidak membuat akun pegawai dan tidak menggantikan Admin Proyek.

### 2. Admin Proyek pertama

Halaman Setup membuat satu Admin Proyek dan satu wadah proyek kosong. Tahap ini
tidak mengimpor dokumen, pegawai, divisi, atau task.

### 3. Import dataset proyek

Login sebagai Admin Proyek, lalu buka Admin Console dan impor paket ZIP. Paket
proyek minimal memuat:

```text
30_AI_Training_Dataset_Master.json
30_AI_Knowledge_Graph.json
30_AI_Instruction_Dataset.jsonl   # opsional
```

Import pertama mengisi proyek kosong dan mengadopsi identitas proyek dari ZIP.
Import ulang dengan identitas proyek yang sama memperbarui data yang dapat
dikenali; ZIP proyek berbeda ditolak agar proyek aktif tidak tertimpa.

### 4. Import akun pegawai

Daftar pegawai diimpor terpisah dari menu Pengguna menggunakan CSV dengan
kolom berikut:

```csv
name,email,position,division_name,project_role
```

`position`, `division_name`, dan `project_role` dapat ditinjau sebelum commit.
Jika AI tidak tersedia, sistem menggunakan fallback berbasis katalog dan hasil
tetap wajib diperiksa Admin Proyek.

Password tidak disimpan dalam dataset CSV. Register kredensial dibuat secara
terpisah dan merotasi password anggota menjadi password acak yang aktif.

### 5. Dokumen sumber dan AI

Dokumen sumber diunggah melalui Pusat Dokumen. Jika opsi analisis AI dipilih,
alur berjalan sebagai berikut:

```text
Upload file
→ simpan ke object storage
→ ekstraksi teks
→ indeks RAG
→ analisis model AI
→ simpan hasil ke database
→ review rekomendasi
→ terapkan perubahan yang disetujui
```

## Alur laporan Telegram

1. Hubungkan Telegram ID pengguna dari website.
2. Ketua Divisi atau pihak berwenang meng-assign task kepada PIC.
3. PIC mengirim `/report` kepada bot.
4. Bot hanya menampilkan task yang menjadi assignment langsung pengguna.
5. PIC memilih task dan membaca target, WBS, lokasi, requirement, serta jumlah
   evidence yang diwajibkan.
6. PIC mengirim teks laporan sesuai detail task.
7. PIC mengirim foto/dokumen setelah report dipilih.
8. PIC mengirim `/submit`.
9. Reviewer memeriksa, meminta revisi, atau menyetujui laporan dari website.

Foto atau dokumen yang dikirim sebelum report dipilih akan ditolak. Memilih
report baru membuka sesi evidence baru sehingga bukti laporan lama tidak ikut
dihitung.

Perintah yang tersedia antara lain:

```text
/start
/help
/tasks
/report
/summary
/status
/ai
/submit
```

## Pengujian

Backend:

```powershell
cd backend
uv run pytest -q
```

Jika menggunakan virtual environment biasa:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
cd frontend
npm run lint
npm run test:api-errors
npm run build
```

Sebelum presentasi, uji minimal login lintas role, import dataset, import akun,
assignment task, laporan Telegram dengan evidence, approval, perubahan progres,
analisis dokumen AI, dan isolasi proyek.

## Deployment Vercel

Frontend dan backend di-link ke project Vercel yang berbeda.

Backend:

```powershell
cd backend
npx vercel deploy --prod
```

Frontend:

```powershell
cd frontend
npx vercel deploy --prod
```

Atur Environment Variables melalui dashboard Vercel masing-masing. Mengubah
ENV production memerlukan deployment baru agar function memakai nilai terbaru.

Setelah deploy, periksa:

```text
GET /api/v1/system/status
GET /api/v1/telegram/webhook/health
```

Detail tambahan tersedia pada [DEPLOYMENT.md](DEPLOYMENT.md).

## Menyiapkan `project_code.zip`

Sertakan source berikut:

```text
README.md
DEPLOYMENT.md
CONTEXT.md
.gitignore
backend/
frontend/
n8n/
```

Dataset proyek dan daftar akun tidak disertakan dalam source archive. Gunakan
dataset milik organisasi atau fixture pengujian non-produksi secara terpisah.

Jangan sertakan:

```text
.git/
.env
.env.local
node_modules/
.next/
.venv/
.vercel/
.pytest_cache/
__pycache__/
*.db
*.sqlite
uploads/
importtime.log
```

Periksa ZIP sebelum diunggah untuk memastikan tidak ada API key, token bot,
password database, SMTP password, bootstrap secret, atau kredensial pengguna.

## Keamanan

- Simpan seluruh secret di Environment Variables backend.
- Jangan commit `.env` atau dokumen register password.
- Gunakan secret yang berbeda untuk JWT, bootstrap, Telegram webhook, dan n8n.
- Gunakan domain email terverifikasi dan App Password untuk SMTP.
- Terapkan prinsip least privilege pada role dan project membership.
- Review hasil AI sebelum menjadikannya perubahan resmi proyek.
- Gunakan PostgreSQL dan object storage persisten untuk production.
- Rotasi credential jika pernah muncul dalam log, screenshot, chat, atau commit.

## Troubleshooting singkat

### `Model not found`

API key dapat valid tetapi endpoint model sudah tidak aktif. Uji inferensi nyata,
periksa URL model, versi deployment, dan provider fallback. Mengubah prompt
tidak memperbaiki endpoint yang mengembalikan HTTP 404.

### Dashboard tetap terisi saat AI mati

Ini merupakan perilaku yang diharapkan. Dashboard membaca database dan rumus
sistem. Label `AI demo` atau `source: demo_dataset` menunjukkan data demonstrasi,
bukan inferensi live.

### Telegram tidak menampilkan task

Pastikan Telegram ID sudah terhubung dan task telah di-assign langsung kepada
akun tersebut. Jalankan `/report` baru dan jangan memakai tombol dari pesan
lama.

### Email tidak diterima

Periksa konfigurasi provider, verified sender/domain, folder spam, dan log
backend. Untuk Gmail/Outlook SMTP gunakan App Password.

## Kontribusi dan pengembangan

Gunakan branch terpisah untuk perubahan:

```bash
git checkout -b codex/nama-perubahan
git add .
git commit -m "Jelaskan perubahan"
git push -u origin codex/nama-perubahan
```

Jalankan pengujian backend dan frontend sebelum membuat pull request. Hindari
memasukkan perubahan hasil build, dependency folder, cache, database lokal,
atau secret ke commit.

---

Rencanix dikembangkan sebagai platform pengendalian proyek dan objek penelitian
akademik. Dokumentasi, dataset demo, serta hasil AI perlu ditinjau sesuai konteks
organisasi dan ketentuan proyek sebelum digunakan untuk keputusan operasional
nyata.
