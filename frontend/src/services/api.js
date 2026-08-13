/**
 * 前端后端接口统一封装。
 * 本文件负责配置 Axios、组织请求参数并统一转换请求错误；页面组件应通过 API 对象调用后端，
 * 业务状态与界面逻辑由对应的状态模块和 Vue 组件维护，不在此处保存。
 */
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
  async analyzeCad(file, projectName = '装修工程', manualMeasurement = null) {
    try {
      const fd = new FormData()
      fd.append('cad_file', file)
      if (projectName) fd.append('project_name', projectName)
      if (manualMeasurement) fd.append('manual_measurement', JSON.stringify(manualMeasurement))// 人工优先、无人工再自动
      const { data } = await api.post('/analyze_full', fd, { timeout: 120000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === 人工标注测量 ===
  // 从后端取得完整的标注文件格式能力表
  async getMeasurementCapabilities() {
    try {
      const { data } = await api.get('/measurement/capabilities')
      return data
    } catch (e) { return handleError(e) }
  },
  async prepareMeasurement(file) {
    try {
      const fd = new FormData()
      fd.append('source_file', file)
      const { data } = await api.post('/measurement/prepare', fd, { timeout: 120000 })
      return data
    } catch (e) { return handleError(e) }
  },
    async calculateMeasurement(drawingId, sourceFormat, rooms, unitOverride = null, calibration = null) {
    try {
      const payload = { drawing_id: drawingId, source_format: sourceFormat, rooms }
      if (unitOverride) payload.unit_override = unitOverride
      if (calibration) payload.calibration = calibration
      const { data } = await api.post('/measurement/calculate', payload, { timeout: 60000 })
      return data
      } catch (e) { return handleError(e) }
    },
    async saveMeasurement(drawingId, sourceFormat, rooms, unitOverride = null, calibration = null) {
      try {
        const payload = { drawing_id: drawingId, source_format: sourceFormat, rooms }
        if (unitOverride) payload.unit_override = unitOverride
        if (calibration) payload.calibration = calibration
        const { data } = await api.post('/measurement/save', payload, { timeout: 60000 })
        return data
      } catch (e) { return handleError(e) }
    },
  async getMeasurementView(drawingId, viewId) {
    try {
      const { data } = await api.get(`/measurement/${drawingId}/views/${encodeURIComponent(viewId)}`, { timeout: 60000 })
      return data
    } catch (e) { return handleError(e) }
  },

  // === 效果图识别 (接口2) ===
  async analyzeImage(file, { model = '', cropEnabled = true, fullEnabled = false, drawingId = 0, fileCount = 1, batchId = null } = {}) {
    const fd = new FormData()
    fd.append('image_file', file)
    fd.append('model', model)  // 模型名称
    fd.append('crop_enabled', cropEnabled ? 'true' : 'false')  // 是否图像裁剪
    fd.append('full_enabled', fullEnabled ? 'true' : 'false')  // 是否识别空间类型
    fd.append('file_count', String(fileCount))   // 本次上传的文件总数
    if (batchId) fd.append('batch_id', batchId)  // 本批次 ID

    // drawing_id 可选：有当前 CAD 图纸时传入，用于把效果图识别结果归属到当前图纸。
    // 不传或为 0 时保持旧行为，记录只会出现在"全部历史"模式。
    if (drawingId) fd.append('drawing_id', String(drawingId))
    const { data } = await api.post('/analyze', fd, { timeout: 120000 })
    return data
  },

  // === 数据融合 (接口3) ===
  async getCurrentFusionData() {
    try {
      const { data } = await api.get('/analyze/latest', { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },
  async clearCurrentFusionData() {
    try {
      const { data } = await api.post('/analyze/latest/clear', {}, { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },
  async quoteLatestFusion(manualBindings = []) {
    try {
      const fd = new FormData()
      fd.append('manual_bindings', JSON.stringify(manualBindings))
      const { data } = await api.post('/fusion/quote_latest', fd, { timeout: 30000 })
      return data
    } catch (e) { return handleError(e) }
  },
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
  // === Excel文件下载（blob二进制流） ===
  async downloadExcelBlob(quoteId) {
    try {
      const { data, headers } = await api.get(`/download_excel/${quoteId}`, {
        responseType: 'blob',
        timeout: 60000,
      })
      const disposition = headers['content-disposition'] || ''
      let filename = `报价单_${quoteId}.xlsx`
      // Try filename*=UTF-8''<url-encoded> format first (preferred by RFC 5987)
      let match = disposition.match(/filename\*=(?:UTF-8''|utf-8'')([^;\s]+)/i)
      if (match) {
        filename = decodeURIComponent(match[1])
      } else {
        // Fallback: filename="<value>" or filename=<value> — strip surrounding quotes
        match = disposition.match(/filename="([^"]*)"/i) || disposition.match(/filename=([^;\s]+)/i)
        if (match) {
          filename = match[1].replace(/^["']|["']$/g, '')
        }
      }
      // 触发浏览器下载
      const url = window.URL.createObjectURL(new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      return { success: true, message: '下载成功', filename }
    } catch (e) {
      return { success: false, message: e.response?.data?.detail || e.message || '下载失败' }
    }
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

  // === 获取图像识别结果列表 ===
  async getImageResults({ scope = 'current', drawingId = null, pageSize = 200 } = {}) {
    try {
      // scope=current：只取当前图纸关联结果；scope=all：取历史库。
      // page_size 只影响 all 模式，避免历史库继续受后端旧的 50 条限制影响。
      const params = new URLSearchParams({ scope, page_size: String(pageSize) })
      // current 模式需要 drawing_id；没有图纸时后端返回空列表，由前端显示空态。
      if (drawingId) params.append('drawing_id', String(drawingId))
      const { data } = await api.get(`/image-results?${params.toString()}`)
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

  // === CAD 测试误差评估 ===
  async evaluateCadResult(cadResult, groundTruthJson) {
    try {
      const fd = new FormData()
      fd.append('cad_result', JSON.stringify(cadResult))
      fd.append('ground_truth_json', JSON.stringify(groundTruthJson))
      const { data } = await api.post('/cad_test', fd, { timeout: 30000 })
      return data
    } catch (e) {
      return handleError(e)
    }
  },
}

export default API
