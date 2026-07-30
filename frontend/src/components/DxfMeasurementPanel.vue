<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import API from '../services/api.js'
import {
  annotationCapability, // 引入能力表查询函数
  annotationFileAccept,
  annotationUnavailableReason,
  canAnnotate,
  fileFormat,
} from '../utils/annotationCapabilities.js'

const props = defineProps({
  active: { type: Boolean, default: false },
  initialFile: { type: Object, default: null },
  initialSpaces: { type: Array, default: () => [] },
  reviewReason: { type: String, default: '' },
  embedded: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'saved'])

const svgRef = ref(null)
const file = ref(null)
const drawing = ref(null)
const loading = ref(false)
const loadingView = ref(false)
const calculating = ref(false)
const error = ref('')
const mode = ref('select')
const roomName = ref('房间1')
const rooms = ref([])
const currentPoints = ref([])
const pointerPoint = ref(null)
const snapTarget = ref(null)
const snapKind = ref('')
const constraintGuide = ref(null)
const measurement = ref(null)
const unitOverride = ref('')
const calibrationPoints = ref([])
const calibrationLength = ref('')
const calibrationLengthUnit = ref('m')
const viewBox = ref({ x: 0, y: 0, w: 1000, h: 700 })
const panState = ref(null)
const vertexDrag = ref(null)
const didPan = ref(false)
const selectedRoomId = ref(null)
const activeEdge = ref(null)
const selectedViewId = ref('all')
const displayMode = ref(localStorage.getItem('dxf-color-mode') || 'semantic')
const showCadTexts = ref(localStorage.getItem('dxf-show-texts') !== 'false')
const orthogonalSnap = ref(localStorage.getItem('dxf-orthogonal-snap') !== 'false')
const hiddenLayers = ref({})
const hiddenCadLayers = ref({})
const disabledSnapLayers = ref({})
const layerFilter = ref('')
const autoReviewMessage = ref('')
const lastInitialFile = ref(null)
const lastInitialSpaces = ref(null)

const colors = ['#19b5a5', '#f59e0b', '#3b82f6', '#ef4444', '#8b5cf6', '#22c55e']
const MAX_SNAP_SEGMENTS = 250_000
const cadPalette = ['#a7c7e7', '#f4b183', '#93c47d', '#c5a3d8', '#e6cf72', '#7fc8c4', '#d58a94', '#9fa8da', '#b7b7a4', '#84a59d']
const semanticStyles = {
  wall: { label: '墙体', color: '#e2e8ee', width: 1.45 },
  door: { label: '门', color: '#f2a65a', width: 1.2 },
  window: { label: '窗', color: '#42c6d6', width: 1.2 },
  structure: { label: '结构', color: '#dc6b73', width: 1.35 },
  axis: { label: '轴线', color: '#d8c56a', width: 0.8, dash: '7 4' },
  dimension: { label: '标注', color: '#78a9dc', width: 0.75 },
  furniture: { label: '家具', color: '#bd91d4', width: 0.85 },
  plumbing: { label: '给排水', color: '#55b7a5', width: 0.9 },
  electrical: { label: '电气', color: '#e6c35c', width: 0.9 },
  ceiling: { label: '吊顶', color: '#d994b4', width: 0.85 },
}
let savedColors = {}
try {
  savedColors = JSON.parse(localStorage.getItem('dxf-custom-colors') || '{}')
} catch {
  savedColors = {}
}
const customColors = ref({
  ...Object.fromEntries(Object.entries(semanticStyles).map(([key, value]) => [key, value.color])),
  default: '#aeb8c2',
  ...savedColors,
})

const yAxisSum = computed(() => {
  const bounds = drawing.value?.bounds
  return bounds ? bounds.min_y + bounds.max_y : 0
})

const renderPaths = computed(() => {
  const groups = new Map()
  for (const entity of drawing.value?.entities || []) {
    const style = entityDisplayStyle(entity.layer, entity.source_type, entity.color)
    if (style.hidden) continue
    const dash = style.dash || ''
    const key = `${style.color}|${style.width}|${dash}`
    if (!groups.has(key)) {
      groups.set(key, { id: key, segments: [], color: style.color, width: style.width, dash })
    }
    const [first, ...remaining] = entity.points
    if (!first) continue
    const commands = [`M${first[0]},${yAxisSum.value - first[1]}`]
    for (const point of remaining) commands.push(`L${point[0]},${yAxisSum.value - point[1]}`)
    groups.get(key).segments.push(commands.join(' '))
  }
  return [...groups.values()].map(({ segments, ...group }) => ({ ...group, path: segments.join(' ') }))
})

const renderTexts = computed(() => showCadTexts.value ? (drawing.value?.texts || []).map((item, index) => {
  const style = entityDisplayStyle(item.layer, 'TEXT', item.color)
  return {
    id: index,
    text: item.text,
    x: item.position[0],
    y: yAxisSum.value - item.position[1],
    size: item.height > 0 ? item.height : drawingTextSize.value,
    color: style.color,
    hidden: style.hidden,
  }
}).filter(item => !item.hidden).slice(0, 1500) : [])

const cadLayers = computed(() => {
  const layers = new Map()
  const addLayer = (layer, sourceType, color, kind) => {
    const name = normalizeLayerName(layer)
    if (!layers.has(name)) {
      const style = entityDisplayStyle(name, sourceType, color)
      layers.set(name, { name, entities: 0, texts: 0, color: style.color })
    }
    layers.get(name)[kind] += 1
  }
  for (const entity of drawing.value?.entities || []) {
    addLayer(entity.layer, entity.source_type, entity.color, 'entities')
  }
  for (const text of drawing.value?.texts || []) {
    addLayer(text.layer, 'TEXT', text.color, 'texts')
  }
  return [...layers.values()]
    .map(layer => ({
      ...layer,
      visible: isCadLayerVisible(layer.name),
      snappable: isCadLayerSnappable(layer.name),
    }))
    .sort((left, right) => (right.entities + right.texts) - (left.entities + left.texts)
      || left.name.localeCompare(right.name, 'zh-CN'))
})

const filteredCadLayers = computed(() => {
  const keyword = layerFilter.value.trim().toLowerCase()
  return keyword
    ? cadLayers.value.filter(layer => layer.name.toLowerCase().includes(keyword))
    : cadLayers.value
})

const visibleCadLayerCount = computed(() => cadLayers.value.filter(layer => layer.visible).length)
const snapCadLayerCount = computed(() => cadLayers.value.filter(layer => layer.snappable).length)

const layerLegend = computed(() => {
  const seen = new Set()
  const legend = []
  for (const entity of drawing.value?.entities || []) {
    const style = cadLayerStyle(entity.layer, entity.source_type)
    const key = style.key
    if (seen.has(key)) continue
    seen.add(key)
    const displayStyle = entityDisplayStyle(entity.layer, entity.source_type, entity.color)
    legend.push({ key, label: style.label, color: displayStyle.color, hidden: displayStyle.hidden })
    if (legend.length >= 8) break
  }
  return legend
})

const snapPoints = computed(() => {
  const points = []
  for (const entity of drawing.value?.entities || []) {
    if (!isCadLayerSnappable(entity.layer)) continue
    for (const point of entity.points) points.push(point)
  }
  for (const room of rooms.value) {
    for (const point of room.vertices) points.push(point)
  }
  return points
})

const snapSegments = computed(() => {
  const segments = []
  const cadEntities = (drawing.value?.entities || []).filter(entity => isCadLayerSnappable(entity.layer))
  const totalCadSegments = cadEntities.reduce((total, entity) => total + Math.max(entity.points.length - 1, 0), 0)
  const sampleStep = Math.max(Math.ceil(totalCadSegments / MAX_SNAP_SEGMENTS), 1)
  let segmentNumber = 0
  for (const [entityIndex, entity] of cadEntities.entries()) {
    for (let index = 0; index < entity.points.length - 1; index += 1) {
      const start = entity.points[index]
      const end = entity.points[index + 1]
      const include = segmentNumber % sampleStep === 0
      segmentNumber += 1
      if (!include) continue
      if (start[0] === end[0] && start[1] === end[1]) continue
      segments.push({ id: `cad-${entityIndex}-${index}`, start, end })
    }
  }
  for (const room of rooms.value) {
    for (let index = 0; index < room.vertices.length; index += 1) {
      segments.push({
        id: `room-${room.client_id}-${index}`,
        start: room.vertices[index],
        end: room.vertices[(index + 1) % room.vertices.length],
      })
    }
  }
  return segments
})

const snapIndex = computed(() => {
  const bounds = drawing.value?.bounds
  if (!bounds) return null
  const span = Math.max(bounds.max_x - bounds.min_x, bounds.max_y - bounds.min_y, 1)
  const cellSize = span / 400
  const cells = new Map()
  for (const point of snapPoints.value) {
    const column = Math.floor((point[0] - bounds.min_x) / cellSize)
    const row = Math.floor((point[1] - bounds.min_y) / cellSize)
    const key = `${column}:${row}`
    if (!cells.has(key)) cells.set(key, [])
    cells.get(key).push(point)
  }
  return { bounds, cellSize, cells }
})

