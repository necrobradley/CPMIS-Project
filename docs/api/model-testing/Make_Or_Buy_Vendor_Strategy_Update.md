# Make-or-Buy dan Vendor Strategy

Dokumen ini mencatat pembaruan modul Project Controls untuk membantu Project Manager dan Procurement menentukan apakah suatu pekerjaan lebih rasional dikerjakan internal, direview untuk vendor, atau direkomendasikan ke vendor/subkon.

## Tujuan

Sebelumnya sistem hanya menilai kecocokan vendor berdasarkan parameter teknis. Pembaruan ini menambahkan analisis biaya sehingga keputusan tidak hanya berbasis intuisi, tetapi mempertimbangkan nilai BOQ, estimasi biaya internal, harga vendor, mobilisasi, risiko, dan performa vendor.

## Data yang Digunakan

### Data Task dan Baseline

Setiap task dapat menyimpan:

- nilai BOQ atau nilai kontrak item;
- control budget;
- volume dan satuan pekerjaan;
- biaya material internal;
- biaya tenaga kerja internal;
- biaya alat internal;
- overhead internal;
- biaya risiko internal;
- manpower dan alat utama;
- deadline, progress, gate, material approval, dan dependency.

### Database Vendor

Sistem memiliki tabel vendor profile dan vendor rate card.

Vendor profile berisi:

- nama vendor;
- spesialisasi;
- lokasi;
- status approved;
- rating umum;
- skor kualitas;
- skor delivery;
- skor safety;
- skor kapasitas;
- catatan.

Vendor rate card berisi:

- kategori pekerjaan;
- keyword pencocokan pekerjaan;
- satuan;
- harga satuan;
- biaya mobilisasi;
- lead time;
- cakupan material, tenaga kerja, dan alat;
- risk multiplier;
- masa berlaku harga;
- catatan harga.

## Cara Sistem Menganalisis

1. Sistem membaca judul task, deskripsi, work package, acceptance criteria, dan material specification.
2. Sistem mendeteksi kategori pekerjaan seperti structure, facade, HVAC, electrical, waterproofing, finishing, HSE, atau testing.
3. Sistem mencari rate card vendor yang cocok berdasarkan kategori, keyword, satuan, dan status vendor approved.
4. Sistem menghitung biaya internal dari komponen yang diinput manager.
5. Jika biaya internal belum lengkap, sistem membuat estimasi konservatif dari nilai BOQ atau benchmark vendor.
6. Sistem menghitung total biaya vendor:

   `harga satuan x volume + mobilisasi + management cost + risk cost`

7. Sistem menghitung margin internal dan margin vendor terhadap nilai BOQ.
8. Sistem memberi rekomendasi:

- `internal_preferred`: internal lebih rasional;
- `vendor_review`: perlu review PM/Procurement;
- `vendor_recommended`: vendor lebih menguntungkan atau lebih layak secara teknis;
- `hybrid_review`: pertimbangkan internal dengan support vendor;
- `need_vendor_rate`: data harga vendor belum tersedia;
- `need_internal_cost`: estimasi biaya internal belum cukup.

## Prinsip Kontrol

Analisis ini adalah decision support. Sistem tidak otomatis membuat PO, kontrak, atau menunjuk vendor. Keputusan akhir tetap berada pada Project Manager bersama Procurement/Commercial.

## RBAC

Staff dan subcontractor tidak melihat biaya internal, harga vendor, margin, atau potensi saving. Data ini dibatasi untuk role manajerial, direktur, admin, atau role proyek yang memiliki akses finansial.

## Status Implementasi

Sudah diterapkan:

- tabel `vendor_profiles`;
- tabel `vendor_rate_cards`;
- field biaya internal pada `task_controls`;
- field `boq_value` pada `task_controls`;
- engine make-or-buy pada Project Controls;
- endpoint vendor profile dan rate card;
- data dummy vendor dan harga;
- tampilan Make-or-Buy pada Project Controls;
- test backend untuk skenario vendor recommended dan internal preferred.

Belum diterapkan:

- halaman admin khusus vendor database;
- import Excel rate card vendor;
- workflow RFQ/quotation;
- purchase order;
- kontrak vendor;
- evaluasi performa vendor dari data real proyek;
- approval komersial multi-level.
