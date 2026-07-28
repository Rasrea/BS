export const MANUAL_ANNOTATION_CAPABILITIES = Object.freeze({
  dxf: Object.freeze({
    enabled: true,
    label: 'DXF',
    requiresCalibration: false,
    unavailableReason: '',
  }),
  pdf: Object.freeze({
    enabled: false,
    label: 'PDF',
    requiresCalibration: true,
    unavailableReason: 'PDF 人工标注尚未开放，后续将支持页码选择、页面底图和比例校准',
  }),
})

export const annotationFileAccept = Object.entries(MANUAL_ANNOTATION_CAPABILITIES)
  .filter(([, capability]) => capability.enabled)
  .map(([format]) => `.${format}`)
  .join(',')

export function fileFormat(fileOrName) {
  const name = typeof fileOrName === 'string' ? fileOrName : fileOrName?.name
  return String(name || '').split('.').pop().toLowerCase()
}

export function annotationCapability(fileOrName) {
  return MANUAL_ANNOTATION_CAPABILITIES[fileFormat(fileOrName)] || null
}

export function canAnnotate(fileOrName) {
  return annotationCapability(fileOrName)?.enabled === true
}

export function annotationUnavailableReason(fileOrName) {
  const capability = annotationCapability(fileOrName)
  return capability?.unavailableReason || '该文件格式不支持人工标注'
}
