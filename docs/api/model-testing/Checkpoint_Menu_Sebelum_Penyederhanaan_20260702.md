# Checkpoint Menu Sebelum Penyederhanaan - 2026-07-02

Checkpoint ini dibuat sebelum struktur menu Model Testing disederhanakan.

- Commit checkpoint: `cea517a`
- Tag checkpoint: `checkpoint-before-menu-simplification-20260702`
- Tujuan: kembali ke kondisi fitur/menu sebelum grouping menu operasional diterapkan.

## Cara Kembali

Untuk melihat kondisi checkpoint tanpa menghapus perubahan:

```bash
git checkout checkpoint-before-menu-simplification-20260702
```

Untuk mengembalikan branch `main` ke checkpoint secara penuh, gunakan hanya jika memang ingin membuang perubahan setelah checkpoint:

```bash
git checkout main
git reset --hard checkpoint-before-menu-simplification-20260702
```

## Catatan

Checkpoint ini menyimpan seluruh source Model Testing saat fitur admin komersial, pricing, entitlement, dan project role policy sudah ada, tetapi sebelum sidebar menu disederhanakan.
