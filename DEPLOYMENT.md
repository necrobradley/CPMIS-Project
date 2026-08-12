# Menjalankan dan Men-deploy AI CPMIS

Repositori ini berisi dua aplikasi yang dideploy sebagai dua proyek Vercel dari
repositori Git yang sama:

- `frontend/`: Next.js untuk dashboard CPMIS;
- `backend/`: FastAPI untuk database, AI, import MNBC, dan webhook Telegram.

Dataset `files.zip` tidak membuat proyek baru yang berbeda. Importer membaca
data MNBC-2025 tersebut dan membentuk **satu proyek** bernama *Pembangunan
Menara Nusantara Business Center (MNBC Tower)* di database CPMIS.

## 1. Menjalankan secara lokal

### Backend

```powershell
cd C:\Users\User\CPMIS-Project\backend
Copy-Item .env.example .env
```

Edit `.env`, kemudian isi sedikitnya:

```env
SECRET_KEY=<random-secret-minimal-48-karakter>
DATABASE_URL=sqlite:///./cpmis_demo.db
MLAPI_API_KEY=<API-key-dari-model-library>
DEMO_ADMIN_PASSWORD=<password-demo-minimal-12-karakter>
BOOTSTRAP_SECRET=<random-bootstrap-secret>
TELEGRAM_BOT_TOKEN=<token-dari-BotFather>
DEMO_TELEGRAM_ID=<telegram-id-user-lapangan>
```

Jangan menaruh API key atau token di file Python/TypeScript. `.env` sudah
diabaikan Git.

Instal dependensi dan jalankan backend:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd C:\Users\User\CPMIS-Project\frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Buka `http://localhost:3000/setup` untuk instalasi pertama. Pilih
`F:\Download\files.zip`, lalu isi `BOOTSTRAP_SECRET`, email/password admin, dan
Telegram ID staf. Setelah berhasil, masuk melalui halaman login.

Jika akun admin sudah tersedia, impor ulang dilakukan dari **Admin Console →
Import dataset proyek MNBC** tanpa memasukkan bootstrap secret. Importer
bersifat idempotent: impor ulang memperbarui satu proyek, 400 task, dan Digital
Twin tanpa menggandakan proyek.

## 2. Konfigurasi model serverless pada gambar

Endpoint Nemotron pada gambar sudah dicontohkan di `backend/.env.example`.
Konfigurasi dasarnya:

```env
AI_DEFAULT_PROVIDER=mlapi
AI_DEFAULT_MODEL=nemotron-3-ultra
MLAPI_API_KEY=<API-key-Anda>
MLAPI_MODELS_JSON={"nemotron-3-ultra":{"label":"Nemotron 3 Ultra","url":"https://mlapi.run/ea1a1990-0eee-4bb0-849b-b22b18ffa68f","payload_style":"messages","include_model":false}}
```

Jika akun yang sama menyediakan beberapa endpoint model, tambahkan semuanya ke
satu katalog. API key tetap satu dan tidak pernah dikirim ke browser:

```env
MLAPI_MODELS_JSON={"nemotron-3-ultra":{"label":"Nemotron 3 Ultra","url":"https://mlapi.run/ENDPOINT_NEMOTRON"},"model-kedua":{"label":"Model Kedua","url":"https://mlapi.run/ENDPOINT_MODEL_KEDUA"}}
```

Model yang sudah dikonfigurasi akan muncul pada dropdown halaman **AI
Assistant**. Untuk endpoint yang meminta satu string prompt, ubah
`payload_style` menjadi `prompt`. Pilihan lain yang didukung adalah `messages`
dan `input`.

Setelah `MLAPI_API_KEY` diisi, uji model langsung dari terminal:

```powershell
cd C:\Users\User\CPMIS-Project\backend
python -m scripts.test_ai_model --model nemotron-3-ultra
```

## 3. Deployment backend ke Vercel

Buat proyek Vercel pertama dengan **Root Directory** `backend`. FastAPI dibaca
melalui `backend/pyproject.toml`.

