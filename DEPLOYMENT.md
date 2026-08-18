# Menjalankan dan Mendemokan CPMIS

CPMIS dirancang untuk menangani banyak proyek. Nama, kode, lokasi, akun tim,
task, dan Digital Twin dibentuk dari paket data proyek yang diunggah melalui
website; aplikasi tidak dikunci pada nama proyek tertentu.

## Aplikasi online

- Frontend: <https://cpmis-frontend.vercel.app>
- Backend API: <https://cpmisbackend.vercel.app>
- Setup awal: <https://cpmis-frontend.vercel.app/setup>

Frontend dan backend berjalan sebagai dua proyek Vercel. Data aplikasi
disimpan dalam Neon PostgreSQL dan file privat disimpan dalam Vercel Blob.
Karena itu, data tidak bergantung pada database atau folder lokal komputer.

## Setup proyek melalui website

Pada instalasi pertama, buka halaman **Setup** untuk membuat satu Admin Proyek
dan satu wadah proyek kosong. Tahap ini tidak mengimpor dataset, dokumen,
pegawai, divisi, atau task.

Setelah Admin Proyek memverifikasi email dan login, lakukan import paket ZIP
melalui **Admin Console → Import Project Dataset**. Paket ZIP harus memuat
berkas inti berikut:

- `30_AI_Training_Dataset_Master.json`;
- `30_AI_Knowledge_Graph.json`;
- `30_AI_Instruction_Dataset.jsonl` (opsional).

Daftar pegawai diimpor secara terpisah dari menu **Pengguna**. Password tidak
disimpan di dataset CSV. Register kredensial proyek dibuat setelah Admin
Proyek meninjau akun, lalu password acak hanya ditampilkan melalui dokumen
rahasia yang dihasilkan sistem.

Dataset proyek, daftar akun, register kredensial, dan paket demo tidak
disertakan dalam source archive. Simpan seluruh data operasional di lokasi
terpisah yang aman.

## Alur AI saat demo

AI bekerja saat dokumen proyek diunggah, bukan saat akun dibuat. Halaman
Documents menampilkan tahapan unggah ke cloud, pembacaan dan pengindeksan,
analisis AI, serta penyimpanan hasil ke database. Akun role dan pembagian task
dibentuk dari paket proyek dengan aturan yang konsisten agar hasil demo dapat
ditelusuri.

Model serverless dikonfigurasi hanya di backend:

```env
AI_DEFAULT_PROVIDER=mlapi
AI_DEFAULT_MODEL=nemotron-3-ultra
MLAPI_API_KEY=<API-key-model-library>
MLAPI_MODELS_JSON={"nemotron-3-ultra":{"label":"Nemotron 3 Ultra","url":"https://mlapi.run/ENDPOINT_MODEL_AKTIF","payload_style":"messages","include_model":false}}
```

API key tidak boleh dimasukkan ke kode frontend atau dikirim ke browser.

## Demo Telegram

Pastikan Telegram ID akun sudah terhubung, lalu:

1. kirim `/start` dan `/tasks` kepada bot;
2. pilih task yang akan diperbarui;
3. kirim progres, jumlah pekerja, cuaca, kendala, dan foto bukti bila diperlukan;
4. kirim `/submit`;
5. buka halaman **Reports** pada website.

Laporan Telegram akan tampil pada website karena bot dan dashboard memakai
database PostgreSQL yang sama. Laporan tetap melalui proses pemeriksaan dan
persetujuan sebelum mengubah progres resmi proyek.

## Menjalankan secara lokal

Backend menggunakan Python 3.14:

```powershell
cd C:\Users\User\CPMIS-Project\backend
Copy-Item .env.example .env
uv sync --dev
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd C:\Users\User\CPMIS-Project\frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Untuk pengembangan lokal, SQLite dan penyimpanan lokal/MinIO dapat dipakai.
Production harus menggunakan PostgreSQL dan object storage persisten.

## Environment production utama

Backend memerlukan `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, `SECRET_KEY`,
`BOOTSTRAP_SECRET`, konfigurasi model AI, token Telegram, webhook secret,
`PUBLIC_BASE_URL`, dan `ALLOWED_ORIGINS`. Frontend memerlukan:

```env
NEXT_PUBLIC_API_URL=https://cpmisbackend.vercel.app
```

Pada Vercel, Telegram memakai webhook, bukan polling. Endpoint webhook aktif:

```text
https://cpmisbackend.vercel.app/api/v1/telegram/webhook
```

Status transport Telegram dapat diperiksa melalui:

```text
https://cpmisbackend.vercel.app/api/v1/telegram/webhook/health
```
