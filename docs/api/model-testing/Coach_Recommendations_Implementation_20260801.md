# Implementasi Masukan Coach: Telegram, Produktivitas, Vendor, dan Make-or-Buy

Dokumen ini mencatat pembaruan model testing CPMIS berdasarkan masukan coach: laporan lapangan dari Telegram harus otomatis masuk ke task yang tepat, sistem harus menjaga agar hanya PIC yang dapat memperbarui pekerjaannya, dan AI/project control harus membantu menentukan apakah pekerjaan lebih menguntungkan dikerjakan internal atau dialihkan ke vendor.

## 1. Telegram Assignment-Aware Reporting

Alur yang diterapkan:

1. Staff mengirim laporan bebas melalui Telegram.
2. Sistem mencari task aktif yang ditugaskan langsung kepada staff tersebut.
3. Pesan dicocokkan ke task berdasarkan WBS, lokasi, judul, divisi, keyword requirement, material, dan detail pekerjaan.
4. Jika confidence cukup, sistem membuat draft laporan.
5. Jika confidence kurang, bot meminta staff memilih task atau mengirim ulang dengan WBS/lokasi.
6. Staff tidak dapat membuat laporan Telegram untuk task orang lain.

Parser lokal sekarang menangkap:

- volume aktual, misalnya `30 m2`, `5 m3`, `10 unit`;
- jumlah pekerja, misalnya `3 tukang`, `6 orang`;
- cuaca bebas, misalnya `hujan`, `cerah`, `mendung`;
- kendala bebas, misalnya `kendala cat kurang`.

AI parsing disiapkan sebagai opsi melalui `TELEGRAM_AI_PARSE_ENABLED`. Default-nya `false` agar hemat token. Jika diaktifkan, AI memperkaya hasil parser lokal, bukan menggantikannya sepenuhnya.

## 2. Database Produktivitas Internal

Sistem sekarang memiliki tabel `productivity_benchmarks` untuk menyimpan standar produktivitas internal per proyek atau global.

Data yang dicatat:

- kategori pekerjaan;
- keyword pekerjaan;
- satuan BOQ;
- output per hari;
- jumlah crew;
- biaya tenaga kerja per hari;
- biaya alat per hari;
- biaya material per satuan;
- overhead;
- risiko;
- confidence score;
- sumber data/catatan.

Contoh:

| Pekerjaan | Output | Crew | Biaya Tenaga/Hari | Material/Unit |
|---|---:|---:|---:|---:|
| Pengecatan dinding | 30 m2/hari | 3 orang | Rp550.000 | Rp23.000/m2 |

## 3. Vendor Price Database

Vendor tetap menggunakan `vendor_profiles` dan `vendor_rate_cards`.

Data vendor yang dibandingkan:

- kategori pekerjaan;
- keyword pekerjaan;
- satuan;
- harga satuan;
- biaya mobilisasi;
- lead time;
- rating vendor;
- skor kualitas, delivery, safety, dan kapasitas;
- risk multiplier.

## 4. Make-or-Buy Analysis

Sistem membandingkan:

- nilai BOQ item;
- biaya internal manual jika sudah diisi;
- biaya internal dari benchmark produktivitas jika biaya manual belum ada;
- harga vendor terbaik;
- margin internal;
- margin vendor;
- potensi saving;
- risiko teknis;
- tekanan schedule;
- kebutuhan alat khusus;
- requirement material/approval;
- blocker pekerjaan.

Output rekomendasi:

- `internal_preferred`: pekerjaan lebih rasional dikerjakan internal;
- `vendor_review`: vendor layak direview oleh PM/Procurement;
- `vendor_recommended`: vendor lebih menguntungkan dan teknisnya layak;
- `hybrid_review`: pekerjaan internal masih bisa jalan, tetapi butuh support vendor;
- `need_vendor_rate`: data harga vendor belum cukup;
- `need_internal_cost`: data biaya/produktivitas internal belum cukup.

Prinsip penting: AI/sistem memberi rekomendasi. Keputusan final tetap pada Project Manager, Procurement/Commercial, atau Director sesuai RBAC.

## 5. UI Yang Ditambahkan

Pada menu `Project Controls > Make-or-Buy`:

- panel database produktivitas internal;
- form tambah benchmark produktivitas;
- indikator sumber estimasi internal;
- durasi estimasi internal dari output per hari;
- perbandingan vendor terbaik vs internal;
- alasan rekomendasi yang bisa dibaca PM.

## 6. File Utama Yang Diubah

- `backend/app/models/user.py`
- `backend/app/schemas/schemas.py`
- `backend/app/api/v1/endpoints/controls.py`
- `backend/app/services/project_controls.py`
- `backend/app/services/telegram_auto_grouping.py`
- `backend/app/services/telegram_service.py`
- `backend/app/services/ai_service.py`
- `backend/scripts/seed_db.py`
- `frontend/src/app/controls/page.tsx`
- `frontend/src/lib/api.ts`

## 7. Hal Yang Masih Dapat Dikembangkan Lanjutan

- approval khusus untuk keputusan vendor/internal;
- import massal benchmark produktivitas dari Excel;
- histori produktivitas aktual dari laporan approved;
- pembelajaran otomatis: produktivitas aktual proyek memperbarui benchmark;
- RAG khusus vendor/BOQ untuk menjawab pertanyaan seperti “harga pekerjaan cat m2 berapa dan vendor mana paling murah?”;
- scoring vendor berbasis performa riil dari proyek sebelumnya.
