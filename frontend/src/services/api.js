import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 统一错误处理
function handleError(e) {
  const msg = e.response?.data?.detail || e.response?.data?.message || e.message || '请求失败'
  return { success: false, message: msg, code: e.response?.status || 500 }
}

export const API = {
  // === 系统 ===
  async getStatus() {
    try { const { data } = await api.get('/system/status'); return data }
    catch (e) { return handleError(e) }
  },
  async getHealth() {
    try { const { data } = await api.get('/system/health'); return data }
    catch (e) { return handleError(e) }
  },

  // === CAD解析 (接口1) ===
  async analyzeCad(file, projectName = '装修工程') {
    try {
      const fd = new FormData()
      fd.append('cad_file', file)
      if (projectName) fd.append('project_name', projectName)
      const { data } = await api.post('/analyze_full', fd, { timeout: 120000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === 效果图识别 (接口2) ===
  async analyzeImage(file) {
    try {
      const fd = new FormData()
      fd.append('image_file', file)
      const { data } = await api.post('/analyze', fd, { timeout: 120000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === 数据融合 (接口3) ===
  async dataMerge(cadResultId, imageResultIds = [], manualBindings = []) {
    try {
      const fd = new FormData()
      fd.append('cad_result_id', cadResultId)
      fd.append('image_result_ids', JSON.stringify(imageResultIds))
      fd.append('manual_bindings', JSON.stringify(manualBindings))
      const { data } = await api.post('/data_merge', fd, { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === Excel导出 (接口4) ===
  async exportExcel(quoteId) {
    try {
      const fd = new FormData()
      fd.append('quote_id', quoteId)
      const { data } = await api.post('/export_excel', fd, { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === 历史记录 (接口5-7) ===
  async getHistory(page = 1, pageSize = 20) {
    try { const { data } = await api.get(`/history?page=${page}&page_size=${pageSize}`); return data }
    catch (e) { return handleError(e) }
  },
  async getHistoryDetail(quoteId) {
    try { const { data } = await api.get(`/history/${quoteId}`); return data }
    catch (e) { return handleError(e) }
  },
  async deleteHistory(quoteId) {
    try { const { data } = await api.delete(`/history/${quoteId}`); return data }
    catch (e) { return handleError(e) }
  },

  // === 操作日志 ===
  async getLogs(page = 1, pageSize = 50) {
    try { const { data } = await api.get(`/logs?page=${page}&page_size=${pageSize}`); return data }
    catch (e) { return handleError(e) }
  },

  // === 定价配置 (接口10) ===
  async getPricing() {
    try { const { data } = await api.get('/settings/pricing'); return data }
    catch (e) { return handleError(e) }
  },
  async updatePricing(key, value) {
    try {
      const fd = new FormData()
      fd.append('key', key)
      fd.append('value', value)
      const { data } = await api.post('/settings/pricing', fd)
      return data
    } catch (e) { return handleError(e) }
  },

  // === 分层工程量 ===
  async computeBreakdown(drawingId) {
    try { const { data } = await api.post(`/spaces/${drawingId}/compute_breakdown`); return data }
    catch (e) { return handleError(e) }
  },
  async getBreakdown(drawingId) {
    try { const { data } = await api.get(`/spaces/${drawingId}/breakdown`); return data }
    catch (e) { return handleError(e) }
  },
  async bindSurfaceMaterial(cadId, surface, materialName, materialCode = '') {
    try {
      const fd = new FormData()
      fd.append('cad_id', cadId)
      fd.append('surface', surface)
      fd.append('material_name', materialName)
      fd.append('material_code', materialCode)
      const { data } = await api.post('/spaces/breakdown/bind_material', fd)
      return data
    } catch (e) { return handleError(e) }
  },

  // === 自动匹配建议 (新增) ===
  async autoSuggestMatch(drawingId, imageResultIds = []) {
    try {
      const fd = new FormData()
      fd.append('drawing_id', drawingId)
      fd.append('image_result_ids', JSON.stringify(imageResultIds))
      const { data } = await api.post('/spaces/auto_suggest_match', fd, { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === 确认绑定 (新增) ===
  async autoConfirmMatch(cadResultId, imageResultId, surfaceMaterials = null) {
    try {
      const fd = new FormData()
      fd.append('cad_result_id', cadResultId)
      fd.append('image_result_id', imageResultId)
      if (surfaceMaterials) fd.append('surface_materials', JSON.stringify(surfaceMaterials))
      const { data } = await api.post('/spaces/auto_confirm_match', fd, { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // 通用HTTP方法
  async get(path) {
    try { const { data } = await api.get(path); return data }
    catch (e) { return handleError(e) }
  },
  async post(path, body) {
    try { const { data } = await api.post(path, body); return data }
    catch (e) { return handleError(e) }
  },
  async put(path, body) {
    try {
      const headers = body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
      const { data } = await api.put(path, body, { headers })
      return data
    } catch (e) { return handleError(e) }
  },
  async delete(path) {
    try { const { data } = await api.delete(path); return data }
    catch (e) { return handleError(e) }
  },
}

export default API