const segmentIndex = computed(() => {
  const pointIndex = snapIndex.value
  if (!pointIndex) return null
  const cells = new Map()
  const longSegments = []
  for (const segment of snapSegments.value) {
    const minColumn = Math.floor((Math.min(segment.start[0], segment.end[0]) - pointIndex.bounds.min_x) / pointIndex.cellSize)
    const maxColumn = Math.floor((Math.max(segment.start[0], segment.end[0]) - pointIndex.bounds.min_x) / pointIndex.cellSize)
    const minRow = Math.floor((Math.min(segment.start[1], segment.end[1]) - pointIndex.bounds.min_y) / pointIndex.cellSize)
    const maxRow = Math.floor((Math.max(segment.start[1], segment.end[1]) - pointIndex.bounds.min_y) / pointIndex.cellSize)
    const cellCount = (maxColumn - minColumn + 1) * (maxRow - minRow + 1)
    if (cellCount > 16) {
      longSegments.push(segment)
      continue
    }
    for (let column = minColumn; column <= maxColumn; column += 1) {
      for (let row = minRow; row <= maxRow; row += 1) {
        const key = `${column}:${row}`
        if (!cells.has(key)) cells.set(key, [])
        cells.get(key).push(segment)
      }
    }
  }
  return { ...pointIndex, cells, longSegments }
})

const markerRadius = computed(() => Math.max(viewBox.value.w / 220, 0.01))
const drawingTextSize = computed(() => {
  const bounds = drawing.value?.bounds
  if (!bounds) return 1
  const span = Math.max(bounds.max_x - bounds.min_x, bounds.max_y - bounds.min_y, 1)
  return Math.max(span / 280, 1)
})

const previewPoints = computed(() => {
  if (!currentPoints.value.length) return []
  if (mode.value === 'rectangle' && pointerPoint.value) {
    return rectangleVertices(currentPoints.value[0], pointerPoint.value)
  }
  return pointerPoint.value
    ? [...currentPoints.value, pointerPoint.value]
    : currentPoints.value
})

const resultById = computed(() => {
  const map = new Map()
  for (const room of measurement.value?.rooms || []) map.set(room.client_id, room)
  return map
})

const calibrationModelLength = computed(() => calibrationPoints.value.length === 2
  ? Math.hypot(
    calibrationPoints.value[1][0] - calibrationPoints.value[0][0],
    calibrationPoints.value[1][1] - calibrationPoints.value[0][1],
  )
  : 0)
const calibrationRealLengthMm = computed(() => {
  const value = Number(calibrationLength.value)
  if (!Number.isFinite(value) || value <= 0) return 0
  return value * (calibrationLengthUnit.value === 'm' ? 1000 : 1)
})
const calibrationMmPerUnit = computed(() => calibrationModelLength.value > 0 && calibrationRealLengthMm.value > 0
  ? calibrationRealLengthMm.value / calibrationModelLength.value
  : 0)
const currentMmPerUnit = computed(() => calibrationMmPerUnit.value || (unitOverride.value
  ? { mm: 1, cm: 10, m: 1000, in: 25.4, ft: 304.8 }[unitOverride.value]
  : drawing.value?.mm_per_unit || 1))
const calibrationPreviewPoints = computed(() => {
  if (!calibrationPoints.value.length) return []
  return calibrationPoints.value.length === 1 && pointerPoint.value
    ? [calibrationPoints.value[0], pointerPoint.value]
    : calibrationPoints.value
})
const canvasStatus = computed(() => {
  if (mode.value === 'select') return '选择空间或边'
  if (mode.value === 'rectangle') return `矩形 ${currentPoints.value.length}/2`
  if (mode.value === 'polygon') return `角点 ${currentPoints.value.length}`
  if (mode.value === 'calibrate') return `校准端点 ${calibrationPoints.value.length}/2`
  return '平移视图'
})

const selectedRoom = computed(() => rooms.value.find(room => room.client_id === selectedRoomId.value) || null)
const sourceFormatLabel = computed(() => {
  const format = drawing.value?.source_format || fileFormat(file.value)
  return format ? format.toUpperCase() : '图纸'
})
// 从已经调后端接口拿到前端的能力表中获取当前格式能力，并提取分析决定校准入口、单位覆盖权限和保存前比例确认要求。
const activeAnnotationCapability = computed(() => (
  annotationCapability(drawing.value?.source_format || file.value)
))
const calibrationPolicy = computed(() => activeAnnotationCapability.value?.calibrationPolicy || 'optional')
const calibrationAllowed = computed(() => calibrationPolicy.value !== 'none')
const unitOverrideAllowed = computed(() => activeAnnotationCapability.value?.allowUnitOverride === true)
const scaleConfirmationRequired = computed(() => drawing.value?.calibration_required === true)
const roomNameModel = computed({
  get: () => selectedRoom.value?.name ?? roomName.value,
  set: value => {
    if (selectedRoom.value) {
      selectedRoom.value.name = value
      measurement.value = null
      return
    }
    roomName.value = value
  },
})
const allRoomEdges = computed(() => rooms.value.flatMap(room => roomEdges(room)))
const selectedRoomEdges = computed(() => selectedRoom.value ? roomEdges(selectedRoom.value) : [])
const drawingFitBounds = computed(() => renderedFitBounds())
const reviewMessages = computed(() => [...new Set([
  autoReviewMessage.value,
  ...(drawing.value?.warnings || []),
  ...(drawing.value?.view_warnings || []),
].filter(Boolean))])
const activeEdgeLabel = computed(() => {
  if (!activeEdge.value) return null
  return allRoomEdges.value.find(edge => (
    edge.roomId === activeEdge.value.roomId && edge.index === activeEdge.value.index
  )) || null
})
const annotationSize = computed(() => Math.max(viewBox.value.w / Math.max(svgRef.value?.clientWidth || 900, 1) * 12, 0.01))

function cadLayerStyle(layer = '0', sourceType = '') {
  const normalized = String(layer).trim().toLowerCase().replace(/[\s_-]+/g, '')
  let role = ''
  if (/wall|墙/.test(normalized)) role = 'wall'
  else if (/door|门/.test(normalized)) role = 'door'
  else if (/window|窗/.test(normalized)) role = 'window'
  else if (/column|pillar|beam|structure|柱|梁|结构/.test(normalized)) role = 'structure'
  else if (/axis|grid|轴/.test(normalized)) role = 'axis'
  else if (/dimension|dim|annotation|anno|标注|尺寸|文字|text/.test(normalized)) role = 'dimension'
  else if (/furniture|furn|fixture|cabinet|家具|洁具|橱柜/.test(normalized)) role = 'furniture'
  else if (/plumb|water|给排水|水管/.test(normalized)) role = 'plumbing'
  else if (/electric|elec|power|电气|插座|灯具/.test(normalized)) role = 'electrical'
  else if (/ceiling|吊顶|天花/.test(normalized)) role = 'ceiling'
  else if (sourceType === 'ARC' && normalized === '0') role = 'door'

  if (role) return { role, key: role, ...semanticStyles[role] }
  if (!normalized || normalized === '0') return { role: 'default', key: 'default', label: '基础线', color: '#aeb8c2', width: 0.9 }

  let hash = 0
  for (const character of normalized) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0
  return {
    role: '',
    key: `layer:${layer}`,
    label: layer.length > 12 ? `${layer.slice(0, 12)}…` : layer,
    color: cadPalette[Math.abs(hash) % cadPalette.length],
    width: 0.85,
  }
}

function entityDisplayStyle(layer, sourceType, originalColor) {
  const base = cadLayerStyle(layer, sourceType)
  let color = base.color
  if (displayMode.value === 'original') color = originalColor || base.color
  else if (displayMode.value === 'mono') color = '#c7d0d9'
  else color = customColors.value[base.key] || base.color
  return {
    ...base,
    color,
    hidden: !!hiddenLayers.value[base.key] || !isCadLayerVisible(layer),
  }
}

function normalizeLayerName(layer) {
  const name = String(layer ?? '').trim()
  return name || '0'
}

function isCadLayerVisible(layer) {
  return !hiddenCadLayers.value[normalizeLayerName(layer)]
}

function isCadLayerSnappable(layer) {
  return !disabledSnapLayers.value[normalizeLayerName(layer)]
}

function setCadLayerVisibility(layer, visible) {
  const name = normalizeLayerName(layer)
  hiddenCadLayers.value = { ...hiddenCadLayers.value, [name]: !visible }
}

function setCadLayerSnapping(layer, enabled) {
  const name = normalizeLayerName(layer)
  disabledSnapLayers.value = { ...disabledSnapLayers.value, [name]: !enabled }
  clearSnapFeedback()
}

function setAllCadLayersVisible(visible) {
  hiddenCadLayers.value = Object.fromEntries(cadLayers.value.map(layer => [layer.name, !visible]))
}

function setAllCadLayersSnappable(enabled) {
  disabledSnapLayers.value = Object.fromEntries(cadLayers.value.map(layer => [layer.name, !enabled]))
  clearSnapFeedback()
}

function toggleLayer(key) {
  hiddenLayers.value = { ...hiddenLayers.value, [key]: !hiddenLayers.value[key] }
}

function changeLayerColor(key, event) {
  customColors.value = { ...customColors.value, [key]: event.target.value }
}

watch(displayMode, value => localStorage.setItem('dxf-color-mode', value))
watch(showCadTexts, value => localStorage.setItem('dxf-show-texts', String(value)))
watch(orthogonalSnap, value => localStorage.setItem('dxf-orthogonal-snap', String(value)))
watch(customColors, value => localStorage.setItem('dxf-custom-colors', JSON.stringify(value)), { deep: true })
watch([unitOverride, calibrationLength, calibrationLengthUnit], () => { measurement.value = null })
watch(
  () => [props.active, props.initialFile, props.initialSpaces],
  async ([active, initialFile, initialSpaces]) => {
    if (!active || !canAnnotate(initialFile)) return
    if (lastInitialFile.value === initialFile && lastInitialSpaces.value === initialSpaces) return
    lastInitialFile.value = initialFile
    lastInitialSpaces.value = initialSpaces
    await loadMeasurementFile(initialFile, initialSpaces, props.reviewReason)
  },
  { immediate: true },
)

