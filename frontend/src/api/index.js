import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 120s for AI deep reasoning
})

export const fetchFeed = (params) => api.get('/recommend/feed', { params }).then(res => res.data)
export const fetchAlgorithms = () => api.get('/recommend/algorithms').then(res => res.data)
export const fetchAssets = (params) => api.get('/assets', { params }).then(res => res.data)
export const fetchAssetDetail = (id) => api.get(`/assets/${id}`).then(res => res.data)
export const rateAsset = (id, rating, isFavorite) => api.post(`/assets/${id}/rate`, { rating, is_favorite: isFavorite }).then(res => res.data)

export const fetchCollections = () => api.get('/collections').then(res => res.data)
export const fetchSupersets = () => api.get('/supersets').then(res => res.data)
export const createSuperset = (data) => api.post('/supersets', data).then(res => res.data)
export const addItemToSuperset = (supersetId, unitId) => api.post(`/supersets/${supersetId}/items`, { unit_id: unitId }).then(res => res.data)

export const triggerScan = (path) => api.post('/scan', { path }).then(res => res.data)
export const logTelemetry = (unitId, action, dwellSeconds = 0) => api.post('/telemetry/log', { unit_id: unitId, action, dwell_seconds: dwellSeconds }).then(res => res.data)

export const revealInExplorer = (params) => api.post('/system/reveal', params).then(res => res.data)
export const openWithDefaultApp = (params) => api.post('/system/open', params).then(res => res.data)
export const fetchMemoryRecapContext = () => api.get('/ai/memory_recap_context').then(res => res.data)

// AI Deep Organizer API
export const analyzeFolderWithAI = (folderPath, instruction = '') =>
  api.post('/ai/analyze_folder', { folder_path: folderPath, instruction }).then(res => res.data)

export const applyAITriagePlan = (folderPath, plan) =>
  api.post('/ai/apply_triage', { folder_path: folderPath, plan }).then(res => res.data)

export const fetchAISettings = () => api.get('/ai/settings').then(res => res.data)

export default api
