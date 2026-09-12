import axios from 'axios'

const API_BASE = '/api'

export const api = {
  // Upload
  uploadFile: (formData: FormData) => axios.post(`${API_BASE}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progress) => {
      // Progress handled by component
    }
  }),
  uploadModelZip: (formData: FormData) => axios.post(`${API_BASE}/models`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // API endpoints
  getForecast: () => axios.get(`${API_BASE}/forecast`),
  getGraph: () => axios.get(`${API_BASE}/graph`),
  getCounterfactual: () => axios.get(`${API_BASE}/counterfactual`),
  getEvaluation: () => axios.get(`${API_BASE}/evaluation`),
  getTopology: () => axios.get(`${API_BASE}/topology`),
  getEntities: () => axios.get(`${API_BASE}/entities`),
  getEntityDetail: (entityId: string) => axios.get(`${API_BASE}/entities/${entityId}`),
  getEdgeDetail: (srcId: string, dstId: string) => axios.get(`${API_BASE}/edges/${srcId}/${dstId}`),
  getMitre: () => axios.get(`${API_BASE}/mitre`),
  getModels: () => axios.get(`${API_BASE}/models`),
  getModelsStatus: () => axios.get(`${API_BASE}/models/status`),
  postScenario: (data: any) => axios.post(`${API_BASE}/scenario`, data),
  retrain: () => axios.post(`${API_BASE}/retrain`),

  // Analysis API
  getAnalysis: () => axios.get(`${API_BASE}/api/analysis`),
}