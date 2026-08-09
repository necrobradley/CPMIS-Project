# PRD Progress Check - Rencanix / DigiCom CPMIS

Tanggal pemeriksaan: 4 Agustus 2026  
Scope pemeriksaan: perbandingan PRD Rencanix CPMIS, RFC terbaru, dokumentasi model testing, source backend/frontend, dan status service lokal.

## 1. Ringkasan Eksekutif

Secara implementasi, alur inti CPMIS sudah semakin dekat dengan PRD model testing: aplikasi tertutup, RBAC, task approval, staff scoped access, laporan harian, requirement checker, evidence upload, approval manager, S-curve, project controls, Telegram auto grouping, RAG awal, Secure AI Gateway, local LLM routing, vendor database, produktivitas internal, dan make-or-buy analysis sudah memiliki basis kode dan test.

Poin yang perlu diperhatikan hari ini adalah environment lokal tidak sedang online. Docker Desktop tidak dapat dihubungi, dan endpoint `localhost:3003`, `localhost:8003/health`, serta `localhost:5681/healthz` tidak merespons. Jadi status kode baik, tetapi demo live perlu menyalakan Docker lagi sebelum presentasi atau QA browser.

## 2. Verifikasi Teknis Hari Ini

Pemeriksaan yang dijalankan:

- Backend test penuh: `67 passed`.
- Frontend typecheck/lint: `npm run lint` berhasil.
- Docker status: gagal terhubung ke Docker API.
- Endpoint lokal: frontend, backend, dan n8n tidak dapat diakses karena service tidak sedang berjalan.

Catatan warning test:

- Ada warning Pydantic `class-based config` menuju Pydantic v3.
- Ada warning SQLAlchemy `declarative_base` deprecated.
- Ada warning dependency `pypdf/cryptography`.

Warning tersebut belum memblokir test, tetapi sebaiknya dicatat untuk hardening teknis berikutnya.

## 3. Progress Terbaru yang Sudah Masuk

Berikut area yang sudah terlihat masuk dalam kode/dokumentasi:

- PRD baru: `docs/PRD_Rencanix_CPMIS_Template_Format_20260801.md`.
- RFC workflow inti: `docs/rfcs/RFC-0001-Rencanix-CPMIS-Core-Workflow.md`.
- Task baru masuk approval pending terlebih dahulu.
- Staff tidak bisa membuat laporan untuk task orang lain.
- Task pending tidak bisa diubah status atau dipakai laporan.
- Laporan approved memperbarui progress melalui Project Controls.
- S-curve sudah tersedia dari data planned vs actual.
- Telegram auto grouping sudah memiliki parser rule-based dan test.
- Evidence foto/dokumen masuk folder berbasis project/task/report.
- Requirement checker sudah menjadi gate sebelum laporan masuk review.
- Make-or-buy analysis sudah membandingkan internal, vendor, BOQ, produktivitas, dan risiko.
- Vendor profile, vendor rate card, dan productivity benchmark sudah tersedia.
- Secure AI Gateway, RAG MVP, dan local LLM routing sudah terdokumentasi dan dites.
- n8n service wrapper dan scheduler backend sudah tersedia.
- RBAC dan staff scope sudah memiliki test.

## 4. Perbandingan PRD vs Implementasi

| Area PRD | Status | Catatan |
| --- | --- | --- |
| Authentication tertutup | Hampir sesuai | Register publik secara produk harus tetap tidak dipakai; akun dibuat admin |
| RBAC data penting | Sesuai untuk baseline | Backend sudah memfilter staff dari data sensitif controls/vendor/cost |
| Admin aplikasi vs admin proyek | Ada fondasi | Perlu QA UI lagi agar tidak terasa menyatu pada menu/admin console |
| Project setup, divisi, role, staff | Sebagian besar ada | Wizard dan UX masih perlu disederhanakan untuk manager |
| Task approval oleh PM | Ada | Task dibuat pending dan masuk approval request |
| Task detail spek/material/evidence | Ada | UI detail task sudah lebih kaya, perlu test manual dengan data dummy |
| Daily report workflow | Ada | Draft, validation, submit, review, approve tersedia |
| Requirement checker | Ada | Perlu data requirement yang realistis per pekerjaan untuk demo |
| Progress update ke S-curve | Ada | Laporan approved memicu update progress |
| Telegram reporting | Ada baseline | Bot live tergantung token/env dan container; preview endpoint sudah ada |
| Document Intelligence/tender analysis | Ada sebagian | Upload + AI analysis + sync preview ada, tetapi kualitas ekstraksi tender real perlu diuji |
| RAG dokumen | Ada MVP | Masih chunk table + deterministic embedding, belum vector DB production |
| Secure AI Gateway | Ada | Mask/block policy dan local LLM route tersedia |
| n8n readiness | Partial | Service wrapper ada, tetapi n8n tidak online pada pemeriksaan ini |
| Deadline alert | Ada backend scheduler | Perlu verifikasi live saat Docker/n8n berjalan |
| Weekly summary | Ada scheduler dan trigger | Ringkasan masih berbasis statistik; AI executive narrative perlu diuji/ditingkatkan |
| Communication Hub | Ada | Perlu E2E komunikasi lintas task/divisi |
| Vendor/make-or-buy | Ada | Sudah thesis-worthy, tetapi import Excel vendor/productivity belum ada |
| Multi-company commercial admin | Sebagian | Untuk model testing bukan target penuh; commercial hardening tetap rencana lanjut |