async function loadMeasurementFile(selected, initialSpaces = [], reviewReason = '') {
  file.value = selected
  loading.value = true
  error.value = ''
  drawing.value = null
  rooms.value = []
  hiddenCadLayers.value = {}
  disabledSnapLayers.value = {}
  layerFilter.value = ''
  selectedRoomId.value = null
  activeEdge.value = null
  currentPoints.value = []
  clearSnapFeedback()
  measurement.value = null
  calibrationPoints.value = []
  calibrationLength.value = ''
  autoReviewMessage.value = ''
  const response = await API.prepareMeasurement(selected)
  loading.value = false
  if (!response.success) {
    error.value = response.message || '测量底图准备失败'
    return
  }
  drawing.value = response.data
  rooms.value = initialSpaces
    .filter(space => Array.isArray(space.vertices) && space.vertices.length >= 3)
    .map((space, index) => ({
      client_id: crypto.randomUUID ? crypto.randomUUID() : `auto-${Date.now()}-${index}`,
      name: space.name || `房间${index + 1}`,
      shape_type: 'polygon',
      vertices: space.vertices.map(point => [Number(point[0]), Number(point[1])]),
      boundary_source: space.boundary_source || 'automatic',
      confidence: Number(space.confidence ?? 0),
    }))
    .filter(room => room.vertices.every(point => point.every(Number.isFinite)) && localArea(room.vertices) > 0)
  roomName.value = `房间${rooms.value.length + 1}`
  autoReviewMessage.value = rooms.value.length
    ? `已载入 ${rooms.value.length} 个已有标注区域，可直接选择、调整或删除。${reviewReason || ''}`
    : reviewReason
  selectedViewId.value = response.data.active_view_id || 'all'
  // 默认使用能力表明确配置的默认单位，不再把未知单位自动当作毫米。
  const capability = annotationCapability(response.data.source_format || selected)
  unitOverride.value = !response.data.unit_confirmed && capability?.allowUnitOverride
    ? capability.defaultUnit || ''
    : ''
  if (capability?.calibrationPolicy === 'none' && mode.value === 'calibrate') mode.value = 'select'
  await nextTick()
  fitViewAfterLayout()
}

async function selectDrawingView() {
  if (!drawing.value || selectedViewId.value === drawing.value.active_view_id) return
  loadingView.value = true
  error.value = ''
  cancelCurrent()
  const response = await API.getMeasurementView(drawing.value.drawing_id, selectedViewId.value)
  loadingView.value = false
  if (!response.success) {
    error.value = response.message || '图纸区域加载失败'
    return
  }
  drawing.value = {
    ...drawing.value,
    ...response.data,
    filename: drawing.value.filename,
    drawing_id: drawing.value.drawing_id,
  }
  await nextTick()
  fitViewAfterLayout()
}

function fitViewAfterLayout() {
  requestAnimationFrame(() => requestAnimationFrame(fitView))
}

function fitView() {
  const bounds = drawingFitBounds.value
  if (!bounds) return
  let width = Math.max(bounds.max_x - bounds.min_x, 1)
  let height = Math.max(bounds.max_y - bounds.min_y, 1)
  const canvasAspect = Math.max(svgRef.value?.clientWidth || 1, 1) / Math.max(svgRef.value?.clientHeight || 1, 1)
  const drawingAspect = width / height
  if (drawingAspect > canvasAspect) height = width / canvasAspect
  else width = height * canvasAspect
  const centerX = (bounds.min_x + bounds.max_x) / 2
  const centerY = (bounds.min_y + bounds.max_y) / 2
  viewBox.value = {
    x: centerX - width * 0.54,
    y: centerY - height * 0.54,
    w: width * 1.08,
    h: height * 1.08,
  }
}

function renderedFitBounds() {
  const entities = (drawing.value?.entities || []).filter(entity => (
    !entityDisplayStyle(entity.layer, entity.source_type, entity.color).hidden
  ))
  if (!entities.length) return drawing.value?.bounds || null
  const records = entities.map(entity => {
    const bounds = pointsBounds(entity.points)
    if (!bounds) return null
    const { minX, maxX, minY, maxY } = bounds
    return { minX, maxX, minY, maxY, centerX: (minX + maxX) / 2, centerY: (minY + maxY) / 2 }
  }).filter(Boolean)
  if (!records.length) return drawing.value?.bounds || null

  let included = records
  if (records.length >= 200) {
    const centerXs = records.map(item => item.centerX).sort((left, right) => left - right)
    const centerYs = records.map(item => item.centerY).sort((left, right) => left - right)
    const lowX = percentile(centerXs, 0.005)
    const highX = percentile(centerXs, 0.995)
    const lowY = percentile(centerYs, 0.005)
    const highY = percentile(centerYs, 0.995)
    const fullBounds = mergeRecordBounds(records)
    const fullWidth = fullBounds.maxX - fullBounds.minX
    const fullHeight = fullBounds.maxY - fullBounds.minY
    const robustWidth = Math.max(highX - lowX, 1)
    const robustHeight = Math.max(highY - lowY, 1)
    if (fullWidth > robustWidth * 6 || fullHeight > robustHeight * 6) {
      const filtered = records.filter(item => (
        item.centerX >= lowX && item.centerX <= highX && item.centerY >= lowY && item.centerY <= highY
      ))
      if (filtered.length >= records.length * 0.9) included = filtered
    }
  }

  const fitBounds = mergeRecordBounds(included)
  return {
    min_x: fitBounds.minX,
    max_x: fitBounds.maxX,
    min_y: yAxisSum.value - fitBounds.maxY,
    max_y: yAxisSum.value - fitBounds.minY,
  }
}

function pointsBounds(points) {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const point of points) {
    if (!Number.isFinite(point[0]) || !Number.isFinite(point[1])) continue
    minX = Math.min(minX, point[0])
    minY = Math.min(minY, point[1])
    maxX = Math.max(maxX, point[0])
    maxY = Math.max(maxY, point[1])
  }
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null
}

function mergeRecordBounds(records) {
  return records.reduce((bounds, item) => ({
    minX: Math.min(bounds.minX, item.minX),
    minY: Math.min(bounds.minY, item.minY),
    maxX: Math.max(bounds.maxX, item.maxX),
    maxY: Math.max(bounds.maxY, item.maxY),
  }), { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity })
}

function percentile(sortedValues, ratio) {
  return sortedValues[Math.min(Math.floor((sortedValues.length - 1) * ratio), sortedValues.length - 1)]
}

function eventToSvg(event) {
  const svg = svgRef.value
  if (!svg) return null
  const point = svg.createSVGPoint()
  point.x = event.clientX
  point.y = event.clientY
  return point.matrixTransform(svg.getScreenCTM().inverse())
}

function eventToCad(event, allowSnap = true, showSnap = false) {
  const point = eventToSvg(event)
  if (!point) return null
  const cadPoint = [point.x, yAxisSum.value - point.y]
  if (!allowSnap) return cadPoint
  const snapped = snapPoint(cadPoint)
  const constrained = constrainAngle(snapped.point, event.shiftKey)
  if (showSnap) {
    snapTarget.value = snapped.kind || constrained.kind ? [...constrained.point] : null
    snapKind.value = [snapped.kind, constrained.kind].filter(Boolean).join(' + ')
    constraintGuide.value = constrained.kind ? {
      start: [...currentPoints.value[currentPoints.value.length - 1]],
      end: [...constrained.point],
    } : null
  }
  return constrained.point
}

function snapPoint(point) {
  const svg = svgRef.value
  const index = snapIndex.value
  if (!index) return { point, kind: '' }
  const threshold = viewBox.value.w / Math.max(svg?.clientWidth || 1, 1) * 12
  const thresholdSquared = threshold * threshold
  let nearest = null
  let best = thresholdSquared
  const centerColumn = Math.floor((point[0] - index.bounds.min_x) / index.cellSize)
  const centerRow = Math.floor((point[1] - index.bounds.min_y) / index.cellSize)
  const cellRadius = Math.max(1, Math.ceil(threshold / index.cellSize))
  for (let columnOffset = -cellRadius; columnOffset <= cellRadius; columnOffset += 1) {
    for (let rowOffset = -cellRadius; rowOffset <= cellRadius; rowOffset += 1) {
      const candidates = index.cells.get(`${centerColumn + columnOffset}:${centerRow + rowOffset}`) || []
      for (const candidate of candidates) {
        const dx = candidate[0] - point[0]
        const dy = candidate[1] - point[1]
        const distance = dx * dx + dy * dy
        if (distance < best) {
          best = distance
          nearest = [...candidate]
        }
      }
    }
  }
  if (nearest) return { point: nearest, kind: '端点' }

  const candidates = nearbySegments(point, threshold)
  const intersection = nearestIntersection(point, candidates.slice(0, 80), thresholdSquared)
  if (intersection) return { point: intersection, kind: '交点' }

  best = thresholdSquared * 0.75 * 0.75
  for (const segment of candidates.slice(0, 500)) {
    const projection = projectToSegment(point, segment.start, segment.end)
    const distance = squaredDistance(point, projection)
    if (distance < best) {
      best = distance
      nearest = projection
    }
  }
  return nearest ? { point: nearest, kind: '线段' } : { point: [...point], kind: '' }
}

