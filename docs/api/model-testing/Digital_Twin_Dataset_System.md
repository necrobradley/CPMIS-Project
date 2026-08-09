# Digital Twin Dataset System - Model Testing

Status: Active foundation  
Last updated: 2026-08-06  
Scope: Rencanix / DigiCom CPMIS Model Testing

## 1. Tujuan

Modul ini dibuat agar dataset dummy CPMIS tidak hanya menjadi kumpulan dokumen atau tabel terpisah, tetapi mulai membentuk **Digital Twin Project** yang saling terhubung. Setiap informasi penting dapat dimodelkan sebagai node, lalu dihubungkan dengan relationship yang punya nama, alasan, referensi rule, dan confidence.

Fondasi ini sengaja dibuat generik karena dataset masih akan berkembang. Dengan pendekatan ini, data seperti Contract, Milestone, WBS, BOQ, Activity, Task, Material, Supplier, Inspection, Progress, Payment, Claim, Risk, Issue, Lesson Learned, dan Close Out dapat dimasukkan bertahap tanpa harus menunggu seluruh tabel enterprise selesai.

## 2. Struktur Data

### Digital Twin Node

Node adalah entitas apa pun di dalam proyek.

Contoh node:

- `project`
- `contract`
- `milestone`
- `wbs`
- `boq`
- `activity`
- `task`
- `material`
- `equipment`
- `labor`
- `supplier`
- `purchase_order`
- `delivery`
- `inspection`
- `progress`
- `payment`
- `cash_flow`
- `claim`
- `risk`
- `issue`
- `lesson_learned`
- `close_out`

Field penting:

| Field | Fungsi |
| --- | --- |
| `uid` | Unique ID dataset, misalnya `activity:STR-001` |
| `node_type` | Jenis node |
| `code` | Kode formal, misalnya WBS/BOQ/Activity code |
| `name` | Nama yang mudah dibaca |
| `source_table` dan `source_id` | Link ke tabel CPMIS jika node berasal dari data aplikasi |
| `discipline`, `zone`, `floor`, `revision` | Metadata proyek untuk RAG/filter |
| `metadata` | Detail tambahan seperti volume, unit, durasi, produktivitas, mitigasi |

### Digital Twin Relationship

Relationship adalah hubungan bernama antar-node.

Contoh:

- Project `has_contract` Contract
- Contract `defines_wbs` WBS
- WBS `has_boq` BOQ
- BOQ `defines_quantity_for` Activity
- Activity `uses_material` Material
- Material `purchased_from` Supplier
- Activity `precedes` Activity lain
- Activity `generates_progress` Progress
- Progress `supports_payment` Payment
- Risk `has_mitigation` Mitigation

Field penting:

| Field | Fungsi |
| --- | --- |
| `relationship_uid` | ID unik relationship |
| `from_uid` dan `to_uid` | Node asal dan tujuan |
| `relationship_type` | Kode relasi machine-readable |
| `relationship_name` | Nama relasi human-readable |
| `reason` | Alasan hubungan dibuat |
| `rule_reference` | Referensi rule/SOP/SNI/PMBOK |
| `confidence` | Tingkat keyakinan 0-1 |

## 3. Rule Engine Foundation

Modul ini sudah menyediakan tabel `digital_twin_rules` dan seed rule awal. Ini belum 1.000 rule, tetapi fondasi untuk menuju rule engine yang lebih besar.

Rule awal yang tersedia:

| Rule | Makna |
| --- | --- |
| `R-SCH-001` | Activity harus terhubung ke WBS |
| `R-SCH-002` | Activity harus punya predecessor kecuali Start |
| `R-RES-001` | Activity harus punya resource |
| `R-PROC-001` | Material harus punya supplier |
| `R-QUAL-001` | Pengecoran harus menunggu QC inspection |

Target berikutnya adalah memperbanyak rule ke kategori scheduling, structural, architectural, MEP, procurement, inspection, quality, safety, contract, payment, risk, weather, equipment, resource, commissioning, dan close out.

## 4. AI Reasoning Dataset

Modul ini juga menyediakan `digital_twin_reasoning_examples`.

Formatnya:

| Field | Fungsi |
| --- | --- |
| `question` | Pertanyaan yang mungkin diajukan user |
| `context` | Konteks data yang digunakan |
| `reasoning` | Alasan teknis/logis |
| `answer` | Jawaban final |
| `reference` | Rule, dokumen, method statement, atau SOP |
| `confidence` | Keyakinan jawaban |
| `related_node_uid` | Node terkait, misalnya activity tertentu |

Ini akan menjadi bahan training/evaluation agar AI tidak hanya menjawab dari dokumen, tetapi dapat menjelaskan alasan teknis berdasarkan relationship dan rule.

## 5. Endpoint API

