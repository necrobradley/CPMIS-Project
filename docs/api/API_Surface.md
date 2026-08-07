# API Surface - DigiCom PMIS / CPMIS

Status: Active
Owner: Engineering
Last updated: 2026-07-02

## 1. Purpose

Dokumen ini merangkum permukaan API utama CPMIS. Detail kontrak request/response tetap mengacu pada Swagger/OpenAPI di:

```text
http://localhost:8003/docs
```

## 2. API Principles

- Semua endpoint aplikasi berada di bawah `/api/v1`.
- Endpoint yang membaca data user/project wajib memakai JWT.
- Permission wajib ditegakkan di backend.
- Endpoint upload wajib membatasi tipe file dan ukuran.
- Endpoint AI wajib melewati Secure AI Gateway.
- Endpoint n8n wajib memakai secret dan rate limit.

## 3. Module API Map

| Module | Prefix | Owner | Security |
| --- | --- | --- | --- |
| Auth | `/api/v1/auth` | Identity | JWT, rate limit |
| Users | `/api/v1/users` | Admin / Identity | RBAC admin, contact filtering |
| Projects | `/api/v1/projects` | Project Management | Project access, role policy |
| Tasks | `/api/v1/tasks` | Work Management | Project/task access |
| Reports | `/api/v1/reports` | Field Reporting | Reporter/reviewer workflow |
| Documents | `/api/v1/documents` | Document Control | Project access, sensitive doc filter |
| Controls | `/api/v1/controls` | Construction Controls | Manager/control roles |
| Communications | `/api/v1/communications` | Communication Hub | Project access |
| Approvals | `/api/v1/approvals` | Governance | Approver/reviewer roles |
| Notifications | `/api/v1/notifications` | System | Current user scoped |
| AI | `/api/v1/ai` | AI Platform | Secure AI Gateway, rate limit |
| n8n | `/api/v1/n8n` | Automation | Webhook secret, rate limit |
| Settings | `/api/v1/settings` | Admin / Commercial | Admin RBAC |
| Audit | `/api/v1/audit` | Compliance | Admin/director/manager |
| Research | `/api/v1/research` | Research / Thesis | Controlled access |
| System | `/api/v1/system` | Operations | Readiness/status |

## 4. Critical Endpoint Groups

### Authentication

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | Login and issue tokens |
| POST | `/api/v1/auth/register` | Register account |
| POST | `/api/v1/auth/refresh` | Refresh token |
| GET | `/api/v1/auth/me` | Current user profile |

### Project Setup

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/projects` | List accessible projects |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects/{id}` | Project detail |
| GET | `/api/v1/projects/{id}/divisions` | Project divisions |
| GET | `/api/v1/projects/{id}/members` | Project members |
| GET | `/api/v1/projects/member-roles` | Project role catalog |
| GET/PATCH | `/api/v1/projects/{id}/role-policy` | Role policy |

### User and Role Setup

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/users` | List users |
| POST | `/api/v1/users/setup` | Create account and optional project assignment |
| PATCH | `/api/v1/users/{id}/setup` | Update existing account/project assignment |
| GET | `/api/v1/users/by-telegram/{telegram_id}` | Resolve Telegram user |

### Documents and RAG

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/documents/upload` | Upload document and optional AI analysis |
| GET | `/api/v1/documents` | List documents by project |
| POST | `/api/v1/documents/qa` | Project-scoped document Q&A |
| GET | `/api/v1/documents/{id}/download-url` | Signed download URL |
| POST | `/api/v1/documents/{id}/sync/preview` | Preview document sync |
| POST | `/api/v1/documents/sync/{id}/request-approval` | Request sync approval |
| POST | `/api/v1/documents/sync/{id}/apply` | Apply approved sync |

### Reports

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/reports` | List reports |
| POST | `/api/v1/reports` | Create daily report |
| PATCH | `/api/v1/reports/{id}` | Update draft report |
| POST | `/api/v1/reports/{id}/evidence` | Upload evidence |
| POST | `/api/v1/reports/{id}/submit` | Submit and validate report |
| PATCH | `/api/v1/reports/{id}/decision` | Review/approve report |
| POST | `/api/v1/reports/telegram/auto-group/preview` | Preview Telegram report grouping |

### AI

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/ai/chat` | Free chat with project context |
| POST | `/api/v1/ai/analyze-document` | Analyze uploaded document |
| POST | `/api/v1/ai/generate-tasks/{project_id}` | Generate tasks from document analysis |
| POST | `/api/v1/ai/summarize-report/{report_id}` | Summarize report |

## 5. Security Notes

High-risk endpoints:

- Login and refresh token.
- User setup and role assignment.
- Document upload/download/sync.
- AI and document QA.
- n8n callbacks.
- Settings/admin/commercial tenant management.

Required controls:

- Rate limit.
- Audit log for state-changing actions.
- Role/project access checks.
- File type/size validation for uploads.
- Secure AI Gateway for external AI.
- Signed URL for file download.

## 6. API Change Management

When adding or changing endpoints:

1. Update Pydantic schema.
2. Add or update backend tests.
3. Update frontend API client if needed.
4. Update this document if endpoint is user-facing or security-sensitive.
5. Update security docs if auth, RBAC, upload, AI, tenant, or document access changes.
