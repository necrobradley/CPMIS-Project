# DigiCom PMIS - Public Deployment Guide

## Opsi Deploy

### Opsi A - VPS + Docker Compose + Caddy
Rekomendasi untuk pilot/tesis.

Yang Anda siapkan:
- VPS Ubuntu 22.04/24.04 atau Debian.
- Domain utama, contoh `pmis.domainanda.com`.
- DNS `A record`:
  - `pmis.domainanda.com` -> IP VPS
  - `files.pmis.domainanda.com` -> IP VPS
- SSH access ke VPS.
- Optional: `OPENAI_API_KEY` dan `TELEGRAM_BOT_TOKEN`.

Yang Codex bisa lakukan:
- Setup production compose.
- Setup Caddy HTTPS.
- Setup `.env`.
- Build dan start container.
- Seed database bila perlu.
- Smoke test login/API/halaman utama.

### Opsi B - Managed PaaS
Contoh: Railway, Render, Fly.io, DigitalOcean App Platform.

Kelebihan:
- Lebih mudah untuk publish app.
- SSL dan deploy biasanya otomatis.

Kekurangan:
- Stack ini punya banyak service: frontend, backend, PostgreSQL, MongoDB, MinIO, n8n.
- Biasanya perlu memecah layanan dan biaya bisa lebih tinggi.

### Opsi C - Cloud Production Terpisah
Untuk tahap scale-up.

Komponen:
- Frontend/backend container di server/app platform.
- Managed PostgreSQL.
- Managed object storage S3-compatible.
- MongoDB Atlas atau log store lain.
- n8n terpisah.
- Monitoring dan backup terpusat.

## File Production Yang Sudah Disiapkan

- `docker-compose.public.yml`
- `Caddyfile`
- `.env.public.example`
- `frontend/Dockerfile.prod`
- `SECURITY.md`
- `docs/security/Production_Security_Hardening.md`

## Security Gate Sebelum Public

Sebelum membuka aplikasi ke internet untuk customer atau data proyek real, selesaikan minimal P0 pada:

```text
docs/security/Production_Security_Hardening.md
```

Untuk pilot terbatas, boleh deploy dengan dummy data, tetapi jangan gunakan dokumen kontrak/proyek real sampai secret production, HTTPS, CORS, RBAC endpoint, upload policy, backup, dan demo fallback production sudah aman.

## Langkah Deploy Opsi A

1. Login ke VPS.
2. Install Docker dan Docker Compose.
3. Upload/copy folder `digicom-pmis-live` ke server.
4. Masuk ke folder project:

```bash
cd digicom-pmis-live
```

5. Buat file `.env` dari template:

```bash
cp .env.public.example .env
```

6. Edit `.env`:

```bash
nano .env
```

Wajib diganti:
- `APP_DOMAIN`
- `ACME_EMAIL`
- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `N8N_BASIC_AUTH_PASSWORD`
- `N8N_WEBHOOK_SECRET`

7. Jalankan stack:

```bash
docker compose -f docker-compose.public.yml up -d --build
```

8. Cek status:

```bash
docker compose -f docker-compose.public.yml ps
```

9. Seed data demo bila masih pilot:

```bash
docker compose -f docker-compose.public.yml exec backend python scripts/seed_db.py
```

10. Import dan aktifkan workflow n8n pada volume baru:

```bash
docker compose -f docker-compose.public.yml exec n8n n8n import:workflow --separate --input=/home/node/.n8n/workflows
docker compose -f docker-compose.public.yml exec n8n n8n update:workflow --all --active=true
docker compose -f docker-compose.public.yml restart n8n
```

11. Buka:

```text
https://APP_DOMAIN
```

## Port Yang Perlu Dibuka

Public:
- `80`
- `443`

SSH:
- `22` atau custom SSH port.

Jangan dibuka public:
- PostgreSQL
- MongoDB
- MinIO internal port
- Backend internal port
- Docker daemon socket

## Catatan Penting

- `files.APP_DOMAIN` dibutuhkan agar signed URL dokumen dari MinIO bisa dibuka browser public.
- n8n tersedia lewat `https://APP_DOMAIN/n8n` dan dilindungi basic auth.
- Jika tidak membutuhkan n8n public, route `/n8n` dapat dihapus dari `Caddyfile`.
- File `.env` production jangan dimasukkan ke ZIP publik atau Git.
- Workflow n8n perlu di-import satu kali ketika volume n8n masih baru.
- AI dan Telegram bersifat opsional; workflow task, validasi laporan, review, dan approval tetap berjalan tanpa API eksternal.

## Perintah Update Setelah Ada Perubahan Source

```bash
docker compose -f docker-compose.public.yml build frontend backend
docker compose -f docker-compose.public.yml up -d frontend backend
```

Untuk perubahan database/model besar, jalankan migration bila sudah tersedia. Saat ini MVP memakai `create_tables()` saat aplikasi start/seed.
