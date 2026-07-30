/**
 * 人工标注格式能力的前端状态与查询工具。
 * 本文件接收后端返回的完整能力表，统一字段命名并保存为响应式状态，再向组件提供格式准入、
 * 文件选择范围和不可用原因等查询；后端请求由 services/api.js 负责。
 */
// 去除原本前端的静态能力表，启用后端标注文件能力表接口
import { computed, reactive } from 'vue'
// 后端能力接口是唯一配置来源；加载完成前保持空集合，避免误开放标注入口。
const annotationCapabilities = reactive({})

// 根据 enabled 动态生成文件选择器允许的扩展名。
export const annotationFileAccept = computed(() => Object.entries(annotationCapabilities)
  .filter(([, capability]) => capability.enabled)
  .map(([format]) => `.${format}`)
  .join(','))
// 保存能力表，将后端数组转换成前端方便查询的对象并字段名统一为 camelCase。
export function setAnnotationCapabilities(formats) {
  Object.keys(annotationCapabilities).forEach(format => delete annotationCapabilities[format])
  for (const item of Array.isArray(formats) ? formats : []) {
    const format = String(item?.format || '').toLowerCase().replace(/^\./, '')
    if (!format) continue
    // 在接口边界统一字段命名，组件内部只使用 camelCase。
    annotationCapabilities[format] = {
      enabled: item.enabled === true,
      label: String(item.label || format.toUpperCase()),
      backgroundType: String(item.background_type || ''),
      calibrationPolicy: String(item.calibration_policy || 'optional'),
      allowUnitOverride: item.allow_unit_override === true,
      defaultUnit: item.default_unit || null,
      unavailableReason: String(item.unavailable_reason || ''),
    }
  }
}

export function fileFormat(fileOrName) {
  const name = typeof fileOrName === 'string' ? fileOrName : fileOrName?.name
  return String(name || '').split('.').pop().toLowerCase()
}

export function annotationCapability(fileOrName) {
  return annotationCapabilities[fileFormat(fileOrName)] || null
}

export function canAnnotate(fileOrName) {
  return annotationCapability(fileOrName)?.enabled === true
}

export function annotationUnavailableReason(fileOrName) {
  const capability = annotationCapability(fileOrName)
  return capability?.unavailableReason || '该文件格式不支持人工标注'
}
