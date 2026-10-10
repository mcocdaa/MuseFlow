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
export const createSupersetFromQueue = (data) => api.post('/supersets/from_queue', data).then(res => res.data)
export const addItemToSuperset = (supersetId, unitId) => api.post(`/supersets/${supersetId}/items`, { unit_id: unitId }).then(res => res.data)
export const addItemsBatchToSuperset = (supersetId, unitIds) => api.post(`/supersets/${supersetId}/items_batch`, { unit_ids: unitIds }).then(res => res.data)
export const removeItemFromSuperset = (supersetId, unitId) => api.delete(`/supersets/${supersetId}/items/${unitId}`).then(res => res.data)
export const deleteSuperset = (supersetId) => api.delete(`/supersets/${supersetId}`).then(res => res.data)

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

// Physical Organizer & Maintenance API
export const fetchMaintenanceStatus = () => api.get('/organize/maintenance').then(res => res.data)
export const inspectFolderScope = (folderPath) => api.post('/organize/inspect', { folder_path: folderPath }).then(res => res.data)
export const planTriage = (folderPath, rule, options = {}) => api.post('/organize/plan', { folder_path: folderPath, rule, options }).then(res => res.data)
export const executeTriagePlan = (plan, dryRun = false) => api.post('/organize/execute', { plan, dry_run: dryRun }).then(res => res.data)

// OOP Tag Taxonomy & Pipeline DSL API
export const fetchTagClasses = () => api.get('/tags/classes').then(res => res.data)
export const fetchTagTree = () => api.get('/tags/tree').then(res => res.data)
export const fetchAllTagsFlat = () => api.get('/tags/all').then(res => res.data)
export const fetchUnitTags = (unitId) => api.get(`/tags/units/${unitId}`).then(res => res.data)
export const createTag = (data) => api.post('/tags/', data).then(res => res.data)
export const updateTagParent = (id, newParentId) => api.put(`/tags/${id}/parent`, { new_parent_id: newParentId }).then(res => res.data)
export const deleteTagApi = (tagId) => api.delete(`/tags/${tagId}`).then(res => res.data)
export const assignTag = (unitId, data) => api.post(`/tags/units/${unitId}/assign`, data).then(res => res.data)
export const removeTag = (unitId, tagId) => api.delete(`/tags/units/${unitId}/remove/${tagId}`).then(res => res.data)
export const fetchPipelinePresets = () => api.get('/organize/pipeline/presets').then(res => res.data)
export const evaluatePipeline = (payload) => api.post('/organize/pipeline/evaluate', payload).then(res => res.data)
export const fetchTagAliases = (tagId) => api.get(`/tags/${tagId}/aliases`).then(res => res.data)
export const addTagAlias = (tagId, data) => api.post(`/tags/${tagId}/aliases`, data).then(res => res.data)
export const removeTagAlias = (aliasId) => api.delete(`/tags/aliases/${aliasId}`).then(res => res.data)
export const resolveConceptTag = (term) => api.get('/tags/concept/resolve', { params: { term } }).then(res => res.data)

export default api


