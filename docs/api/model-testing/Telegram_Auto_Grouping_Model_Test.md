# Telegram Auto Grouping - Model Testing

## Tujuan

Menguji alur pelaporan lapangan yang ringan untuk petugas: user cukup mengirim teks, foto, atau dokumen melalui Telegram; sistem mengelompokkan pesan ke project/task/WBS, membuat draft laporan, lalu meminta bukti tambahan atau klarifikasi bila confidence rendah.

## Alur MVP

1. User Telegram terdaftar mengirim pesan bebas atau caption foto.
2. Backend membaca user, project membership, task aktif, divisi, WBS code, lokasi, judul task, requirement, dan material.
3. Service `telegram_auto_grouping` memberi skor kandidat task.
4. Jika confidence >= `0.45`, sistem membuat `DailyReport` dan `DailyReportWorkflow(status=draft)`.
5. Jika confidence rendah, bot mengirim kandidat task dan meminta user memakai `/report` atau mengirim ulang dengan kode WBS/lokasi.
6. Foto/dokumen berikutnya masuk ke direktori evidence berdasarkan project/task/report.
7. User menjalankan `/submit` untuk validasi requirement dan antrean review.

## Endpoint Preview

Endpoint ini dipakai untuk model testing tanpa mengirim Telegram asli.

```http
POST /api/v1/reports/telegram/auto-group/preview
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Progress: pembesian pile cap WBS-STR-PILECAP-A zona A sudah 80%. Pekerja: 6"
}
```

Response utama:

- `matched`: true/false.
- `confidence`: skor kandidat terbaik.
- `threshold`: batas minimum auto-draft.
- `task_id`, `title`, `wbs_code`, `project_id`.
- `reasons`: alasan pencocokan.
- `candidates`: maksimal 3 kandidat task.
- `parsed_fields`: weather, manpower, progress, issues.

## Skenario Uji

| Skenario | Input | Ekspektasi |
| --- | --- | --- |
| WBS eksplisit | Caption berisi WBS code | Task cocok confidence tinggi |
| Lokasi eksplisit | Caption berisi zona/lantai/area | Task lokasi terkait naik skor |
| User hanya punya 1 task | Pesan tanpa WBS | Task tunggal tetap dipilih |
| Banyak task mirip | Caption umum | Bot meminta klarifikasi |
| Foto tanpa draft aktif | Caption cukup jelas | Draft dibuat lalu foto masuk evidence |
| Dokumen tanpa draft aktif | Nama file/caption jelas | Draft dibuat lalu dokumen masuk evidence |
| Requirement checklist | `REQ-X: ya` | Requirement terkonfirmasi pada draft |

## Catatan Batasan

- MVP ini masih rule-based dan token-free.
- Vision/OCR foto belum dipakai untuk membaca isi foto.
- GPS/EXIF belum dipakai.
- Jika dua task sangat mirip, sistem wajib meminta klarifikasi agar data tidak salah masuk task.
- Keputusan final tetap melalui `/submit` dan review atasan.
