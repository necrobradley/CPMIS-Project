# DigiCom PMIS - n8n Setup

n8n menjadi automation layer untuk notifikasi dan pekerjaan terjadwal. Keputusan validasi requirement dan approval utama tetap berada di backend agar alur PMIS tidak bergantung pada layanan eksternal.

## Workflow Tersedia

| Workflow | Trigger | Fungsi |
|---|---|---|
| Daily Report | `POST /webhook/daily-report` | Menerima laporan valid dan meneruskan notifikasi |
| Tender Analysis | `POST /webhook/tender-analysis` | Meneruskan hasil analisis tender |
| Stakeholder Task Reminder | Schedule harian | Meminta backend menyusun reminder task, membuat notifikasi web, mengirim Telegram, lalu callback status kirim |
| Weekly Summary | Schedule Jumat | Membuat ringkasan eksekutif |

File workflow berada di `n8n/workflows/`.

## Instalasi Lokal

Jalankan stack:

```powershell
docker compose -p digicom-pmis-prd -f docker-compose.prd.yml up -d --build
```

Pada volume n8n baru, import dan aktifkan workflow satu kali:

```powershell
docker exec digicom_pmis_prd_n8n n8n import:workflow --separate --input=/home/node/.n8n/workflows
docker exec digicom_pmis_prd_n8n n8n update:workflow --all --active=true
docker compose -p digicom-pmis-prd -f docker-compose.prd.yml restart n8n
```

Buka `http://localhost:5681` dengan akun lokal `admin / digicom1234`.

## Instalasi Production

Setelah stack production aktif:

```bash
docker compose -f docker-compose.public.yml exec n8n n8n import:workflow --separate --input=/home/node/.n8n/workflows
docker compose -f docker-compose.public.yml exec n8n n8n update:workflow --all --active=true
docker compose -f docker-compose.public.yml restart n8n
```

Workflow hanya perlu di-import lagi saat volume n8n baru dibuat atau file workflow berubah.

## Konfigurasi

Environment utama:

```text
CPMIS_BACKEND_URL=http://backend:8000
CPMIS_N8N_SECRET=<secret-production>
TELEGRAM_BOT_TOKEN=<token-opsional>
```

Untuk notifikasi Telegram, tambahkan credential Telegram di n8n dan isi `telegram_id` user. Tanpa token Telegram, workflow dan alur PMIS tetap aktif tetapi pengiriman pesan eksternal tidak berjalan.

## Reminder Task v2.6

Reminder task tidak lagi dihitung langsung di n8n. Backend CPMIS menjadi sumber aturan utama agar data, stakeholder, website notification, dan status Telegram konsisten.

Alur harian:

1. n8n menjalankan workflow `Workflow 3 - Stakeholder Task Reminder` jam 08:00 WIB.
2. n8n memanggil `POST /api/v1/n8n/reminders/prepare` dengan header `X-N8N-Secret`.
3. Backend mencari task `todo`, `in_progress`, `review`, dan `blocked` yang mendekati deadline, overdue, blocked, atau lama tidak di-update.
4. Backend menentukan stakeholder dari PIC task, pembuat task, owner proyek, manager divisi, project manager, director/admin untuk item critical, lalu membuat notifikasi website.
5. Backend mengembalikan payload Telegram hanya untuk user yang punya `telegram_id`.
6. n8n mengirim Telegram dan memanggil `POST /api/v1/n8n/reminders/delivered` untuk menandai `sent_to_telegram=true`.

Endpoint `prepare` mencegah spam dengan menggunakan notifikasi task/user/judul yang sudah dibuat pada hari yang sama. Jika Telegram belum terkirim, payload Telegram tetap dikembalikan sampai callback `delivered` berhasil.

## Uji Webhook

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:5681/webhook/daily-report `
  -ContentType 'application/json' `
  -Body '{"event":"daily_report_submitted","report_id":999,"project_id":1,"severity":"low","manager_telegram_ids":[]}'
```

Respons yang diharapkan:

```json
{"status":"received","report_id":999}
```

Uji backend reminder dari host/container backend:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8003/api/v1/n8n/reminders/prepare `
  -Headers @{ "X-N8N-Secret" = "cpmis-n8n-secret-2024" } `
  -ContentType 'application/json' `
  -Body '{"horizon_days":3,"include_stalled":true}'
```

Respons berisi `summary`, `reminders`, dan `telegram_messages`.

## Troubleshooting

- Cek container: `docker compose -p digicom-pmis-prd -f docker-compose.prd.yml ps`
- Cek daftar workflow: `docker exec digicom_pmis_prd_n8n n8n list:workflow`
- Cek log: `docker logs digicom_pmis_prd_n8n --tail 100`
- Di jaringan Docker, gunakan `http://backend:8000`, bukan `localhost`, untuk mengakses backend.