## 5. Status Area Automation

| Automation | Status kode | Status live | Risiko |
| --- | --- | --- | --- |
| Daily Report | Implemented | Belum live hari ini | Docker/backend/n8n sedang tidak jalan |
| Deadline Alert | Implemented scheduler | Belum live hari ini | Scheduler perlu container aktif dan observasi jam 08:00 WIB |
| Tender Analysis | Implemented partial | Belum live hari ini | Perlu uji PDF/Word tender real dan kualitas output AI |
| Weekly Summary | Implemented trigger | Belum live hari ini | Perlu format narasi executive dan test Telegram |
| Telegram Bot | Implemented baseline | Belum live hari ini | Bergantung `TELEGRAM_BOT_TOKEN`, polling, dan mapping Telegram ID |
| n8n | Wrapper dan compose ada | Offline hari ini | Docker Desktop tidak aktif/terhubung |
| RAG | Implemented MVP | Belum live hari ini | Belum production vector DB |
| Secure AI Gateway | Implemented/tested | Belum live hari ini | Perlu validasi env policy saat demo |

## 6. Thesis-Critical Items yang Masih Perlu Dikuatkan

1. **Demo environment harus stabil.** Sebelum presentasi, Docker harus aktif dan endpoint `3003`, `8003`, `5681` harus hijau.
2. **Skenario E2E harus dibuat sangat jelas.** Minimal satu alur dari admin buat akun, manager approve task, staff submit report, checker validasi, manager approve, S-curve berubah.
3. **Tender analysis jangan diklaim otomatis sempurna.** Klaim yang lebih aman: sistem membuat draft WBS/task dan tetap memerlukan approval Project Manager.
4. **Weekly summary perlu dibuat lebih presentable.** Saat ini sudah ada data statistik, tetapi ringkasan untuk director sebaiknya punya narasi: progress, issue utama, risiko deadline, dan keputusan yang dibutuhkan.
5. **n8n perlu diposisikan opsional.** Core automation sudah bisa di backend; n8n dipakai untuk integrasi/notification orchestration, bukan fondasi wajib.
6. **Data dummy harus lebih realistis.** Untuk sidang/demo, isi task perlu punya BOQ, quantity, requirement evidence, material, vendor price, productivity benchmark, dan blocker yang nyambung.
7. **UI role staff perlu diuji lagi.** Staff harus hanya melihat tugas, dokumen, laporan, dan komunikasi yang berhubungan dengan pekerjaannya.
8. **Document revision impact dan handover dossier masih perlu E2E nyata.** Modelnya ada di PRD/RFC, tetapi demo perlu contoh perubahan dokumen yang menandai task/material terdampak.

## 7. Rekomendasi Aksi Berikutnya

Prioritas paling konkret:

1. Nyalakan Docker dan jalankan smoke test browser untuk `localhost:3003`.
2. Buat satu seed/demo project yang sangat rapi untuk skenario sidang:
   - 1 project;
   - 4 role tim;
   - 3 divisi;
   - 8-12 task approved/pending;
   - 2 laporan draft;
   - 1 laporan needs revision;
   - 1 laporan approved yang mengubah S-curve;
   - 2 vendor rate;
   - 2 productivity benchmark.
3. Buat halaman atau dokumen "Demo Script 10 Menit" berisi langkah klik dan akun demo.
4. Uji Telegram preview endpoint untuk 3 contoh laporan:
   - WBS jelas;
   - lokasi jelas;
   - pesan ambigu yang harus meminta klarifikasi.
5. Tambahkan executive weekly summary format agar output terlihat matang untuk director.
6. Buat screenshot evidence untuk PRD/thesis: My Work staff, Task Detail, Report Validation, Manager Approval, S-curve, Make-or-Buy.

## 8. Kesimpulan

CPMIS model testing sudah memiliki fondasi workflow yang cukup kuat untuk tesis: tidak hanya dashboard, tetapi sudah ada hubungan antara task, assignment, laporan, requirement, approval, progress, AI, RAG, Telegram, dan project controls. Risiko terbesar saat ini bukan lagi konsep utama, melainkan kesiapan demo live, kerapian data dummy, dan pembuktian E2E dengan skenario yang mudah dipahami pembimbing/coach.