function nearbySegments(point, threshold) {
  const index = segmentIndex.value
  if (!index) return []
  const centerColumn = Math.floor((point[0] - index.bounds.min_x) / index.cellSize)
  const centerRow = Math.floor((point[1] - index.bounds.min_y) / index.cellSize)
  const cellRadius = Math.max(1, Math.ceil(threshold / index.cellSize))
  const candidates = new Map()
  for (let columnOffset = -cellRadius; columnOffset <= cellRadius; columnOffset += 1) {
    for (let rowOffset = -cellRadius; rowOffset <= cellRadius; rowOffset += 1) {
      for (const segment of index.cells.get(`${centerColumn + columnOffset}:${centerRow + rowOffset}`) || []) {
        candidates.set(segment.id, segment)
      }
    }
  }
  for (const segment of index.longSegments) {
    if (pointNearSegmentBounds(point, segment, threshold)) candidates.set(segment.id, segment)
  }
  return [...candidates.values()]
}

function pointNearSegmentBounds(point, segment, threshold) {
  return point[0] >= Math.min(segment.start[0], segment.end[0]) - threshold
    && point[0] <= Math.max(segment.start[0], segment.end[0]) + threshold
    && point[1] >= Math.min(segment.start[1], segment.end[1]) - threshold
    && point[1] <= Math.max(segment.start[1], segment.end[1]) + threshold
}

function nearestIntersection(point, segments, thresholdSquared) {
  let nearest = null
  let best = thresholdSquared
  const extensionTolerance = Math.sqrt(thresholdSquared)
  for (let leftIndex = 0; leftIndex < segments.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < segments.length; rightIndex += 1) {
      const intersection = segmentIntersection(segments[leftIndex], segments[rightIndex], extensionTolerance)
      if (!intersection) continue
      const distance = squaredDistance(point, intersection)
      if (distance < best) {
        best = distance
        nearest = intersection
      }
    }
  }
  return nearest
}

function segmentIntersection(left, right, extensionTolerance = 0) {
  const [ax, ay] = left.start
  const [bx, by] = left.end
  const [cx, cy] = right.start
  const [dx, dy] = right.end
  const denominator = (ax - bx) * (cy - dy) - (ay - by) * (cx - dx)
  if (Math.abs(denominator) < 1e-10) return null
  const leftCross = ax * by - ay * bx
  const rightCross = cx * dy - cy * dx
  const x = (leftCross * (cx - dx) - (ax - bx) * rightCross) / denominator
  const y = (leftCross * (cy - dy) - (ay - by) * rightCross) / denominator
  const epsilon = Math.max(extensionTolerance, 1e-8)
  if (x < Math.min(ax, bx) - epsilon || x > Math.max(ax, bx) + epsilon
    || y < Math.min(ay, by) - epsilon || y > Math.max(ay, by) + epsilon
    || x < Math.min(cx, dx) - epsilon || x > Math.max(cx, dx) + epsilon
    || y < Math.min(cy, dy) - epsilon || y > Math.max(cy, dy) + epsilon) return null
  return [x, y]
}