Semua endpoint berada di bawah `/api/v1/digital-twin`.

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/template` | Melihat contoh payload dataset |
| POST | `/projects/{project_id}/import` | Bulk import node, relationship, rule, reasoning example |
| GET | `/projects/{project_id}/graph` | Export Knowledge Graph JSON |
| POST | `/projects/{project_id}/validate` | Validasi konsistensi dataset |
| POST | `/projects/{project_id}/validate?persist=true` | Validasi dan simpan issue ke database |
| POST | `/projects/{project_id}/rules/defaults` | Seed rule awal |
| POST | `/projects/{project_id}/sync-existing` | Membuat node/relationship dari data CPMIS yang sudah ada |

Endpoint ini hanya boleh dikelola oleh admin, director, manager, atau owner project karena graph dapat berisi data komersial, vendor, progres, dan risiko.

## 6. Contoh Payload Minimal

```json
{
  "nodes": [
    {
      "uid": "project:demo",
      "node_type": "project",
      "code": "PRJ-DEMO",
      "name": "Demo Project",
      "metadata": {"owner": "Rencanix"}
    },
    {
      "uid": "wbs:1",
      "node_type": "wbs",
      "code": "1.0",
      "name": "Pekerjaan Struktur",
      "metadata": {}
    },
    {
      "uid": "boq:1",
      "node_type": "boq",
      "code": "BOQ-001",
      "name": "Beton K-300",
      "metadata": {"unit": "m3", "planned_quantity": 100, "boq_value": 85000000}
    },
    {
      "uid": "activity:1",
      "node_type": "activity",
      "code": "ACT-001",
      "name": "Pengecoran kolom lantai 1",
      "metadata": {"duration_days": 2, "productivity_reference": "30 m3/hari"}
    }
  ],
  "relationships": [
    {
      "from_uid": "project:demo",
      "to_uid": "wbs:1",
      "relationship_type": "has_wbs",
      "relationship_name": "Project memiliki WBS"
    },
    {
      "from_uid": "wbs:1",
      "to_uid": "boq:1",
      "relationship_type": "has_boq",
      "relationship_name": "WBS memiliki BOQ"
    },
    {
      "from_uid": "boq:1",
      "to_uid": "activity:1",
      "relationship_type": "defines_quantity_for",
      "relationship_name": "BOQ menjadi dasar activity"
    }
  ],
  "rules": [],
  "reasoning_examples": []
}
```

## 7. Validasi Dataset v1

Validator awal memeriksa:

- Dataset punya foundation node seperti project, contract, WBS, BOQ, dan activity.
- WBS harus terhubung ke BOQ.
- Activity harus terhubung ke WBS, langsung atau melalui BOQ.
- Activity harus punya resource material/equipment/labor/crew.
- Activity harus punya predecessor dan successor, kecuali ditandai `is_start` atau `is_finish`.
- Durasi activity harus punya `productivity_reference`.
- Material harus terhubung ke supplier.
- Risk/issue harus memiliki mitigasi.
- Relationship tidak boleh menghubungkan node dari project berbeda.
- Relationship harus memiliki nama.

Validator ini adalah tahap awal. Validasi enterprise berikutnya perlu menambahkan CPM, cash flow, progress claim, drawing/BOQ consistency, method statement/RKS consistency, dan closeout dossier completeness.

## 8. Cara Pakai Saat Membuat Dummy Dataset

Urutan yang disarankan:

1. Buat node `project`, `contract`, `milestone`, `wbs`, `boq`, dan `activity`.
2. Hubungkan chain awal: Project -> Contract -> Milestone -> WBS -> BOQ -> Activity.
3. Tambahkan resource: Material, Equipment, Labor, Crew.
4. Hubungkan Material ke Supplier.
5. Tambahkan predecessor/successor activity.
6. Isi `duration_days` dan `productivity_reference` di metadata activity.
7. Tambahkan inspection, quality check, progress, payment, risk, issue, dan closeout secara bertahap.
8. Jalankan endpoint validate.
9. Jika hasil masih warning/error, lengkapi relationship atau metadata.
10. Export graph untuk bahan RAG, Knowledge Graph, atau analisis AI.

## 9. Batasan Saat Ini

Yang sudah tersedia adalah fondasi dataset digital twin. Yang belum selesai:

- Belum ada 1.000 rule konstruksi.
- Belum ada Neo4j/GraphML/P6/MS Project export.
- Belum ada CPM engine penuh.
- Belum ada durasi otomatis dari produktivitas untuk semua activity.
- Belum ada vector DB production seperti Qdrant/BGE/reranker.
- Belum ada UI khusus untuk mengelola graph.

Namun, struktur ini sudah cukup untuk mulai membuat dummy data yang rapi, relasional, dan siap dikembangkan menjadi AI Project Planning Assistant.
