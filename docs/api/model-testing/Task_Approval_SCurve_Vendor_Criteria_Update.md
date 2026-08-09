# Update Alur Task, Timeline, dan Vendor Criteria

Dokumen ini mencatat pembaruan model testing setelah masukan coaching terkait task approval, timeline manusia, dan parameter pekerjaan yang perlu dipertimbangkan untuk dialihkan ke vendor.

## 1. Task Tidak Langsung Menjadi Pekerjaan Aktif

Task baru dari input manual atau hasil analisis dokumen masuk sebagai `pending` terlebih dahulu. Sistem otomatis membuat approval request bertipe `task` untuk Project Manager atau approver yang ditentukan. Selama belum approved, task tidak boleh diperlakukan sebagai pekerjaan aktif.

Dampak alur:

- Staff belum melihat task pending sebagai pekerjaan yang dapat dilaporkan.
- Status task pending tidak dapat diubah menjadi in progress, review, done, atau blocked.
- Task pending tidak ikut menghitung progress resmi proyek.
- Setelah Project Manager approve, task menjadi aktif dan dapat masuk ke timeline, laporan, progress control, dan action queue.

## 2. Timeline Detail Tetap Dikendalikan Manusia

Sistem tidak lagi menjadikan hasil AI/tender sebagai timeline final. Dokumen tender atau kontrak dapat memberi petunjuk milestone, tetapi baseline detail tetap ditentukan oleh manusia melalui Project Controls.

Data timeline yang digunakan:

- planned start;
- planned finish;
- deadline task sebagai fallback awal;
- bobot pekerjaan;
- planned quantity;
- actual quantity dari laporan approved;
- progress aktual setelah laporan diterima.

## 3. S-Curve Project

Project Controls sekarang menyediakan data S-curve berupa perbandingan planned progress dan actual progress. Kurva dibuat dari task approved yang memiliki baseline atau minimal deadline. Actual progress dihitung dari laporan approved dan progress task saat ini.

S-curve ditampilkan di:

- halaman detail proyek sebagai ringkasan timeline;
- menu Project Controls pada tab Timeline.

## 4. Vendor Criteria

Vendor Criteria adalah decision support untuk membantu Project Manager menentukan apakah pekerjaan tetap dikerjakan internal atau perlu direview untuk dialihkan ke vendor/subkon. Sistem memberi skor dan alasan, tetapi keputusan akhir tetap berada pada Project Manager.

Parameter yang dinilai:

- pekerjaan membutuhkan spesialis/vendor tersertifikasi;
- material membutuhkan submittal, sertifikat, approval, atau pengujian;
- pekerjaan membutuhkan alat khusus;
- risiko mutu/K3 tinggi atau prioritas kritikal;
- kapasitas internal berpotensi tidak cukup;
- deadline dekat dengan progres rendah;
- banyak gate teknis sebelum mulai atau selesai;
- lingkup mudah dipaketkan sebagai pekerjaan vendor/subkon.

Kategori hasil:

- `internal_preferred`: masih layak dikerjakan internal;
- `vendor_review`: perlu review vendor oleh PM/Procurement;
- `vendor_recommended`: direkomendasikan untuk vendor/subkon.

## 5. Aturan Staff

Staff hanya dapat mengubah status dan membuat laporan untuk task yang ditugaskan langsung kepadanya. Staff tidak boleh mengupdate task milik orang lain walaupun task tersebut berada pada divisi yang sama. Supervisor, Manager, Director, dan Admin tetap memiliki hak review sesuai RBAC.
