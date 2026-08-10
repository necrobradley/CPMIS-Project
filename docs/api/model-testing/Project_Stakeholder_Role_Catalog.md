# Project Stakeholder Role Catalog

Dokumen ini menjelaskan katalog role proyek yang dipakai CPMIS Model Testing untuk menempatkan staff dan stakeholder pada proyek.

## Prinsip Desain

- `UserRole` tetap dipakai untuk RBAC aplikasi: admin, director, manager, staff, subcontractor.
- `project_role` dipakai untuk jabatan orang pada proyek tertentu.
- Satu user bisa memiliki role aplikasi yang sama, tetapi jabatan proyek berbeda pada proyek yang berbeda.
- Role proyek membantu assignment task, komunikasi, reminder, approval routing, dan pembatasan visibility.

## Kelompok Role

| Kelompok | Contoh Role |
|---|---|
| Owner & Executive | Project Sponsor, Owner Representative, Client Stakeholder |
| Project Management | Project Manager, Deputy PM, Construction Manager, Site Manager, Division Lead |
| Engineering & Design | Project Engineer, Site Engineer, Field Engineer, Structural Engineer, MEP Engineer, Architectural Engineer, Drafter, BIM Modeler, Surveyor |
| Planning & Controls | Planning Engineer, Scheduler, Cost Controller, Quantity Surveyor, Document Controller |
| Quality & Safety | QA/QC Manager, QA/QC Engineer, Inspector, HSE Manager, HSE Officer |
| Commercial & Procurement | Contract Manager, Finance Manager, Project Accountant, Procurement Manager, Procurement Officer, Logistics Coordinator |
| Field Execution | Supervisor, Foreman/Mandor, Field Staff, Warehouse Keeper, Staff |
| External Parties | Subcontractor, Vendor/Supplier, Consultant, Authority Reviewer, Auditor, Viewer |

## Implementasi Sistem

- Katalog role backend ada di `backend/app/services/project_role_catalog.py`.
- Endpoint katalog role: `GET /api/v1/projects/member-roles`.
- Detail proyek memakai katalog ini untuk dropdown **Tempatkan staff**.
- Task Board memakai katalog ini untuk menentukan calon PIC yang relevan.
- Role lintas divisi seperti Project Manager, Deputy PM, Construction Manager, Site Manager, Planning Engineer, QA/QC Manager, HSE Manager, Contract Manager, Procurement Manager, Consultant, dan Auditor dapat melihat/menangani lintas divisi sesuai RBAC.
- Role financial project seperti Cost Controller, Quantity Surveyor, Contract Manager, Finance Manager, dan Project Accountant dapat melihat kontrol biaya/kontrak pada proyek tempat mereka menjadi member aktif.
- Communication Hub memakai membership proyek untuk Ball-in-court dan mention lintas divisi. User tujuan harus anggota aktif proyek.
- Task Detail, Task Board, Controls, Reports, Telegram auto grouping, reminder automation, dan Communication Hub memakai katalog role yang sama.

## Template Divisi Project Setup

Detail proyek menyediakan template cepat untuk menambahkan divisi umum proyek:

- Project Management
- Site Management
- Engineering
- Architecture
- MEP
- BIM / Digital Engineering
- Survey
- Planning & Controls
- Cost Control
- Quantity Surveying
- Finance & Accounting
- Commercial / Contract
- Procurement
- Logistics
- Warehouse
- Document Control
- QA/QC
- HSE
- Site Execution
- Administration / GA
- HR / People
- Legal & Permit
- IT / Digital Support
- Security
- Owner / Executive
- Consultant
- Subcontractor
- Vendor / Supplier

## Catatan

Referensi role mengikuti pola umum struktur proyek konstruksi global: sponsor/owner, project management, engineering/design, planning/control, commercial/procurement, QA/QC, HSE, document control, site execution, subcontractor/vendor, consultant, dan authority reviewer.
