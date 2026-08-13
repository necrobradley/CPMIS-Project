# CPMIS Domain Glossary

## User

Akun manusia yang dapat masuk ke aplikasi. Satu user memiliki satu role aplikasi dan dapat memiliki role proyek yang berbeda pada setiap proyek.

## Role aplikasi

Tingkat akses umum pada aplikasi: Admin Owner, Admin Proyek, director, manager, staff, atau subcontractor. Role ini tidak menjelaskan keahlian atau jabatan orang pada proyek tertentu.

## Admin Owner

Satu-satunya akun pemilik platform yang mengelola tenant, paket layanan, entitlement per proyek, feature flag, kesiapan layanan, dan reset sistem. Admin Owner tidak membuat akun pegawai atau menjalankan administrasi proyek.
_Avoid_: Admin aplikasi, super admin, admin proyek

## Admin Proyek

Akun administrator operasional yang mewakili tepat satu proyek dan dapat membuat, mengimpor, serta mengatur akun pengguna pada proyek tersebut. Setiap proyek memiliki tepat satu Admin Proyek; akun ini tidak dapat mengelola tenant, paket, entitlement, feature flag, kesiapan layanan, atau reset sistem.
_Avoid_: Admin Owner, project role `project_admin`

## Setup Admin Proyek

Proses satu kali untuk membuat satu akun Admin Proyek sekaligus satu proyek kosong yang diwakilinya. Setup ini tidak mengimpor dataset, tidak mengunggah dokumen, dan tidak membuat akun pegawai.
_Avoid_: Import dataset proyek, bootstrap Admin Owner

## Paket proyek

Paket layanan Starter, Professional, atau Enterprise yang ditetapkan Admin Owner pada satu proyek. Penerapan paket mengatur pilihan awal entitlement fitur proyek; Admin Owner masih dapat menyesuaikan fitur noninti setelah paket diterapkan.
_Avoid_: Tenant organisasi, dataset proyek

## Entitlement fitur proyek

Pilihan fitur aktif untuk satu proyek yang ditetapkan oleh Admin Owner. Entitlement ini menentukan menu dan kapabilitas yang tersedia bagi Admin Proyek dan anggota proyek tersebut.
_Avoid_: Feature flag global, hak akses role

## Role proyek

Jabatan dan tanggung jawab seorang user pada satu proyek, misalnya Project Manager, Site Engineer, QA/QC Engineer, atau HSE Officer.

## PIC task

User aktif yang bertanggung jawab memperbarui progres dan bukti untuk sebuah task. Hanya role proyek yang ditandai dapat menjadi PIC yang boleh menerima assignment task.

## Stakeholder non-PIC

Anggota proyek yang berfungsi memberi arahan, review, approval, audit, pasokan, atau observasi. Akunnya tetap dibuat dan terhubung ke proyek, tetapi tidak menerima task pelaksanaan sebagai PIC.

## Rekomendasi role oleh AI

Role proyek yang disarankan model berdasarkan isi task. Model tidak memilih user secara langsung; sistem memilih anggota aktif dengan role yang sesuai dan beban task paling rendah.

## Task demo AI

Task dummy yang diberi penanda AI untuk memperlihatkan coverage role pada presentasi. Task ini disiapkan oleh paket demo dan dibedakan dari task yang benar-benar dihasilkan melalui panggilan model online.

## Dataset terstruktur

Data proyek yang sudah dinormalisasi menjadi JSON atau JSONL dan siap dipetakan secara deterministik menjadi proyek, WBS, task, graph, rule, dan contoh reasoning. Dataset proyek tidak membuat akun, tidak menetapkan password, dan tidak menetapkan PIC. Import dataset terstruktur bukan panggilan model AI.
_Avoid_: Dokumen sumber, hasil generate Nemotron

## Dataset akun proyek

File CSV terpisah yang memuat nama, email, role aplikasi, nama divisi, dan role proyek. Admin Proyek mengimpornya melalui fitur Pengguna. Nama divisi dibuat atau digunakan kembali dalam lingkup proyek yang sama; password tidak disimpan di CSV.
_Avoid_: Dataset proyek, ZIP proyek, daftar password

## Register kredensial proyek

Dokumen Word rahasia yang dibuat atas konfirmasi dan password Admin Proyek. Proses pembuatannya merotasi password seluruh akun anggota aktif pada proyek, mengaktifkan password acak tersebut untuk login, menghentikan sesi lama melalui perubahan versi autentikasi, lalu menyajikannya satu kali dalam tabel. Nilai password tidak dicatat pada audit log dan tidak dapat dibaca kembali dari database.
_Avoid_: Ekspor user biasa, undangan email, penyimpanan password mentah

## Import ulang dataset proyek

Impor dataset pertama mengisi wadah proyek kosong milik Admin Proyek dan mengadopsi nama proyek dari ZIP tanpa membuat proyek kedua. Setelah dataset pernah dimuat, impor dengan nama proyek yang sama memperbarui data beridentitas sama, misalnya WBS yang sama; ZIP dengan nama proyek berbeda ditolak agar data proyek aktif tidak tertimpa.
_Avoid_: Membuat proyek baru, mengganti Admin Proyek

## Dokumen sumber

Berkas asli proyek seperti PDF, DOCX, dan XLSX yang menjadi bukti atau konteks proyek. Dokumen sumber disimpan di Pusat Dokumen; format yang didukung dapat dianalisis model AI secara terpisah dan hasilnya dicatat pada dokumen.
_Avoid_: Dataset terstruktur, knowledge graph

## Analisis AI dokumen

Panggilan model online terhadap satu dokumen sumber yang tersimpan. Proses ini menghasilkan analisis yang dapat ditinjau dan, setelah persetujuan, digunakan sebagai calon perubahan task atau data proyek.
_Avoid_: Import dataset, parsing ZIP
