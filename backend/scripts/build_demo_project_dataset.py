"""Bangun paket ZIP dummy multi-fitur untuk demo CPMIS."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


PROJECT = {
    "project_name": "Pusat Inovasi Terpadu Nusantara",
    "project_code": "PITN-2026",
    "location": "Tangerang Selatan, Banten",
    "contract_value_idr": 187_500_000_000,
    "start": "2026-05-04T00:00:00",
    "baseline_finish": "2027-06-30T00:00:00",
}


ACTIVITIES = [
    ("ACT-001", "1.1", "Mobilisasi dan persiapan area", "Persiapan", "ls", 1, 100, "2026-05-04", "2026-05-15", "YES", "Site setup selesai", "MAT-001", "Pagar proyek dan rambu K3", "Tim Persiapan", "Excavator mini", "Cuaca menghambat mobilisasi"),
    ("ACT-002", "2.1", "Pekerjaan bored pile", "Struktur Bawah", "m", 1850, 82, "2026-05-16", "2026-07-15", "YES", "Pengeboran dan pengecoran pile", "MAT-002", "Beton ready-mix fc' 35 MPa", "PT Beton Prima Nusantara", "Bored pile rig", "Keterlambatan hasil uji integritas pile"),
    ("ACT-003", "2.2", "Pile cap dan tie beam", "Struktur Bawah", "m3", 720, 64, "2026-06-20", "2026-08-08", "YES", "Pembesian dan pengecoran pile cap", "MAT-003", "Baja tulangan BJTS 420B", "PT Beton Prima Nusantara", "Concrete pump", "Area mock-up mengalami honeycomb"),
    ("ACT-004", "3.1", "Kolom struktur lantai dasar", "Struktur Atas", "m3", 410, 55, "2026-07-10", "2026-08-25", "YES", "Bekisting, pembesian, pengecoran kolom", "MAT-004", "Beton fc' 40 MPa", "PT Beton Prima Nusantara", "Tower crane", "Produktivitas bekisting di bawah rencana"),
    ("ACT-005", "3.2", "Balok dan slab lantai 2", "Struktur Atas", "m2", 4250, 38, "2026-07-25", "2026-09-10", "YES", "Pekerjaan balok dan slab", "MAT-005", "Plywood film faced 18 mm", "PT Beton Prima Nusantara", "Tower crane", "Keterlambatan siklus pengecoran"),
    ("ACT-006", "3.3", "Struktur atap dan rooftop", "Struktur Atas", "m2", 1850, 0, "2026-09-11", "2026-10-20", "NO", "Struktur atap dan dudukan peralatan", "MAT-006", "Baja profil struktural", "PT Baja Fabrikasi Sentosa", "Mobile crane", "Shop drawing belum final"),
    ("ACT-007", "4.1", "Dinding bata ringan", "Arsitektur", "m2", 6900, 22, "2026-08-01", "2026-11-15", "NO", "Pasangan dinding dan plester", "MAT-007", "Bata ringan AAC", "PT Arsitektur Karya", "Material hoist", "Akses material bertabrakan"),
    ("ACT-008", "4.2", "Fasad aluminium dan kaca", "Arsitektur", "m2", 4800, 0, "2026-10-01", "2027-01-20", "YES", "Supply dan instalasi curtain wall", "MAT-008", "Kaca low-e laminated", "PT Fasad Cemerlang", "Gondola", "Lead time kaca impor"),
    ("ACT-009", "4.3", "Waterproofing toilet dan rooftop", "Arsitektur", "m2", 2150, 15, "2026-08-20", "2026-11-30", "NO", "Aplikasi membran dan flood test", "MAT-009", "Membran waterproofing", "PT Arsitektur Karya", "Hand tools", "Flood test harus diulang"),
    ("ACT-010", "4.4", "Plafon dan finishing interior", "Arsitektur", "m2", 7200, 0, "2026-11-01", "2027-03-15", "NO", "Rangka plafon dan finishing", "MAT-010", "Gypsum board tahan api", "PT Interior Modular", "Scaffolding", "Mock-up warna belum disetujui"),
    ("ACT-011", "5.1", "Supply panel listrik utama", "Elektrikal", "unit", 6, 10, "2026-07-01", "2026-10-15", "YES", "Supply panel MV/LV dan FAT", "MAT-011", "Panel utama IEC 61439", "PT Mekanikal Energi Mandiri", "Forklift", "Approval drawing panel terlambat"),
    ("ACT-012", "5.2", "Instalasi cable tray dan kabel", "Elektrikal", "m", 12500, 8, "2026-09-15", "2027-02-10", "NO", "Instalasi cable tray, feeder, dan grounding", "MAT-012", "Kabel low smoke zero halogen", "PT Mekanikal Energi Mandiri", "Scissor lift", "Konflik jalur dengan ducting"),
    ("ACT-013", "6.1", "Instalasi plumbing dan sanitasi", "Mekanikal", "m", 8800, 5, "2026-09-01", "2027-01-31", "NO", "Instalasi pipa air bersih dan air kotor", "MAT-013", "Pipa PPR dan HDPE", "PT Mekanikal Energi Mandiri", "Pipe threading machine", "Ruang shaft terbatas"),
    ("ACT-014", "6.2", "Instalasi ducting HVAC", "Mekanikal", "m2", 9600, 0, "2026-10-01", "2027-02-28", "YES", "Fabrikasi dan instalasi ducting", "MAT-014", "Galvanized iron duct", "PT Mekanikal Energi Mandiri", "Scissor lift", "Akses pemasangan ducting lantai 3"),
    ("ACT-015", "6.3", "Fire alarm dan fire fighting", "Mekanikal", "ls", 1, 0, "2026-11-01", "2027-03-10", "NO", "Instalasi alarm, hydrant, dan sprinkler", "MAT-015", "Peralatan fire fighting bersertifikat", "PT Proteksi Api", "Hydrotest pump", "Koordinasi cause-and-effect"),
    ("ACT-016", "7.1", "Supply dan instalasi elevator", "Transportasi Vertikal", "unit", 5, 0, "2026-09-01", "2027-04-15", "YES", "Supply, instalasi, testing elevator", "MAT-016", "Elevator 1600 kg", "PT Lift Nusantara", "Chain block", "Lead time komponen elevator"),
    ("ACT-017", "8.1", "Landscape dan pekerjaan luar", "Eksternal", "m2", 5200, 0, "2027-02-01", "2027-05-15", "NO", "Landscape, drainase, dan hardscape", "MAT-017", "Paving block permeabel", "PT Landscape Hijau", "Mini roller", "Pekerjaan dipengaruhi cuaca"),
    ("ACT-018", "9.1", "Integrated testing dan commissioning", "Commissioning", "ls", 1, 0, "2027-03-15", "2027-05-31", "YES", "Testing fungsi dan integrasi seluruh sistem", "MAT-018", "Peralatan testing terkalibrasi", "PT Mekanikal Energi Mandiri", "Testing instruments", "Kegagalan integrasi sistem"),
    ("ACT-019", "9.2", "As-built drawing dan O&M manual", "Handover", "ls", 1, 0, "2027-03-01", "2027-06-10", "NO", "Kompilasi as-built dan manual operasi", "MAT-019", "Dokumen digital terkontrol", "Tim Dokumen Proyek", "Workstation BIM", "Dokumen vendor belum lengkap"),
    ("ACT-020", "9.3", "Serah terima dan masa pemeliharaan", "Handover", "ls", 1, 0, "2027-06-01", "2027-06-30", "YES", "Final inspection dan serah terima", "MAT-020", "Dossier serah terima", "Tim Proyek", "Inspection tools", "Punch list belum ditutup"),
]


RULES = [
    ("RULE-SCH-001", "Scheduling", "Jika task critical terlambat lebih dari 2 hari", "Buat alert dan eskalasi ke manager"),
    ("RULE-HSE-001", "HSE", "Jika toolbox meeting belum dikonfirmasi", "Blokir mulai pekerjaan"),
    ("RULE-QLT-001", "Quality", "Jika material wajib approval belum disetujui", "Blokir mulai pekerjaan"),
    ("RULE-QLT-002", "Quality", "Jika inspeksi wajib belum lulus", "Blokir penyelesaian task"),
    ("RULE-RSK-001", "Risk", "Jika NCR major masih terbuka", "Naikkan risk score task"),
    ("RULE-CST-001", "Cost", "Jika actual cost melampaui budget 5 persen", "Kirim peringatan cost overrun"),
    ("RULE-RES-001", "Resource", "Jika manpower aktual di bawah 70 persen rencana", "Minta recovery plan"),
    ("RULE-PRC-001", "Procurement", "Jika lead time material melewati kebutuhan", "Evaluasi vendor alternatif"),
    ("RULE-SCH-002", "Scheduling", "Jika predecessor belum selesai", "Blokir task successor"),
    ("RULE-QLT-003", "Quality", "Jika evidence foto kurang", "Kembalikan laporan untuk revisi"),
    ("RULE-RSK-002", "Risk", "Jika RFI lewat due date", "Buat escalation communication"),
    ("RULE-GEN-001", "General", "Jika laporan disetujui", "Terapkan volume ke kontrol task"),
]


def build_master() -> dict:
    chains = []
    for index, activity in enumerate(ACTIVITIES):
        (
            activity_id, wbs_code, name, discipline, unit, volume, progress,
            start, finish, critical, boq_description, material_code,
            material_description, vendor, equipment, risk_event,
        ) = activity
        total_price = (index + 1) * 650_000_000 + float(volume) * 85_000
        chains.append(
            {
                "wbs": {"wbs_code": wbs_code, "wbs_name": discipline},
                "boq": {
                    "boq_id": f"BOQ-{index + 1:03d}",
                    "description": boq_description,
                    "unit": unit,
                    "volume": volume,
                    "total_price_idr": total_price,
                },
                "activity": {
                    "activity_id": activity_id,
                    "name": name,
                    "discipline": discipline,
                    "early_start": f"{start}T00:00:00",
                    "early_finish": f"{finish}T00:00:00",
                    "progress_pct": progress,
                    "status": "complete" if progress >= 100 else "in progress" if progress else "not started",
                    "is_critical": critical,
                },
                "progress": {
                    "progress_pct": progress,
                    "actual_cost_idr": total_price * progress / 100 * 0.96,
                },
                "resource": {"manpower": 8 + (index % 5) * 4},
                "equipment": {"jenis": equipment},
                "material": {
                    "material_code": material_code,
                    "description": material_description,
                    "quality_standard": "SNI dan spesifikasi teknis proyek yang berlaku",
                    "vendor": vendor,
                },
                "risk": {
                    "risk_id": f"RISK-{index + 1:03d}",
                    "risk_event": risk_event,
                    "mitigation": "Pantau mingguan, tetapkan PIC, dan jalankan rencana mitigasi terukur.",
                },
                "network": {
                    "predecessors": [] if index == 0 else [f"ACT-{index:03d}|FS|0"],
                },
            }
        )
    return {
        "dataset_version": "CPMIS-DEMO-2026.1",
        "project_summary": PROJECT,
        "performance_at_data_date": {
            "data_date": "2026-08-12",
            "planned_pct": 32.5,
            "actual_pct": 28.7,
            "variance_pct": -3.8,
        },
        "linked_chains": chains,
        "rules_engine": [
            {
                "rule_id": rule_id,
                "kategori": category,
                "aturan": condition,
                "kondisi_if": condition,
                "aksi_then": action,
                "parameter": "project_control",
                "validasi": "automatic_or_manual",
                "sumber_standar": "CPMIS Demo Governance",
                "aktif": True,
            }
            for rule_id, category, condition, action in RULES
        ],
    }


def build_graph(master: dict) -> dict:
    nodes = [
        {
            "id": "PRJ:PITN-2026",
            "type": "project",
            "label": PROJECT["project_name"],
            "location": PROJECT["location"],
        }
    ]
    edges = []
    for chain in master["linked_chains"]:
        wbs = chain["wbs"]
        boq = chain["boq"]
        activity = chain["activity"]
        material = chain["material"]
        risk = chain["risk"]
        equipment = chain["equipment"]
        wbs_id = f"WBS:{wbs['wbs_code']}"
        boq_id = f"BOQ:{boq['boq_id']}"
        activity_id = f"ACT:{activity['activity_id']}"
        material_id = f"MAT:{material['material_code']}"
        risk_id = f"RSK:{risk['risk_id']}"
        equipment_id = f"EQP:{activity['activity_id']}"
        nodes.extend(
            [
                {"id": wbs_id, "type": "wbs", "label": wbs["wbs_name"]},
                {"id": boq_id, "type": "boq", "label": boq["description"], "value_idr": boq["total_price_idr"]},
                {"id": activity_id, "type": "activity", "label": activity["name"], "progress_pct": activity["progress_pct"]},
                {"id": material_id, "type": "material", "label": material["description"], "vendor": material["vendor"]},
                {"id": risk_id, "type": "risk", "label": risk["risk_event"]},
                {"id": equipment_id, "type": "equipment", "label": equipment["jenis"]},
            ]
        )
        edges.extend(
            [
                {"from": "PRJ:PITN-2026", "rel": "has_wbs", "to": wbs_id},
                {"from": wbs_id, "rel": "has_boq", "to": boq_id},
                {"from": boq_id, "rel": "executed_by", "to": activity_id},
                {"from": activity_id, "rel": "uses_material", "to": material_id},
                {"from": activity_id, "rel": "uses_equipment", "to": equipment_id},
                {"from": activity_id, "rel": "exposed_to", "to": risk_id},
            ]
        )
    return {"nodes": nodes, "edges": edges}


def build_instructions() -> list[dict]:
    prompts = [
        ("Ringkas kondisi proyek pada data date.", "Gunakan planned, actual, dan variance.", "Progres aktual 28,7%, tertinggal 3,8 poin dari rencana; fokuskan recovery pada struktur dan pengadaan critical."),
        ("Apa task yang tepat untuk demo Telegram?", "Pilih task assigned ke staff dengan WBS.", "Gunakan task lapangan aktif, kirim kode WBS, progres, tenaga kerja, cuaca, kendala, dan bukti foto."),
        ("Bagaimana menangani NCR mock-up?", "NCR major masih open.", "Tetapkan corrective action, unggah bukti perbaikan, lakukan inspeksi ulang, lalu tutup NCR setelah hasil passed."),
        ("Apa risiko pengadaan utama?", "Tinjau material dan aktivitas critical.", "Panel utama, kaca fasad, dan elevator memiliki lead time tinggi sehingga approval drawing dan vendor tracking harus dipercepat."),
        ("Bagaimana kontrol laporan harian?", "Gunakan workflow laporan CPMIS.", "Laporan harus memuat uraian, progres, tenaga kerja, volume, checklist, dan evidence sebelum masuk review."),
        ("Apa fungsi Digital Twin proyek?", "Hubungkan WBS, BOQ, aktivitas, material, alat, dan risiko.", "Digital Twin membuat hubungan sebab-akibat dapat ditelusuri dari aktivitas hingga risiko dan pemasok."),
        ("Bagaimana keputusan make-or-buy dibuat?", "Bandingkan biaya internal dan rate vendor.", "Gunakan produktivitas internal, biaya tenaga kerja, alat, material, risiko, mobilisasi, dan rating vendor."),
        ("Kapan task boleh diselesaikan?", "Periksa quality gate.", "Task selesai setelah volume terpenuhi, laporan disetujui, inspeksi wajib lulus, dan NCR major ditutup."),
        ("Bagaimana eskalasi RFI terlambat?", "RFI melewati due date.", "Ubah prioritas, kirim notifikasi manager, dan buat komunikasi escalation yang tercatat dalam audit trail."),
        ("Apa skenario presentasi terbaik?", "Demo lintas web dan Telegram.", "Login admin, tinjau dashboard, login staf atau gunakan Telegram untuk laporan, lalu review dan approve dari akun manager."),
    ]
    return [
        {"instruction": instruction, "input": context, "output": output}
        for instruction, context, output in prompts
    ]


def build_manifest() -> dict:
    return {
        "enabled": True,
        "profile": "full_feature_presentation",
        "seed_all_project_roles": True,
        "data_date": "2026-08-12T09:00:00",
        "blocked_activity_ids": ["ACT-003"],
        "critical_activity_ids": ["ACT-002", "ACT-004", "ACT-008", "ACT-011", "ACT-014"],
        "documents": [
            {
                "file_name": "01_Project_Brief_Demo.txt",
                "content": "Pusat Inovasi Terpadu Nusantara adalah proyek gedung riset dan kolaborasi. Nilai kontrak Rp187,5 miliar. Target utama adalah penyelesaian struktur, fasad, MEP, commissioning, dan serah terima pada Juni 2027. Risiko utama mencakup lead time material, konflik akses, koordinasi lintas disiplin, dan kelengkapan dokumen vendor.",
                "ai_analysis": {"project_name": PROJECT["project_name"], "risks": ["Lead time material", "Koordinasi lintas disiplin"], "generated_for_demo": True},
            },
            {
                "file_name": "02_Quality_and_HSE_Plan_Demo.txt",
                "content": "Setiap pekerjaan wajib melalui toolbox meeting, pemeriksaan APD, persetujuan material, inspeksi pekerjaan, bukti foto, dan penutupan NCR. Pekerjaan kritis tidak boleh dimulai apabila material atau predecessor belum memenuhi gate.",
                "ai_analysis": {"key_requirements": ["Toolbox meeting", "Material approval", "Inspection passed"], "generated_for_demo": True},
            },
            {
                "file_name": "03_Telegram_Demo_Guide.txt",
                "content": "Untuk update Telegram, jalankan /start lalu /tasks atau /report. Pilih task, kirim laporan berisi kode WBS, progres, volume, pekerja, cuaca, dan kendala. Kirim foto sebagai evidence lalu jalankan /submit. Data akan muncul pada halaman Reports di website.",
                "ai_analysis": {"channel": "telegram", "workflow": ["select_task", "send_progress", "upload_evidence", "submit"], "generated_for_demo": True},
            },
        ],
    }


def main() -> None:
    repository = Path(__file__).resolve().parents[2]
    output_dir = repository / "demo-data" / "pusat-inovasi-terpadu"
    output_dir.mkdir(parents=True, exist_ok=True)

    master = build_master()
    graph = build_graph(master)
    instructions = build_instructions()
    manifest = build_manifest()

    files = {
        "30_AI_Training_Dataset_Master.json": json.dumps(master, ensure_ascii=False, indent=2),
        "30_AI_Knowledge_Graph.json": json.dumps(graph, ensure_ascii=False, indent=2),
        "30_AI_Instruction_Dataset.jsonl": "\n".join(json.dumps(item, ensure_ascii=False) for item in instructions) + "\n",
        "CPMIS_Demo_Features.json": json.dumps(manifest, ensure_ascii=False, indent=2),
        "README_DEMO.txt": (
            "Paket dummy CPMIS untuk presentasi multi-project.\n"
            "Unggah ZIP melalui halaman Setup atau Admin Console dan isi Telegram ID staf.\n"
            "Data bersifat fiktif dan hanya untuk demonstrasi.\n"
        ),
    }
    for name, content in files.items():
        (output_dir / name).write_text(content, encoding="utf-8")

    archive_path = repository / "demo-data" / "CPMIS_Demo_Pusat_Inovasi_2026.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(output_dir / name, arcname=name)
    print({"archive": str(archive_path), "tasks": len(ACTIVITIES), "files": len(files)})


if __name__ == "__main__":
    main()
