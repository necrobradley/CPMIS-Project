import axios from 'axios'
import Cookies from 'js-cookie'
import { apiDetailMessage } from '@/lib/api-error'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach token to every request
api.interceptors.request.use((config) => {
  const token = Cookies.get('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh / logout on 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = Cookies.get('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
            refresh_token: refresh,
          })
          Cookies.set('access_token', data.access_token, { expires: 1 })
          Cookies.set('refresh_token', data.refresh_token, { expires: 7 })
          original.headers.Authorization = `Bearer ${data.access_token}`
          return api(original)
        } catch {
          Cookies.remove('access_token')
          Cookies.remove('refresh_token')
          window.location.href = '/login'
        }
      } else {
        window.location.href = '/login'
      }
    }
    const responseData = err.response?.data
    if (responseData && typeof responseData === 'object' && 'detail' in responseData) {
      const normalizedDetail = apiDetailMessage(responseData.detail)
      if (normalizedDetail) responseData.detail = normalizedDetail
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
  register: (data: Record<string, unknown>) => api.post('/auth/register', data),
}

// ── Projects ──────────────────────────────────
export const projectsApi = {
  list: (status?: string) => api.get('/projects', { params: status ? { status } : {} }),
  memberRoles: () => api.get('/projects/member-roles'),
  rolePolicy: (id: number) => api.get(`/projects/${id}/role-policy`),
  updateRolePolicy: (id: number, roleCode: string, enabled: boolean) =>
    api.patch(`/projects/${id}/role-policy/${roleCode}`, { enabled }),
  get:  (id: number) => api.get(`/projects/${id}`),
  create: (data: Record<string, unknown>) => api.post('/projects', data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/projects/${id}`, data),
  delete: (id: number) => api.delete(`/projects/${id}`),
  divisions: (id: number) => api.get(`/projects/${id}/divisions`),
  createDivision: (id: number, data: Record<string, unknown>) => api.post(`/projects/${id}/divisions`, data),
  updateDivision: (projectId: number, divisionId: number, data: Record<string, unknown>) =>
    api.put(`/projects/${projectId}/divisions/${divisionId}`, data),
  deleteDivision: (projectId: number, divisionId: number) =>
    api.delete(`/projects/${projectId}/divisions/${divisionId}`),
  members: (id: number, divisionId?: number) =>
    api.get(`/projects/${id}/members`, { params: divisionId ? { division_id: divisionId } : {} }),
  addMember: (id: number, data: Record<string, unknown>) => api.post(`/projects/${id}/members`, data),
  updateMember: (projectId: number, membershipId: number, data: Record<string, unknown>) =>
    api.put(`/projects/${projectId}/members/${membershipId}`, data),
  removeMember: (projectId: number, membershipId: number) =>
    api.delete(`/projects/${projectId}/members/${membershipId}`),
}

// ── Tasks ─────────────────────────────────────
export const tasksApi = {
  list: (params?: Record<string, unknown>) => api.get('/tasks', { params }),
  get:  (id: number) => api.get(`/tasks/${id}`),
  create: (data: Record<string, unknown>) => api.post('/tasks', data),
  update: (id: number, data: Record<string, unknown>) => api.put(`/tasks/${id}`, data),
  updateStatus: (id: number, status: string) =>
    api.patch(`/tasks/${id}/status`, null, { params: { status } }),
  delete: (id: number) => api.delete(`/tasks/${id}`),
  subtasks: (id: number) => api.get(`/tasks/${id}/subtasks`),
  materials: (id: number) => api.get(`/tasks/${id}/materials`),
  createMaterial: (id: number, data: Record<string, unknown>) => api.post(`/tasks/${id}/materials`, data),
  updateMaterial: (taskId: number, materialId: number, data: Record<string, unknown>) =>
    api.put(`/tasks/${taskId}/materials/${materialId}`, data),
  deleteMaterial: (taskId: number, materialId: number) => api.delete(`/tasks/${taskId}/materials/${materialId}`),
}

// ── Reports ───────────────────────────────────
export const reportsApi = {
  list: (params?: Record<string, unknown>) => api.get('/reports', { params }),
  get:  (id: number) => api.get(`/reports/${id}`),
  create: (data: Record<string, unknown>) => api.post('/reports', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/reports/${id}`, data),
  uploadEvidence: (id: number, formData: FormData) =>
    api.post(`/reports/${id}/evidence`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  evidenceDownloadUrl: (id: number) => api.get(`/reports/evidence/${id}/download-url`),
  deleteEvidence: (id: number) => api.delete(`/reports/evidence/${id}`),
  submit: (id: number) => api.post(`/reports/${id}/submit`),
  decide: (id: number, decision: string, note?: string) =>
    api.patch(`/reports/${id}/decision`, { decision, note }),
  delete: (id: number) => api.delete(`/reports/${id}`),
}

// Construction Project Controls
export const controlsApi = {
  myWork: () => api.get('/controls/my-work'),
  summary: (projectId: number) => api.get(`/controls/projects/${projectId}/summary`),
  vendors: (projectId: number) => api.get(`/controls/projects/${projectId}/vendors`),
  createVendor: (projectId: number, data: Record<string, unknown>) =>
    api.post(`/controls/projects/${projectId}/vendors`, data),
  updateVendor: (vendorId: number, data: Record<string, unknown>) =>
    api.patch(`/controls/vendors/${vendorId}`, data),
  createVendorRate: (vendorId: number, data: Record<string, unknown>) =>
    api.post(`/controls/vendors/${vendorId}/rates`, data),
  productivity: (projectId: number) => api.get(`/controls/projects/${projectId}/productivity`),
  createProductivity: (projectId: number, data: Record<string, unknown>) =>
    api.post(`/controls/projects/${projectId}/productivity`, data),
  updateProductivity: (benchmarkId: number, data: Record<string, unknown>) =>
    api.patch(`/controls/productivity/${benchmarkId}`, data),
  bootstrapBaseline: (projectId: number) => api.post(`/controls/projects/${projectId}/baseline/bootstrap`),
  taskGate: (taskId: number) => api.get(`/controls/tasks/${taskId}/gate`),
  taskPlan: (taskId: number) => api.get(`/controls/tasks/${taskId}/plan`),
  updateTaskPlan: (taskId: number, data: Record<string, unknown>) =>
    api.put(`/controls/tasks/${taskId}/plan`, data),
  addDependency: (taskId: number, data: Record<string, unknown>) =>
    api.post(`/controls/tasks/${taskId}/dependencies`, data),
  decideMaterial: (materialId: number, status: string, note?: string) =>
    api.patch(`/controls/materials/${materialId}/approval`, { status, note }),
  createInspection: (data: Record<string, unknown>) => api.post('/controls/inspections', data),
  decideInspection: (inspectionId: number, data: Record<string, unknown>) =>
    api.patch(`/controls/inspections/${inspectionId}/decision`, data),
  updateNcr: (ncrId: number, data: Record<string, unknown>) =>
    api.patch(`/controls/ncr/${ncrId}`, data),
  clearRevision: (taskId: number, note?: string) =>
    api.post(`/controls/tasks/${taskId}/revision/clear`, null, { params: { note } }),
  refreshHandover: (projectId: number) => api.post(`/controls/projects/${projectId}/handover/refresh`),
}

// ── Users ─────────────────────────────────────
export const usersApi = {
  list: (projectId?: number) => api.get('/users', { params: projectId ? { project_id: projectId } : {} }),
  setup: (data: Record<string, unknown>) => api.post('/users/setup', data),
  importCsv: (formData: FormData) =>
    api.post('/users/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  updateSetup: (id: number, data: Record<string, unknown>) => api.patch(`/users/${id}/setup`, data),
  changeMyPassword: (data: Record<string, unknown>) => api.patch('/users/me/password', data),
  uploadMyAvatar: (formData: FormData) =>
    api.post('/users/me/avatar', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  get:  (id: number) => api.get(`/users/${id}`),
  update: (id: number, data: Record<string, unknown>) => api.put(`/users/${id}`, data),
}

// ── AI ────────────────────────────────────────
export const aiApi = {
  models:          () => api.get('/ai/models'),
  chat:            (message: string, project_id?: number, provider?: string, model?: string) =>
    api.post('/ai/chat', null, { params: { message, project_id, provider, model } }),
  summarizeReport: (reportId: number) =>
    api.post(`/ai/summarize-report/${reportId}`),
  generateTasks:   (projectId: number, documentId: number) =>
    api.post(`/ai/generate-tasks/${projectId}`, null, { params: { document_id: documentId } }),
  analyzeDocument: (formData: FormData) =>
    api.post('/ai/analyze-document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

// ── Documents ─────────────────────────────────────────────────
export const documentsApi = {
  list: (project_id: number, doc_type?: string) =>
    api.get('/documents', { params: { project_id, doc_type } }),
  upload: (formData: FormData) =>
    api.post('/documents/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  qa: (project_id: number, question: string) =>
    api.post('/documents/qa', { project_id, question }),
  downloadUrl: (id: number) => api.get(`/documents/${id}/download-url`),
  analysis: (id: number) => api.get(`/documents/${id}/analysis`),
  previewSync: (id: number, includeTasks = true, forceNew = false) =>
    api.post(`/documents/${id}/sync/preview`, { include_tasks: includeTasks, force_new: forceNew }),
  getSync: (id: number) => api.get(`/documents/sync/${id}`),
  requestSyncApproval: (id: number, changeIds: string[], approverId?: number) =>
    api.post(`/documents/sync/${id}/request-approval`, { change_ids: changeIds, approver_id: approverId }),
  applySync: (id: number) => api.post(`/documents/sync/${id}/apply`),
  delete: (id: number) => api.delete(`/documents/${id}`),
}

// ── Notifications ─────────────────────────────────────────────
export const notificationsApi = {
  list: (unread_only?: boolean) => api.get('/notifications', { params: { unread_only } }),
  unreadCount: () => api.get('/notifications/unread-count'),
  markRead: (id: number) => api.patch(`/notifications/${id}/read`),
  markAllRead: () => api.patch('/notifications/read-all'),
}

// Settings
export const settingsApi = {
  features: () => api.get('/settings/features'),
  updateFeature: (featureKey: string, enabled: boolean) =>
    api.patch(`/settings/features/${featureKey}`, { enabled }),
  commercialPlans: () => api.get('/settings/commercial/plans'),
  commercialReadiness: () => api.get('/settings/commercial/readiness'),
  commercialTenants: () => api.get('/settings/commercial/tenants'),
  createCommercialTenant: (data: Record<string, unknown>) =>
    api.post('/settings/commercial/tenants', data),
  updateCommercialTenant: (tenantId: number, data: Record<string, unknown>) =>
    api.patch(`/settings/commercial/tenants/${tenantId}`, data),
  tenantEntitlements: (tenantId: number) =>
    api.get(`/settings/commercial/tenants/${tenantId}/entitlements`),
  updateTenantEntitlement: (tenantId: number, featureKey: string, enabled: boolean, notes?: string) =>
    api.patch(`/settings/commercial/tenants/${tenantId}/entitlements/${featureKey}`, { enabled, notes }),
  tenantUsage: (tenantId: number) => api.get(`/settings/commercial/tenants/${tenantId}/usage`),
}

// ── Compliance ────────────────────────────────────────────────
export const complianceApi = {
  check: (project_id: number) => api.post(`/compliance/${project_id}/check`),
  summary: (project_id: number) => api.get(`/compliance/${project_id}/summary`),
}

// Approvals
export const approvalsApi = {
  list: (params?: Record<string, unknown>) => api.get('/approvals', { params }),
  create: (data: Record<string, unknown>) => api.post('/approvals', data),
  decide: (id: number, status: string, decision_note?: string) =>
    api.patch(`/approvals/${id}/decision`, { status, decision_note }),
}

// Communications
export const communicationsApi = {
  list: (params?: Record<string, unknown>) => api.get('/communications', { params }),
  get: (id: number) => api.get(`/communications/${id}`),
  create: (data: Record<string, unknown>) => api.post('/communications', data),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/communications/${id}`, data),
  message: (id: number, data: Record<string, unknown>) => api.post(`/communications/${id}/messages`, data),
  uploadAttachment: (id: number, formData: FormData) =>
    api.post(`/communications/${id}/attachments`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  markRead: (id: number) => api.post(`/communications/${id}/read`),
  escalate: (id: number, data: Record<string, unknown>) => api.post(`/communications/${id}/escalate`, data),
  runSlaEscalation: () => api.post('/communications/sla/escalate-overdue'),
  attachmentDownloadUrl: (id: number) => api.get(`/communications/attachments/${id}/download-url`),
}

// Audit trail
export const auditApi = {
  list: (params?: Record<string, unknown>) => api.get('/audit', { params }),
  recent: (limit?: number) => api.get('/audit/recent', { params: { limit } }),
}

// Research export
export const researchApi = {
  export: (format: 'json' | 'csv' = 'json', anonymize = true) =>
    api.get('/research/export', { params: { format, anonymize }, responseType: format === 'csv' ? 'blob' : 'json' }),
}

// System readiness
export const systemApi = {
  status: () => api.get('/system/status'),
  bootstrapMnbc: (formData: FormData, bootstrapSecret: string) =>
    api.post('/system/bootstrap/mnbc', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'X-Bootstrap-Secret': bootstrapSecret,
      },
    }),
  importMnbc: (formData: FormData) =>
    api.post('/system/import/mnbc', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}