Production membutuhkan PostgreSQL yang persisten. SQLite hanya digunakan untuk
demo lokal karena filesystem fungsi serverless tidak persisten. Isi environment
variables Vercel backend, minimal:

```env
DEBUG=false
SECRET_KEY=<random-minimal-48-karakter>
PUBLIC_BASE_URL=https://nama-backend.vercel.app
DATABASE_URL=postgresql://...
ALLOWED_ORIGINS=["https://nama-frontend.vercel.app"]
BACKGROUND_WORKERS_ENABLED=false
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_WEBHOOK_SECRET=<random-secret>
BOOTSTRAP_SECRET=<random-secret>
MLAPI_API_KEY=<API-key>
AI_DEFAULT_PROVIDER=mlapi
AI_DEFAULT_MODEL=nemotron-3-ultra
MLAPI_MODELS_JSON=<katalog-model-JSON>
N8N_WEBHOOK_SECRET=<random-secret>
MINIO_ENDPOINT=<endpoint-object-storage>
MINIO_ACCESS_KEY=<access-key>
MINIO_SECRET_KEY=<secret-key>
MINIO_BUCKET_NAME=<bucket>
MINIO_SECURE=true
```

Deploy preview dan production:

```powershell
cd C:\Users\User\CPMIS-Project\backend
vercel
vercel --prod
```

Setelah frontend dan backend production aktif, buka
`https://nama-frontend.vercel.app/setup`. Pilih `files.zip`, lalu isi secret,
akun admin, dan Telegram ID melalui form website. Browser otomatis mengemas
ulang hanya tiga berkas AI yang diperlukan sehingga upload berada di bawah
batas request Vercel.

Endpoint setup menolak request jika secret salah. Setelah import berhasil,
rotasi `BOOTSTRAP_SECRET` agar setup awal tidak bisa dipakai ulang oleh pihak
lain. Impor berikutnya dilakukan setelah login melalui **Admin Console**.

### Mengaktifkan webhook Telegram

Vercel tidak menjalankan polling tanpa batas. Karena itu production menggunakan
webhook:

```powershell
cd C:\Users\User\CPMIS-Project\backend
$env:PUBLIC_BASE_URL='https://nama-backend.vercel.app'
$env:TELEGRAM_BOT_TOKEN='<token-bot>'
$env:TELEGRAM_WEBHOOK_SECRET='<secret-yang-sama-dengan-Vercel>'
python -m scripts.configure_telegram_webhook
```

Periksa statusnya melalui:

```text
GET https://nama-backend.vercel.app/api/v1/telegram/webhook/health
```

## 4. Deployment frontend ke Vercel

Buat proyek Vercel kedua dengan **Root Directory** `frontend`, lalu tambahkan:

```env
NEXT_PUBLIC_API_URL=https://nama-backend.vercel.app
```

Deploy:

```powershell
cd C:\Users\User\CPMIS-Project\frontend
vercel
vercel --prod
```

Setelah URL frontend tersedia, pastikan `ALLOWED_ORIGINS` pada proyek backend
memuat URL production frontend, kemudian redeploy backend.

## 5. Skenario demo Telegram

1. Jalankan `/start` dan `/tasks` pada bot.
2. Kirim laporan, misalnya:

   ```text
   Progress WBS MNBC.300.CL.L16.Z1.CL01 sudah 80%. Pekerja: 12. Cuaca: cerah. Kendala: tidak ada.
   ```

3. Bot membuat draft laporan pada task MNBC yang cocok.
4. Bila task meminta bukti, kirim foto dengan caption WBS, kemudian `/submit`.
5. Buka halaman **Reports** di dashboard. Draft Telegram langsung tampil karena
   bot dan dashboard membaca database yang sama.
6. Login sebagai administrator/manager, periksa laporan, lalu setujui. Progress
   task baru diterapkan ke kontrol proyek setelah laporan disetujui; mekanisme
   ini mencegah pesan Telegram yang belum diverifikasi langsung mengubah baseline.