function projectToSegment(point, start, end) {
  const dx = end[0] - start[0]
  const dy = end[1] - start[1]
  const lengthSquared = dx * dx + dy * dy
  if (!lengthSquared) return [...start]
  const ratio = Math.min(Math.max(((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / lengthSquared, 0), 1)
  return [start[0] + dx * ratio, start[1] + dy * ratio]
}

function squaredDistance(left, right) {
  const dx = left[0] - right[0]
  const dy = left[1] - right[1]
  return dx * dx + dy * dy
}

function constrainAngle(point, forceOrthogonal = false) {
  if (mode.value !== 'polygon' || !currentPoints.value.length || (!orthogonalSnap.value && !forceOrthogonal)) {
    return { point: [...point], kind: '' }
  }
  const origin = currentPoints.value[currentPoints.value.length - 1]
  const dx = point[0] - origin[0]
  const dy = point[1] - origin[1]
  if (!dx && !dy) return { point: [...point], kind: '' }
  const angle = Math.atan2(Math.abs(dy), Math.abs(dx))
  const horizontalDelta = angle
  const verticalDelta = Math.abs(Math.PI / 2 - angle)
  const tolerance = 3 * Math.PI / 180
  if (!forceOrthogonal && Math.min(horizontalDelta, verticalDelta) > tolerance) {
    return { point: [...point], kind: '' }
  }
  if (horizontalDelta <= verticalDelta) return { point: [point[0], origin[1]], kind: '水平' }
  return { point: [origin[0], point[1]], kind: '垂直' }
}

function onCanvasClick(event) {
  if (mode.value === 'select' || mode.value === 'pan' || didPan.value || !drawing.value) return
  const point = eventToCad(event)
  if (!point) return
  measurement.value = null

  if (mode.value === 'calibrate') {
    if (calibrationPoints.value.length >= 2) calibrationPoints.value = [point]
    else calibrationPoints.value.push(point)
    pointerPoint.value = null
    return
  }

  if (mode.value === 'rectangle') {
    if (!currentPoints.value.length) {
      currentPoints.value = [point]
    } else {
      addRoom(rectangleVertices(currentPoints.value[0], point), 'rectangle')
    }
    return
  }
  currentPoints.value.push(point)
}

function onPointerMove(event) {
  if (vertexDrag.value) {
    const point = eventToCad(event, true, true)
    if (!point) return
    rooms.value = rooms.value.map(room => {
      if (room.client_id !== vertexDrag.value.roomId) return room
      const vertices = room.vertices.map(vertex => [...vertex])
      vertices[vertexDrag.value.vertexIndex] = point
      return { ...room, vertices }
    })
    measurement.value = null
    return
  }
  if (panState.value) {
    const clientDx = event.clientX - panState.value.clientX
    const clientDy = event.clientY - panState.value.clientY
    if (!panState.value.active && Math.hypot(clientDx, clientDy) >= 4) {
      panState.value.active = true
      didPan.value = true
      clearSnapFeedback()
    }
    if (panState.value.active) {
      const dx = clientDx * panState.value.viewBox.w / Math.max(svgRef.value.clientWidth, 1)
      const dy = clientDy * panState.value.viewBox.h / Math.max(svgRef.value.clientHeight, 1)
      viewBox.value = {
        ...viewBox.value,
        x: panState.value.viewBox.x - dx,
        y: panState.value.viewBox.y - dy,
      }
      return
    }
  }
  const point = eventToCad(event, true, true)
  if (currentPoints.value.length || (mode.value === 'calibrate' && calibrationPoints.value.length === 1)) {
    pointerPoint.value = point
  }
}

function startPan(event) {
  if (![0, 1, 2].includes(event.button)) return
  if (event.button === 2 && mode.value === 'polygon' && currentPoints.value.length) return
  const immediate = mode.value === 'pan' || event.button !== 0
  if (immediate) event.preventDefault()
  didPan.value = false
  panState.value = {
    clientX: event.clientX,
    clientY: event.clientY,
    viewBox: { ...viewBox.value },
    active: immediate,
  }
  svgRef.value?.setPointerCapture?.(event.pointerId)
}

function startVertexDrag(event, roomId, vertexIndex) {
  if (mode.value !== 'select' || event.button !== 0) return
  selectedRoomId.value = roomId
  activeEdge.value = null
  vertexDrag.value = { roomId, vertexIndex }
  measurement.value = null
  clearSnapFeedback()
  svgRef.value?.setPointerCapture?.(event.pointerId)
}

function onContextMenu(event) {
  event.preventDefault()
  if (mode.value === 'polygon' && currentPoints.value.length) undoPoint()
}

function stopPan(event) {
  if (vertexDrag.value) {
    vertexDrag.value = null
    svgRef.value?.releasePointerCapture?.(event.pointerId)
    return
  }
  if (!panState.value) return
  panState.value = null
  svgRef.value?.releasePointerCapture?.(event.pointerId)
  setTimeout(() => { didPan.value = false }, 0)
}

function zoom(event) {
  if (!drawing.value) return
  event.preventDefault()
  const cursor = eventToSvg(event)
  if (!cursor) return
  zoomAt(cursor.x, cursor.y, event.deltaY > 0 ? 1.15 : 0.87)
}

function zoomBy(factor) {
  zoomAt(
    viewBox.value.x + viewBox.value.w / 2,
    viewBox.value.y + viewBox.value.h / 2,
    factor,
  )
}

function zoomAt(centerX, centerY, factor) {
  const bounds = drawing.value?.bounds
  if (!bounds) return
  const baseWidth = Math.max(bounds.max_x - bounds.min_x, 1)
  const requestedWidth = viewBox.value.w * factor
  const nextWidth = Math.min(Math.max(requestedWidth, baseWidth * 0.002), baseWidth * 5)
  const appliedFactor = nextWidth / viewBox.value.w
  const nextHeight = viewBox.value.h * appliedFactor
  const ratioX = Math.min(Math.max((centerX - viewBox.value.x) / viewBox.value.w, 0), 1)
  const ratioY = Math.min(Math.max((centerY - viewBox.value.y) / viewBox.value.h, 0), 1)
  viewBox.value = {
    x: centerX - ratioX * nextWidth,
    y: centerY - ratioY * nextHeight,
    w: nextWidth,
    h: nextHeight,
  }
}

function rectangleVertices(start, end) {
  return [
    [start[0], start[1]],
    [end[0], start[1]],
    [end[0], end[1]],
    [start[0], end[1]],
  ]
}

function finishPolygon() {
  if (currentPoints.value.length < 3) return
  addRoom([...currentPoints.value], 'polygon')
}

function addRoom(vertices, shapeType) {
  if (localArea(vertices) <= 0) {
    error.value = '房间边界面积必须大于零'
    return
  }
  const clientId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${rooms.value.length}`
  rooms.value.push({
    client_id: clientId,
    name: roomName.value.trim() || `房间${rooms.value.length + 1}`,
    shape_type: shapeType,
    vertices,
  })
  selectedRoomId.value = null
  activeEdge.value = null
  currentPoints.value = []
  pointerPoint.value = null
  clearSnapFeedback()
  roomName.value = `房间${rooms.value.length + 1}`
  error.value = ''
}

function undoPoint() {
  if (mode.value === 'calibrate') {
    calibrationPoints.value.pop()
    measurement.value = null
    pointerPoint.value = null
    clearSnapFeedback()
    return
  }
  currentPoints.value.pop()
  pointerPoint.value = null
  clearSnapFeedback()
}

function cancelCurrent() {
  currentPoints.value = []
  pointerPoint.value = null
  clearSnapFeedback()
}

function clearCalibration() {
  calibrationPoints.value = []
  calibrationLength.value = ''
  pointerPoint.value = null
  measurement.value = null
  clearSnapFeedback()
}

function clearSnapFeedback() {
  snapTarget.value = null
  snapKind.value = ''
  constraintGuide.value = null
}

function removeRoom(clientId) {
  rooms.value = rooms.value.filter(room => room.client_id !== clientId)
  if (selectedRoomId.value === clientId) selectedRoomId.value = null
  if (activeEdge.value?.roomId === clientId) activeEdge.value = null
  measurement.value = null
}

function localArea(vertices) {
  let area = 0
  for (let index = 0; index < vertices.length; index += 1) {
    const current = vertices[index]
    const next = vertices[(index + 1) % vertices.length]
    area += current[0] * next[1] - next[0] * current[1]
  }
  const scale = currentMmPerUnit.value
  return scale ? Math.abs(area) / 2 * scale * scale / 1_000_000 : 0
}

function roomSvgPoints(vertices) {
  return vertices.map(point => `${point[0]},${yAxisSum.value - point[1]}`).join(' ')
}

function formatLength(lengthMm) {
  return lengthMm >= 1000 ? `${(lengthMm / 1000).toFixed(2)} m` : `${Math.round(lengthMm)} mm`
}

function roomEdges(room) {
  return room.vertices.map((point, index) => {
    const next = room.vertices[(index + 1) % room.vertices.length]
    const x1 = point[0]
    const y1 = yAxisSum.value - point[1]
    const x2 = next[0]
    const y2 = yAxisSum.value - next[1]
    const dx = x2 - x1
    const dy = y2 - y1
    const length = Math.max(Math.hypot(dx, dy), 0.0001)
    const offset = annotationSize.value * 1.15
    return {
      roomId: room.client_id,
      index,
      number: index + 1,
      x1,
      y1,
      x2,
      y2,
      labelX: (x1 + x2) / 2 - dy / length * offset,
      labelY: (y1 + y2) / 2 + dx / length * offset,
      lengthLabel: formatLength(length * currentMmPerUnit.value),
    }
  })
}

function selectRoom(clientId) {
  selectedRoomId.value = selectedRoomId.value === clientId ? null : clientId
  activeEdge.value = null
}

function normalizeRoomName() {
  if (selectedRoom.value) {
    const roomIndex = rooms.value.findIndex(room => room.client_id === selectedRoom.value.client_id)
    selectedRoom.value.name = selectedRoom.value.name.trim() || `房间${roomIndex + 1}`
    return
  }
  roomName.value = roomName.value.trim() || `房间${rooms.value.length + 1}`
}

function selectEdge(edge) {
  selectedRoomId.value = edge.roomId
  activeEdge.value = { roomId: edge.roomId, index: edge.index }
}

async function calculate() {
  if (!drawing.value || !rooms.value.length) return
  error.value = ''
  if ((calibrationPoints.value.length > 0 || calibrationRealLengthMm.value > 0) && !calibrationMmPerUnit.value) {
    error.value = '请在图上选择校准线段的两个端点，并填写大于 0 的真实长度'
    return
  }
  // 保证安全，防止用户切换文件后，仍然继承上一个文件的校准能力
  if (calibrationPolicy.value === 'required' && !calibrationMmPerUnit.value) {
    error.value = `${sourceFormatLabel.value} 必须完成已知长度校准后才能保存`
    return
  }
  const unitConfirmsScale = unitOverrideAllowed.value && !!unitOverride.value
  if (scaleConfirmationRequired.value && !calibrationMmPerUnit.value && !unitConfirmsScale) {
    error.value = unitOverrideAllowed.value
      ? '图纸单位无法确认，请选择正确单位或完成已知长度校准'
      : '图纸单位无法确认，请完成已知长度校准'
    return
  }
  calculating.value = true
  const calibration = calibrationMmPerUnit.value ? {
    start: calibrationPoints.value[0],
    end: calibrationPoints.value[1],
    real_length_mm: calibrationRealLengthMm.value,
  } : null
  const response = await API.saveMeasurement(
    drawing.value.drawing_id,
    drawing.value.source_format || 'dxf',
    rooms.value,
    unitOverrideAllowed.value ? unitOverride.value || null : null,
    calibration,
  )
  calculating.value = false
  if (!response.success) {
    error.value = response.message || '测量计算失败'
    return
  }
  measurement.value = {
    ...response.data,
    rooms: response.data.spaces,
    total_area_sqm: response.data.total_area,
  }
  emit('saved', response.data)
}
</script>

<template>
  <section class="measurement-shell" :class="{ embedded }">
    <header class="measurement-header">
      <div class="measurement-title">
        <h2>图纸预览</h2>
        <span v-if="drawing">{{ drawing.filename }}</span>
      </div>
      <div class="header-actions">
        <select
          v-if="drawing?.views?.length > 1"
          v-model="selectedViewId"
          class="view-select"
          :disabled="loadingView"
          @change="selectDrawingView"
        >
          <option v-for="view in drawing.views" :key="view.id" :value="view.id">
            {{ view.name }}（{{ view.entity_count }} 图元）
          </option>
        </select>
        <details v-if="reviewMessages.length" class="review-menu">
          <summary title="查看识别提示">
            识别提示
            <strong>{{ reviewMessages.length }}</strong>
          </summary>
          <div class="review-menu-panel">
            <div class="review-menu-heading">识别与文件提示</div>
            <ul>
              <li v-for="message in reviewMessages" :key="message">{{ message }}</li>
            </ul>
          </div>
        </details>
        <button v-if="embedded" class="close-preview" type="button" title="关闭预览" @click="emit('close')">×</button>
      </div>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div v-if="!drawing" class="empty-state">
      <div class="empty-mark">{{ sourceFormatLabel }}</div>
      <p>{{ loading ? '正在提取测量底图' : '选择一份图纸开始测量' }}</p>
    </div>

    <div v-else class="measurement-workspace">
      <div class="canvas-column">
        <div class="display-row">
          <div class="color-mode" aria-label="底图颜色模式">
            <button :class="{ active: displayMode === 'semantic' }" @click="displayMode = 'semantic'">分类色</button>
            <button :class="{ active: displayMode === 'original' }" @click="displayMode = 'original'">CAD原色</button>
            <button :class="{ active: displayMode === 'mono' }" @click="displayMode = 'mono'">黑白</button>
          </div>
          <label class="display-toggle"><input v-model="showCadTexts" type="checkbox" />原图文字</label>
          <label class="display-toggle"><input v-model="orthogonalSnap" type="checkbox" />正交吸附</label>
          <details class="layer-control">
            <summary>
              图层 {{ visibleCadLayerCount }}/{{ cadLayers.length }}
              <span>吸附 {{ snapCadLayerCount }}</span>
            </summary>
            <div class="layer-panel">
              <div class="layer-panel-toolbar">
                <strong>原始 CAD 图层</strong>
                <button type="button" @click="setAllCadLayersVisible(true)">全部显示</button>
                <button type="button" @click="setAllCadLayersVisible(false)">全部隐藏</button>
              </div>
              <input
                v-if="cadLayers.length > 8"
                v-model="layerFilter"
                class="layer-search"
                type="search"
                placeholder="搜索图层名称"
              />
              <div class="layer-columns">
                <span>图层（图元数）</span>
                <button
                  type="button"
                  :title="visibleCadLayerCount === cadLayers.length ? '隐藏所有图层' : '显示所有图层'"
                  @click="setAllCadLayersVisible(visibleCadLayerCount !== cadLayers.length)"
                >显示</button>
                <button
                  type="button"
                  :title="snapCadLayerCount === cadLayers.length ? '关闭所有图层吸附' : '开启所有图层吸附'"
                  @click="setAllCadLayersSnappable(snapCadLayerCount !== cadLayers.length)"
                >吸附</button>
              </div>
              <div class="layer-list">
                <label v-for="item in filteredCadLayers" :key="item.name" class="cad-layer-row">
                  <span class="cad-layer-name" :title="item.name">
                    <i :style="{ background: item.color }"></i>
                    <span>{{ item.name }}</span>
                    <small>{{ item.entities + item.texts }}</small>
                  </span>
                  <input
                    type="checkbox"
                    :checked="item.visible"
                    :aria-label="`${item.name} 图层显示`"
                    @change="setCadLayerVisibility(item.name, $event.target.checked)"
                  />
                  <input
                    type="checkbox"
                    :checked="item.snappable"
                    :aria-label="`${item.name} 图层参与吸附`"
                    @change="setCadLayerSnapping(item.name, $event.target.checked)"
                  />
                </label>
                <div v-if="!filteredCadLayers.length" class="layer-empty">没有匹配的图层</div>
              </div>
              <p>显示与吸附相互独立；隐藏辅助图层后仍可按需保留吸附。</p>
            </div>
          </details>
        </div>

        <div class="layer-legend">
          <span class="legend-title">颜色分类</span>
          <span v-for="item in layerLegend" :key="item.key" class="legend-item" :class="{ muted: item.hidden }">
            <button class="visibility-button" :title="item.hidden ? '显示图层' : '隐藏图层'" @click="toggleLayer(item.key)">
              {{ item.hidden ? '○' : '●' }}
            </button>
            <i :style="{ background: item.color }"></i>
            <span>{{ item.label }}</span>
            <input
              v-if="displayMode === 'semantic'"
              type="color"
              :value="item.color"
              :title="`修改${item.label}颜色`"
              @input="changeLayerColor(item.key, $event)"
            />
          </span>
        </div>

        <div class="tool-row">
          <div class="segmented" aria-label="绘制模式">
            <button :class="{ active: mode === 'select' }" @click="mode = 'select'; cancelCurrent()">选择</button>
            <button :class="{ active: mode === 'rectangle' }" @click="mode = 'rectangle'; cancelCurrent()">矩形</button>
            <button :class="{ active: mode === 'polygon' }" @click="mode = 'polygon'; cancelCurrent()">多边形</button>
            <button v-if="calibrationAllowed" :class="{ active: mode === 'calibrate' }" @click="mode = 'calibrate'; cancelCurrent()">校准</button>
            <button :class="{ active: mode === 'pan' }" @click="mode = 'pan'; cancelCurrent()">平移</button>
          </div>
          <button
            class="icon-command"
            title="撤销最后一个点"
            :disabled="mode === 'calibrate' ? !calibrationPoints.length : !currentPoints.length"
            @click="undoPoint"
          >↶</button>
          <button
            class="icon-command"
            :title="mode === 'calibrate' ? '清除校准' : '取消当前轮廓'"
            :disabled="mode === 'calibrate' ? !calibrationPoints.length && !calibrationLength : !currentPoints.length"
            @click="mode === 'calibrate' ? clearCalibration() : cancelCurrent()"
          >×</button>
          <button class="icon-command" title="放大" @click="zoomBy(0.8)">+</button>
          <button class="icon-command" title="缩小" @click="zoomBy(1.25)">−</button>
          <button class="icon-command" title="适应窗口" @click="fitView">⌗</button>
          <button v-if="mode === 'polygon'" class="command" :disabled="currentPoints.length < 3" @click="finishPolygon">闭合轮廓</button>
          <div class="canvas-status">
            {{ canvasStatus }}{{ snapKind ? ` · ${snapKind}` : '' }}
          </div>
        </div>

        <div class="canvas-wrap">
          <svg
            ref="svgRef"
            class="drawing-canvas"
            :class="{ panning: mode === 'pan' || panState?.active, selecting: mode === 'select' }"
            :viewBox="`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`"
            preserveAspectRatio="xMidYMid meet"
            @click="onCanvasClick"
            @pointerdown="startPan"
            @pointermove="onPointerMove"
            @pointerup="stopPan"
            @pointercancel="stopPan"
            @mouseleave="pointerPoint = null; clearSnapFeedback()"
            @wheel="zoom"
            @contextmenu="onContextMenu"
          >
            <rect :x="viewBox.x" :y="viewBox.y" :width="viewBox.w" :height="viewBox.h" class="canvas-background" />
            <path
              v-for="path in renderPaths"
              :key="path.id"
              :d="path.path"
              :style="{ stroke: path.color, strokeWidth: path.width, strokeDasharray: path.dash }"
              class="cad-entity"
              vector-effect="non-scaling-stroke"
            />
            <text
              v-for="text in renderTexts"
              :key="`text-${text.id}`"
              :x="text.x"
              :y="text.y"
              :font-size="text.size"
              :style="{ fill: text.color }"
              class="cad-text"
            >{{ text.text }}</text>

            <polygon
              v-for="(room, index) in rooms"
              :key="room.client_id"
              :points="roomSvgPoints(room.vertices)"
              :style="{ fill: `${colors[index % colors.length]}30`, stroke: colors[index % colors.length] }"
              class="saved-room"
              :class="{ selected: selectedRoomId === room.client_id, interactive: mode === 'select' }"
              vector-effect="non-scaling-stroke"
              @click.stop="selectRoom(room.client_id)"
            />
            <circle
              v-for="(vertex, vertexIndex) in selectedRoom?.vertices || []"
              v-show="mode === 'select'"
              :key="`vertex-${selectedRoomId}-${vertexIndex}`"
              :cx="vertex[0]"
              :cy="yAxisSum - vertex[1]"
              :r="annotationSize * 0.48"
              class="room-vertex-handle"
              vector-effect="non-scaling-stroke"
              @pointerdown.stop.prevent="startVertexDrag($event, selectedRoomId, vertexIndex)"
              @click.stop
            />
            <line
              v-for="edge in allRoomEdges"
              :key="`edge-hit-${edge.roomId}-${edge.index}`"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              class="room-edge-hit"
              :class="{ interactive: mode === 'select' }"
              vector-effect="non-scaling-stroke"
              @click.stop="selectEdge(edge)"
            />
            <g class="room-annotation">
              <text
                v-for="edge in selectedRoomEdges"
                :key="`edge-number-${edge.roomId}-${edge.index}`"
                :x="edge.labelX"
                :y="edge.labelY"
                :font-size="annotationSize"
                text-anchor="middle"
                dominant-baseline="central"
                class="edge-number"
              >{{ edge.number }}</text>
              <text
                v-if="activeEdgeLabel"
                :x="activeEdgeLabel.labelX"
                :y="activeEdgeLabel.labelY - annotationSize * 1.6"
                :font-size="annotationSize"
                text-anchor="middle"
                dominant-baseline="central"
                class="edge-length-popover"
              >{{ activeEdgeLabel.lengthLabel }}</text>
            </g>
            <line
              v-if="constraintGuide"
              :x1="constraintGuide.start[0]"
              :y1="yAxisSum - constraintGuide.start[1]"
              :x2="constraintGuide.end[0]"
              :y2="yAxisSum - constraintGuide.end[1]"
              class="constraint-guide"
              vector-effect="non-scaling-stroke"
            />
            <polyline
              v-if="previewPoints.length"
              :points="roomSvgPoints(previewPoints)"
              class="preview-room"
              vector-effect="non-scaling-stroke"
            />
            <polyline
              v-if="calibrationPreviewPoints.length"
              :points="roomSvgPoints(calibrationPreviewPoints)"
              class="calibration-line"
              vector-effect="non-scaling-stroke"
            />
            <circle
              v-for="(point, index) in calibrationPoints"
              :key="`calibration-point-${index}`"
              :cx="point[0]"
              :cy="yAxisSum - point[1]"
              :r="markerRadius * 0.8"
              class="calibration-point"
              vector-effect="non-scaling-stroke"
            />
            <circle
              v-for="(point, index) in currentPoints"
              :key="`point-${index}`"
              :cx="point[0]"
              :cy="yAxisSum - point[1]"
              :r="markerRadius * 0.7"
              class="corner-point"
              vector-effect="non-scaling-stroke"
            />
            <circle
              v-if="snapTarget && mode !== 'pan'"
              :cx="snapTarget[0]"
              :cy="yAxisSum - snapTarget[1]"
              :r="markerRadius"
              class="snap-target"
              vector-effect="non-scaling-stroke"
            />
          </svg>
        </div>
      </div>

      <aside class="measurement-sidebar">
        <div class="field-group">
          <label for="room-name">{{ selectedRoom ? '当前空间名称' : '新建空间名称' }}</label>
          <input id="room-name" v-model="roomNameModel" maxlength="100" @blur="normalizeRoomName" />
        </div>

        <div class="field-group">
          <label for="drawing-unit">图纸单位</label>
          <select id="drawing-unit" v-model="unitOverride" :disabled="!!calibrationMmPerUnit || !unitOverrideAllowed">
            <option value="">按 {{ sourceFormatLabel }} 声明（{{ drawing.unit }}）</option>
            <option value="mm">毫米 mm</option>
            <option value="cm">厘米 cm</option>
            <option value="m">米 m</option>
            <option value="in">英寸 in</option>
            <option value="ft">英尺 ft</option>
          </select>
        </div>

        <div v-if="calibrationAllowed" class="field-group calibration-group">
          <div class="field-heading">
            <label for="calibration-length">已知长度校准{{ calibrationPolicy === 'required' ? '（必填）' : '' }}</label>
            <button type="button" :disabled="!calibrationPoints.length && !calibrationLength" @click="clearCalibration">清除</button>
          </div>
          <div class="length-input-row">
            <input
              id="calibration-length"
              v-model="calibrationLength"
              type="number"
              min="0"
              step="any"
              inputmode="decimal"
              placeholder="真实长度"
            />
            <select v-model="calibrationLengthUnit" aria-label="校准长度单位">
              <option value="m">m</option>
              <option value="mm">mm</option>
            </select>
          </div>
          <small v-if="calibrationMmPerUnit">
            图上 {{ calibrationModelLength.toFixed(3) }} 单位 = {{ calibrationLength }} {{ calibrationLengthUnit }}
          </small>
          <small v-else>校准模式下选择两个端点</small>
        </div>

        <div class="room-list">
          <div class="list-heading">
            <span>已标注空间</span>
            <strong>{{ rooms.length }}</strong>
          </div>
          <div v-if="!rooms.length" class="list-empty">暂无空间</div>
          <article
            v-for="(room, index) in rooms"
            :key="room.client_id"
            class="room-row"
            :class="{ selected: selectedRoomId === room.client_id }"
            @click="selectRoom(room.client_id)"
          >
            <span class="room-swatch" :style="{ background: colors[index % colors.length] }"></span>
            <div class="room-copy">
              <strong>{{ room.name }}</strong>
              <span>
                {{ resultById.get(room.client_id)?.area_sqm?.toFixed(2) ?? localArea(room.vertices).toFixed(2) }}㎡
                · {{ room.vertices.length }} 点
              </span>
              <small v-if="room.boundary_source === 'wall_mask_furniture_fallback'" class="review-warning">
                家具线参与闭合，请核对边界
              </small>
              <small v-for="warning in resultById.get(room.client_id)?.warnings || []" :key="warning">{{ warning }}</small>
              <small v-for="roomError in resultById.get(room.client_id)?.errors || []" :key="roomError" class="invalid">{{ roomError }}</small>
              <ol v-if="selectedRoomId === room.client_id" class="edge-list">
                <li v-for="edge in selectedRoomEdges" :key="`sidebar-edge-${edge.index}`">
                  <button type="button" @click.stop="selectEdge(edge)">
                    <span>{{ edge.number }}</span>
                    <strong>{{ edge.lengthLabel }}</strong>
                  </button>
                </li>
              </ol>
            </div>
            <button class="remove-room" title="删除空间" @click.stop="removeRoom(room.client_id)">×</button>
          </article>
        </div>

        <div class="summary">
          <span>总面积</span>
          <strong>{{ measurement?.total_area_sqm?.toFixed(2) ?? rooms.reduce((sum, room) => sum + localArea(room.vertices), 0).toFixed(2) }}㎡</strong>
        </div>
        <button class="calculate-button" :disabled="!rooms.length || calculating" @click="calculate">
          {{ calculating ? '保存中' : '保存面积结果' }}
        </button>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.measurement-shell {
  min-height: 720px;
  color: #17202a;
  background: #f7f9fb;
  border: 1px solid #dce2e8;
  border-radius: 6px;
  overflow: hidden;
}
.measurement-shell.embedded {
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 0;
  border-radius: 0;
}
.measurement-shell.embedded .measurement-header,
.measurement-shell.embedded .alert { flex: 0 0 auto; }
.measurement-shell.embedded .empty-state,
.measurement-shell.embedded .measurement-workspace {
  min-height: 0;
  flex: 1 1 auto;
}
.measurement-shell.embedded .measurement-workspace { overflow: hidden; }
.measurement-shell.embedded .canvas-column,
.measurement-shell.embedded .canvas-wrap,
.measurement-shell.embedded .measurement-sidebar { min-height: 0; }
.measurement-shell.embedded .canvas-wrap { min-height: 0; }
.measurement-shell.embedded .measurement-sidebar { overflow: hidden; }

.measurement-header {
  position: relative;
  z-index: 5;
  min-height: 62px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #ffffff;
  border-bottom: 1px solid #dce2e8;
}

.measurement-header h2 { margin: 0; font-size: 16px; font-weight: 700; letter-spacing: 0; }
.measurement-title span { display: block; margin-top: 3px; max-width: 55vw; color: #66727e; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.close-preview { width: 40px; height: 40px; border: 0; background: transparent; color: #66727e; font-size: 28px; line-height: 1; cursor: pointer; }
.close-preview:hover { color: #17202a; }
.view-select { max-width: 260px; height: 40px; padding: 0 32px 0 11px; border: 1px solid #cbd3db; border-radius: 5px; background: #ffffff; color: #263442; font-size: 13px; }

.command, .icon-command, .calculate-button {
  border: 1px solid #cbd3db;
  border-radius: 5px;
  background: #ffffff;
  color: #263442;
  cursor: pointer;
  font-size: 14px;
}
.command { min-height: 40px; padding: 0 15px; }
.command.primary { border-color: #087f78; background: #087f78; color: #ffffff; }
.command:disabled, .icon-command:disabled, .calculate-button:disabled { cursor: not-allowed; opacity: .45; }
.icon-command { width: 40px; height: 40px; flex: 0 0 40px; font-size: 20px; }

.alert { margin: 10px 16px 0; padding: 9px 12px; border-radius: 4px; font-size: 12px; }
.alert.error { border: 1px solid #fecaca; background: #fff1f2; color: #b42318; }
.review-menu { position: relative; }
.review-menu summary { height: 40px; padding: 0 11px; display: flex; align-items: center; gap: 7px; border: 1px solid #e7c86c; border-radius: 5px; background: #fffbeb; color: #7a4e00; cursor: pointer; list-style: none; font-size: 13px; font-weight: 700; }
.review-menu summary::-webkit-details-marker { display: none; }
.review-menu summary::before { content: '!'; width: 18px; height: 18px; display: inline-grid; place-items: center; border-radius: 50%; background: #d99a13; color: #ffffff; font-size: 12px; }
.review-menu summary strong { min-width: 20px; height: 20px; display: inline-grid; place-items: center; border-radius: 10px; background: #fef3c7; color: #92400e; font-size: 11px; }
.review-menu[open] summary { border-color: #d99a13; background: #fff7d6; }
.review-menu-panel { position: absolute; top: calc(100% + 8px); right: 0; width: min(430px, calc(100vw - 32px)); padding: 12px 14px; border: 1px solid #e7c86c; border-radius: 5px; background: #fffdf5; color: #6f4a08; box-shadow: 0 12px 28px rgba(35,28,15,.18); }
.review-menu-heading { padding-bottom: 8px; border-bottom: 1px solid #f1dfaa; color: #4d3914; font-size: 13px; font-weight: 700; }
.review-menu-panel ul { max-height: 260px; margin: 9px 0 0; padding-left: 20px; overflow-y: auto; font-size: 12px; line-height: 1.6; }
.review-menu-panel li + li { margin-top: 6px; }

.empty-state { height: 650px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #72808d; }
.empty-mark { width: 72px; height: 54px; display: grid; place-items: center; border: 2px solid #9aa6b2; color: #53616e; font-size: 15px; font-weight: 700; }
.empty-state p { margin-top: 16px; font-size: 13px; }

.measurement-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 300px; min-height: 657px; }
.canvas-column { min-width: 0; display: flex; flex-direction: column; background: #1a2026; }
.tool-row { min-height: 58px; padding: 9px 12px; display: flex; align-items: center; gap: 8px; order: 4; background: #f4f6f8; border-top: 1px solid #d5dce3; }
.display-row { position: relative; z-index: 3; min-height: 38px; padding: 5px 10px; display: flex; align-items: center; gap: 14px; order: 2; overflow: visible; background: #27313a; border-top: 1px solid #35414b; border-bottom: 1px solid #35414b; color: #c5ced6; }
.color-mode { display: flex; padding: 2px; border: 1px solid #465460; border-radius: 4px; background: #1e272e; }
.color-mode button { height: 25px; padding: 0 9px; border: 0; border-radius: 3px; background: transparent; color: #9eabb6; cursor: pointer; font-size: 10px; }
.color-mode button.active { background: #43515d; color: #ffffff; }
.display-toggle { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; cursor: pointer; }
.display-toggle input { accent-color: #19b5a5; }
.layer-control { position: relative; margin-left: auto; font-size: 10px; }
.layer-control summary { min-width: 116px; height: 27px; padding: 0 8px; display: flex; align-items: center; justify-content: space-between; gap: 9px; border: 1px solid #465460; border-radius: 4px; background: #1e272e; color: #e1e7ec; cursor: pointer; list-style: none; }
.layer-control summary::-webkit-details-marker { display: none; }
.layer-control summary::after { content: '▾'; color: #8f9ca7; }
.layer-control[open] summary::after { content: '▴'; }
.layer-control summary span { color: #8f9ca7; }
.layer-panel { position: absolute; top: calc(100% + 7px); right: 0; width: min(360px, calc(100vw - 32px)); padding: 10px; border: 1px solid #465460; border-radius: 5px; background: #202a32; color: #c9d2da; box-shadow: 0 12px 28px rgba(0,0,0,.35); }
.layer-panel-toolbar { height: 28px; display: flex; align-items: center; gap: 6px; }
.layer-panel-toolbar strong { margin-right: auto; color: #f2f5f7; font-size: 11px; }
.layer-panel button { padding: 3px 6px; border: 1px solid #4b5964; border-radius: 3px; background: #2d3943; color: #cbd4dc; cursor: pointer; font-size: 9px; }
.layer-panel button:hover { background: #3a4853; color: #ffffff; }
.layer-search { width: 100%; height: 29px; margin: 6px 0; padding: 0 8px; border: 1px solid #465460; border-radius: 3px; outline: none; background: #182027; color: #edf2f5; font-size: 10px; }
.layer-search:focus { border-color: #42bdb3; }
.layer-columns, .cad-layer-row { display: grid; grid-template-columns: minmax(0, 1fr) 38px 38px; align-items: center; }
.layer-columns { height: 26px; padding: 0 5px; color: #85939f; border-bottom: 1px solid #3a4650; }
.layer-columns button { padding: 2px; border: 0; background: transparent; color: #8e9ca7; }
.layer-list { max-height: 300px; overflow-y: auto; }
.cad-layer-row { min-height: 31px; padding: 0 5px; border-bottom: 1px solid #303b44; cursor: default; }
.cad-layer-row:hover { background: #26333c; }
.cad-layer-name { min-width: 0; display: flex; align-items: center; gap: 7px; }
.cad-layer-name i { width: 13px; height: 2px; flex: 0 0 auto; }
.cad-layer-name span { overflow: hidden; color: #d9e0e5; text-overflow: ellipsis; white-space: nowrap; }
.cad-layer-name small { margin-left: auto; padding-right: 7px; color: #7f8d98; }
.cad-layer-row input { justify-self: center; accent-color: #19b5a5; }
.layer-empty { padding: 22px 0; color: #82909b; text-align: center; }
.layer-panel p { margin: 8px 3px 0; color: #82909b; line-height: 1.45; }
.layer-legend { min-height: 34px; padding: 6px 12px; display: flex; align-items: center; gap: 14px; order: 3; overflow-x: auto; background: #202830; border-bottom: 1px solid #303b45; color: #aab4be; font-size: 10px; white-space: nowrap; }
.legend-title { color: #71808c; }
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-item.muted { opacity: .42; }
.legend-item i { width: 16px; height: 2px; display: inline-block; }
.legend-item input[type="color"] { width: 18px; height: 18px; padding: 0; border: 1px solid #53616c; border-radius: 3px; background: transparent; cursor: pointer; }
.visibility-button { width: 16px; height: 18px; padding: 0; border: 0; background: transparent; color: #b9c4cd; cursor: pointer; font-size: 10px; }
.segmented { display: flex; padding: 2px; border: 1px solid #cbd3db; border-radius: 5px; background: #e9edf1; }
.segmented button { height: 36px; padding: 0 14px; border: 0; border-radius: 3px; background: transparent; color: #53616e; cursor: pointer; font-size: 13px; }
.segmented button.active { background: #ffffff; color: #087f78; box-shadow: 0 1px 2px rgba(0,0,0,.1); font-weight: 700; }
.canvas-status { margin-left: auto; color: #687582; font-size: 12px; }
.canvas-wrap { flex: 1; min-height: 600px; order: 1; overflow: hidden; }
.drawing-canvas { width: 100%; height: 100%; display: block; cursor: crosshair; touch-action: none; user-select: none; }
.drawing-canvas.panning { cursor: grab; }
.drawing-canvas.selecting { cursor: default; }
.canvas-background { fill: #151b20; }
.cad-entity { fill: none; opacity: .86; pointer-events: none; }
.cad-text { opacity: .74; pointer-events: none; letter-spacing: 0; }
.saved-room { stroke-width: 2; pointer-events: none; }
.saved-room.interactive { cursor: pointer; pointer-events: auto; }
.saved-room.selected { stroke-width: 3; fill-opacity: .42; }
.room-vertex-handle { fill: #ffffff; stroke: #0f766e; stroke-width: 2; cursor: grab; }
.room-vertex-handle:active { cursor: grabbing; fill: #99f6e4; }
.room-edge-hit { stroke: transparent; stroke-width: 14; pointer-events: none; }
.room-edge-hit.interactive { cursor: pointer; pointer-events: stroke; }
.room-annotation { pointer-events: none; }
.edge-number, .edge-length-popover { paint-order: stroke; stroke: rgba(13,18,22,.94); stroke-width: 3px; stroke-linejoin: round; letter-spacing: 0; }
.edge-number { fill: #f8d477; font-weight: 700; }
.edge-length-popover { fill: #ffffff; font-weight: 700; }
.constraint-guide { stroke: #5eead4; stroke-width: 1; stroke-dasharray: 6 4; opacity: .9; pointer-events: none; }
.preview-room { fill: rgba(8,127,120,.18); stroke: #24c7b8; stroke-width: 2; stroke-dasharray: 7 5; pointer-events: none; }
.calibration-line { fill: none; stroke: #f8d477; stroke-width: 2; stroke-dasharray: 5 3; pointer-events: none; }
.calibration-point { fill: #f8d477; stroke: #4c3b08; stroke-width: 2; pointer-events: none; }
.corner-point { fill: #ffffff; stroke: #087f78; stroke-width: 2; pointer-events: none; }
.snap-target { fill: rgba(36,199,184,.22); stroke: #5eead4; stroke-width: 2; pointer-events: none; }

.measurement-sidebar { min-width: 0; padding: 16px; display: flex; flex-direction: column; gap: 16px; background: #f9fafb; border-left: 1px solid #dce2e8; }
.field-group label { display: block; margin-bottom: 6px; color: #4a5568; font-size: 12px; font-weight: 600; letter-spacing: 0; }
.field-group input, .field-group select { width: 100%; height: 36px; padding: 0 10px; border: 1px solid #d5dce3; border-radius: 6px; background: #ffffff; color: #17202a; font-size: 13px; transition: border-color .15s, box-shadow .15s; }
.field-group select:disabled { background: #eef1f4; color: #7c8791; }
.field-group input:focus, .field-group select:focus { border-color: #087f78; outline: none; box-shadow: 0 0 0 2px rgba(8,127,120,.12); }
.calibration-group { padding-top: 14px; padding-bottom: 2px; border-top: 1px solid #e8ecf0; }
.field-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.field-heading label { margin-bottom: 0; }
.field-heading button { padding: 0; border: 0; background: transparent; color: #087f78; cursor: pointer; font-size: 11px; font-weight: 600; }
.field-heading button:hover { color: #065f5b; }
.field-heading button:disabled { color: #aab2b9; cursor: not-allowed; }
.length-input-row { display: grid; grid-template-columns: minmax(0, 1fr) 64px; gap: 6px; }
.calibration-group small { display: block; margin-top: 6px; color: #6b7784; font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.room-list { min-height: 0; flex: 1; overflow-y: auto; border-top: 1px solid #e8ecf0; padding-top: 6px; }
.list-heading { height: 40px; padding: 0 2px; display: flex; align-items: center; justify-content: space-between; color: #5a6872; font-size: 12px; font-weight: 600; }
.list-heading strong { min-width: 22px; height: 22px; display: inline-grid; place-items: center; border-radius: 11px; background: #e2e8f0; color: #4a5568; font-size: 11px; font-weight: 700; }
.list-empty { padding: 40px 16px; color: #94a3b8; text-align: center; font-size: 13px; background: #f1f5f9; border-radius: 6px; margin-top: 8px; }
.room-row { min-height: 56px; margin: 0 0 6px; padding: 10px 8px 10px 8px; display: grid; grid-template-columns: 6px minmax(0, 1fr) 28px; gap: 10px; align-items: start; border: 1px solid #edf0f2; border-radius: 6px; background: #ffffff; cursor: pointer; transition: background .12s, border-color .12s, box-shadow .12s; }
.room-row:hover { background: #f7fafa; border-color: #d0ddd9; }
.room-row.selected { background: #f0f9f8; border-color: #b2d8d4; box-shadow: 0 1px 4px rgba(8,127,120,.1); }
.room-swatch { width: 6px; height: 32px; border-radius: 3px; margin-top: 2px; }
.room-copy { min-width: 0; }
.room-copy strong, .room-copy span, .room-copy small { display: block; overflow-wrap: anywhere; }
.room-copy strong { font-size: 13px; font-weight: 600; color: #17202a; }
.room-copy span { margin-top: 3px; color: #6b7784; font-size: 11px; }
.room-copy small { margin-top: 4px; color: #9a6700; font-size: 10px; line-height: 1.45; }
.room-copy small.invalid { color: #b42318; }
.edge-list { margin: 8px 0 0; padding: 8px 0 0; border-top: 1px solid #e0ece8; list-style: none; }
.edge-list li + li { margin-top: 2px; }
.edge-list button { width: 100%; min-height: 32px; padding: 4px 8px; display: flex; align-items: center; justify-content: space-between; gap: 8px; border: 1px solid transparent; border-radius: 4px; background: transparent; color: #53616e; cursor: pointer; transition: background .1s; }
.edge-list button:hover { background: #e4f1ef; border-color: #c5ded9; }
.edge-list button span { width: 22px; height: 22px; display: inline-grid; place-items: center; border-radius: 50%; background: #087f78; color: #ffffff; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.edge-list button strong { color: #26343f; font-size: 11px; font-weight: 600; }
.remove-room { width: 28px; height: 28px; border: 0; border-radius: 5px; background: transparent; color: #94a3b8; cursor: pointer; font-size: 16px; line-height: 1; transition: color .12s, background .12s; }
.remove-room:hover { background: #fde8e8; color: #b42318; }
.summary { margin-top: 4px; padding: 12px 14px; display: flex; align-items: center; justify-content: space-between; border-radius: 6px; background: #f0f9f8; border: 1px solid #c5e0db; }
.summary span { color: #3d7069; font-size: 13px; font-weight: 600; }
.summary strong { color: #087f78; font-size: 24px; font-weight: 700; letter-spacing: 0; }
.calculate-button { width: 100%; height: 44px; margin-top: 2px; border: 1px solid #087f78; border-radius: 6px; background: #087f78; color: #ffffff; font-weight: 700; font-size: 14px; cursor: pointer; transition: background .15s, box-shadow .15s, transform .1s; }
.calculate-button:hover:not(:disabled) { background: #065f5b; box-shadow: 0 3px 12px rgba(8,127,120,.3); transform: translateY(-1px); }
.calculate-button:active:not(:disabled) { transform: translateY(0); }

@media (max-width: 900px) {
  .measurement-workspace { grid-template-columns: 1fr; }
  .canvas-wrap { min-height: 480px; }
  .measurement-sidebar { border-left: 0; border-top: 1px solid #dce2e8; }
  .room-list { max-height: 280px; }

  .measurement-shell.embedded { overflow-y: auto; }
  .measurement-shell.embedded .measurement-workspace {
    min-height: auto;
    flex: 0 0 auto;
    overflow: visible;
  }
  .measurement-shell.embedded .canvas-wrap { height: 60dvh; min-height: 420px; }
  .measurement-shell.embedded .measurement-sidebar { overflow: visible; }
}

@media (max-width: 620px) {
  .measurement-header { align-items: flex-start; flex-direction: column; }
  .header-actions { width: 100%; }
  .view-select { min-width: 0; flex: 1; }
  .tool-row { flex-wrap: wrap; }
  .display-row { flex-wrap: wrap; }
  .canvas-status { width: 100%; margin-left: 0; }
  .canvas-wrap { min-height: 420px; }
  .segmented { width: 100%; }
  .segmented button { flex: 1; }
}
</style>
