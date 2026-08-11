<template>
  <div class="space-y-4">
    <div class="card">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h3 class="text-base font-semibold text-gray-800">融合报价</h3>
          <p class="text-xs text-gray-500 mt-1">
            读取当前批次 CAD 与效果图识别结果；列表只展示融合结果，点“编辑”可按墙/地/顶分别选择或手填材质。
          </p>
        </div>
        <button class="btn-secondary text-sm" :disabled="loading" @click="loadCurrentBatch">
          {{ loading ? '刷新中...' : '刷新当前批次' }}
        </button>
      </div>

      <div v-if="loadError" class="mt-4 p-3 rounded-xl text-sm bg-yellow-50 text-yellow-700 border border-yellow-100">
        {{ loadError }}
      </div>

      <div v-if="currentBatch" class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
        <div class="rounded-xl border border-blue-100 bg-blue-50 p-3">
          <div class="text-xs text-blue-500">CAD 空间</div>
          <div class="text-xl font-semibold text-blue-700">{{ currentBatch.space_count || 0 }}</div>
        </div>
        <div class="rounded-xl border border-green-100 bg-green-50 p-3">
          <div class="text-xs text-green-500">效果图</div>
          <div class="text-xl font-semibold text-green-700">{{ imageResults.length }}</div>
        </div>
        <div class="rounded-xl border border-purple-100 bg-purple-50 p-3">
          <div class="text-xs text-purple-500">总面积</div>
          <div class="text-xl font-semibold text-purple-700">{{ formatNum(currentBatch.total_area) }}㎡</div>
        </div>
      </div>
    </div>

    <div v-if="currentBatch" class="card">
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
        <h3 class="text-sm font-semibold text-gray-800">融合匹配看板</h3>
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span class="px-2 py-1 rounded-full bg-green-50 text-green-700 border border-green-100">自动 {{ autoRows.length }}</span>
          <span class="px-2 py-1 rounded-full bg-orange-50 text-orange-700 border border-orange-100">候选 {{ candidateRows.length }}</span>
          <span class="px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100">已编辑 {{ manualMatchedCount }}</span>
          <span class="px-2 py-1 rounded-full bg-yellow-50 text-yellow-700 border border-yellow-100">待处理 {{ unresolvedCount }}</span>
        </div>
      </div>

      <div v-if="cadSpaces.length === 0" class="text-sm text-gray-400 py-6 text-center">
        当前批次暂无 CAD 空间，请先在图纸分析页点击开始分析。
      </div>

      <div v-else class="grid grid-cols-1 xl:grid-cols-[1fr_1fr] gap-4">
        <section class="rounded-2xl border border-green-100 bg-gradient-to-br from-green-50 to-white overflow-hidden">
          <div class="flex items-center justify-between px-3 py-2 border-b border-green-100/70">
            <h4 class="text-sm font-semibold text-green-800">已自动匹配</h4>
            <span class="text-xs px-2.5 py-1 rounded-full bg-white text-green-700 border border-green-100 shadow-sm">{{ autoRows.length }} 项</span>
          </div>
          <div v-if="autoRows.length === 0" class="text-sm text-green-700/70 px-4 py-8 text-center">暂无自动匹配成功项。</div>
          <div v-else class="p-2 space-y-1.5 max-h-[520px] overflow-y-auto">
            <div v-for="row in autoRows" :key="row.key" class="rounded-lg border bg-white px-2.5 py-1.5 shadow-sm">
              <div class="grid grid-cols-[76px_42px_58px_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.15fr)_42px] items-center gap-2 text-xs whitespace-nowrap">
                <span class="font-semibold text-gray-800 text-sm truncate">{{ row.space_name }}</span>
                <span class="px-1.5 py-0.5 rounded-full text-center" :class="statusClass(row.status)">{{ shortStatusText(row.status) }}</span>
                <span class="text-gray-400">{{ formatNum(row.area) }}㎡</span>
                <MaterialPill v-if="hasMaterialResult(row)" label="墙面" :value="row.material.wall || '默认'" tone="wall" />
                <MaterialPill v-if="hasMaterialResult(row)" label="地面" :value="row.material.floor || '默认'" tone="floor" />
                <MaterialPill v-if="hasMaterialResult(row)" label="顶面" :value="row.material.ceiling || '默认'" tone="ceiling" />
                <span v-if="!hasMaterialResult(row)" class="col-span-3 text-gray-600 truncate">{{ row.candidateReason }}</span>
                <button type="button" class="text-xs text-blue-600 hover:text-blue-800 text-right" @click="openEditor(row)">编辑</button>
              </div>
            </div>
          </div>
        </section>

        <section class="rounded-2xl border border-yellow-100 bg-gradient-to-br from-yellow-50 to-white overflow-hidden">
          <div class="flex items-center justify-between px-3 py-2 border-b border-yellow-100/70">
            <h4 class="text-sm font-semibold text-yellow-800">需人工处理</h4>
            <span class="text-xs px-2.5 py-1 rounded-full bg-white text-yellow-700 border border-yellow-100 shadow-sm">{{ manualNeededRows.length }} 项</span>
          </div>
          <div v-if="manualNeededRows.length === 0" class="px-4 py-8 bg-white text-center">
            <div class="text-sm font-medium text-green-700">全部空间已自动融合</div>
            <div class="text-xs text-gray-400 mt-1">可以直接生成报价。</div>
          </div>
          <div v-else class="p-2 space-y-1.5 max-h-[520px] overflow-y-auto">
            <div v-for="row in manualNeededRows" :key="row.key" class="rounded-lg border bg-white px-2.5 py-1.5 shadow-sm">
              <div class="grid grid-cols-[76px_42px_58px_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.15fr)_42px] items-center gap-2 text-xs whitespace-nowrap">
                <span class="font-semibold text-gray-800 text-sm truncate">{{ row.space_name }}</span>
                <span class="px-1.5 py-0.5 rounded-full text-center" :class="statusClass(row.status)">{{ shortStatusText(row.status) }}</span>
                <span class="text-gray-400">{{ formatNum(row.area) }}㎡</span>
                <MaterialPill v-if="hasMaterialResult(row)" label="墙面" :value="row.material.wall || '默认'" tone="wall" />
                <MaterialPill v-if="hasMaterialResult(row)" label="地面" :value="row.material.floor || '默认'" tone="floor" />
                <MaterialPill v-if="hasMaterialResult(row)" label="顶面" :value="row.material.ceiling || '默认'" tone="ceiling" />
                <span v-if="!hasMaterialResult(row)" class="col-span-3 text-gray-600 truncate">{{ row.candidateReason }}</span>
                <button type="button" class="text-xs text-blue-600 hover:text-blue-800 text-right" @click="openEditor(row)">编辑</button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="flex items-center gap-3 mt-4">
        <button class="btn-primary" :disabled="quoting || cadSpaces.length === 0" @click="generateQuote">
          {{ quoting ? '生成中...' : '生成融合报价' }}
        </button>
        <span v-if="quoteError" class="text-xs text-red-600">{{ quoteError }}</span>
        <span v-else class="text-xs text-gray-400">编辑后的墙/地/顶材质会作为人工融合结果传给后端。</span>
      </div>
    </div>

    <div v-if="imageResults.length > 0" class="card">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">当前批次效果图识别</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div v-for="image in imageResults" :key="getImageKey(image)" class="rounded-lg border border-gray-100 bg-gray-50 p-3 text-sm">
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium text-gray-800">{{ image.space_name || image.recognized_space || '未识别空间' }}</span>
            <span class="text-xs text-gray-400">{{ formatConfidence(image.confidence) }}</span>
          </div>
          <div class="text-xs text-gray-400 mt-1 truncate">{{ image.filename || image.original_filename || image.id }}</div>
          <div class="text-xs text-gray-600 mt-2 truncate">{{ materialSummary(image) || '未识别到具体材质' }}</div>
        </div>
      </div>
    </div>

    <div v-if="editingRow" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
      <div class="w-full max-w-3xl rounded-2xl bg-white shadow-xl border border-gray-100">
        <div class="flex items-start justify-between gap-4 px-5 py-4 border-b border-gray-100">
          <div>
            <h3 class="text-base font-semibold text-gray-800">编辑空间材质：{{ editingRow.space_name }}</h3>
            <p class="text-xs text-gray-400 mt-1">先一键套用整套材质，再按需微调墙、地、顶。</p>
          </div>
          <button class="text-gray-400 hover:text-gray-600" @click="closeEditor">×</button>
        </div>

        <div class="px-5 py-4 space-y-3 max-h-[70vh] overflow-y-auto">
          <div class="rounded-2xl border border-gray-100 bg-gradient-to-br from-slate-50 to-white p-4">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-3 items-start">
              <label class="block">
                <span class="text-xs font-semibold text-gray-600">整体材质</span>
                <select v-model="draftSetName"
                        class="mt-1 w-full border border-gray-300 rounded-xl px-3 py-2 text-sm bg-white shadow-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                        @change="applyMaterialSetByName">
                  <option value="自定义">自定义</option>
                  <option v-for="option in materialSetOptions" :key="option.key" :value="option.title">
                    {{ option.shortTitle }}
                  </option>
                </select>
              </label>

              <label v-for="surface in surfaces" :key="surface.key" class="block">
                <span class="text-xs font-semibold text-gray-600">{{ surface.label }}</span>
                <input v-model="draftMaterial[surface.key]"
                       :list="`fusion-${surface.key}-options`"
                       class="mt-1 w-full border rounded-xl px-3 py-2 text-sm shadow-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                       :class="isCustomSet ? 'border-gray-300 bg-white' : 'border-gray-200 bg-gray-100 text-gray-500 cursor-not-allowed'"
                       :disabled="!isCustomSet"
                       :placeholder="surface.placeholder" />
                <datalist :id="`fusion-${surface.key}-options`">
                  <option v-for="option in materialOptions(surface.key)" :key="option.key" :value="option.value" />
                </datalist>
              </label>
            </div>
            <div class="mt-2 text-xs text-gray-400">
              选择“自定义”后可修改墙、地、顶；选择识别出的整体材质会锁定三项并一次性带入。
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between gap-3 px-5 py-4 border-t border-gray-100">
          <button class="btn-secondary text-sm" @click="clearDraft">清空材质</button>
          <div class="flex items-center gap-2">
            <button class="btn-secondary text-sm" @click="closeEditor">取消</button>
            <button class="btn-primary text-sm" @click="saveEditor">保存材质</button>
          </div>
        </div>
      </div>
    </div>

    <QuoteDisplay v-if="quoteResult" :data="quoteResult" @export="handleExport" />
  </div>
</template>

<script setup>
import { computed, defineComponent, h, inject, onMounted, ref, watch } from 'vue'
import API from '../services/api.js'
import QuoteDisplay from './QuoteDisplay.vue'

const emit = defineEmits(['quote-exists'])
const refreshKey = inject('refreshKey', ref(0))

const loading = ref(false)
const quoting = ref(false)
const loadError = ref('')
const quoteError = ref('')
const currentData = ref(null)
const quoteResult = ref(null)
const manualMaterials = ref({})
const editingRow = ref(null)
const draftSetName = ref('自定义')
const draftMaterial = ref({ wall: '', floor: '', ceiling: '' })

const surfaces = [
  { key: 'wall', label: '墙面材质', placeholder: '如：乳胶漆、墙布、木饰面' },
  { key: 'floor', label: '地面材质', placeholder: '如：地砖、木地板、大理石' },
  { key: 'ceiling', label: '顶面材质', placeholder: '如：石膏板吊顶、铝扣板' },
]

const currentBatch = computed(() => currentData.value?.data || currentData.value || null)
const cadSpaces = computed(() => currentBatch.value?.cad_spaces || [])
const imageResults = computed(() => currentBatch.value?.image_results || [])

const candidatesBySpace = computed(() => {
  const result = new Map()
  for (const space of cadSpaces.value) {
    const spaceName = space.space_name || space.name || ''
    if (!spaceName) continue
    const candidates = imageResults.value
      .filter(image => namesMatch(spaceName, image.space_name || image.recognized_space || ''))
      .map(image => normalizeImageMaterial(image))
    result.set(spaceName, candidates)
  }
  return result
})

const cadMatchesByImage = computed(() => {
  const result = new Map()
  for (const image of imageResults.value) {
    const imageKey = getImageKey(image)
    const imageSpace = image.space_name || image.recognized_space || ''
    if (!imageKey || !imageSpace) continue
    const matchedSpaces = cadSpaces.value.filter(space => namesMatch(space.space_name || space.name, imageSpace))
    result.set(imageKey, matchedSpaces)
  }
  return result
})

const fusionRows = computed(() => cadSpaces.value.map((space, idx) => {
  const spaceName = space.space_name || space.name || `未命名#${idx + 1}`
  const manual = manualMaterials.value[spaceName] || {}
  const candidates = candidatesBySpace.value.get(spaceName) || []
  const uniqueCandidate = candidates.length === 1 ? candidates[0] : null
  const reverseMatches = uniqueCandidate ? cadMatchesByImage.value.get(getImageKey(uniqueCandidate.image)) || [] : []
  const auto = uniqueCandidate && reverseMatches.length === 1 ? uniqueCandidate : null
  const hasManual = hasAnyMaterial(manual)
  const isAmbiguous = candidates.length > 1 || (uniqueCandidate && reverseMatches.length > 1)
  return {
    key: space.id || spaceName,
    space_name: spaceName,
    area: Number(space.area_sqm ?? space.area ?? 0),
    status: hasManual ? 'manual' : (auto ? 'auto' : (isAmbiguous ? 'candidate' : 'unmatched')),
    material: hasManual ? manual : (auto?.material || {}),
    image: auto?.image || null,
    candidates,
    candidateReason: candidates.length > 1
      ? `${candidates.length} 个可能来源`
      : (uniqueCandidate && reverseMatches.length > 1 ? `同一效果图命中 ${reverseMatches.length} 个 CAD 空间` : '当前批次无对应效果图'),
  }
}))

const autoRows = computed(() => fusionRows.value.filter(row => row.status === 'auto'))
const manualNeededRows = computed(() => fusionRows.value.filter(row => row.status !== 'auto'))
const candidateRows = computed(() => manualNeededRows.value.filter(row => row.status === 'candidate'))
const manualMatchedCount = computed(() => fusionRows.value.filter(row => row.status === 'manual').length)
const unresolvedCount = computed(() => fusionRows.value.filter(row => row.status === 'candidate' || row.status === 'unmatched').length)

const materialSetOptions = computed(() => {
  const seen = new Set()
  const options = []
  const images = [
    ...(editingRow.value?.candidates?.map(candidate => candidate.image) || []),
    ...imageResults.value,
  ]
  for (const image of images) {
    const material = normalizeMaterial(image.material_info || image)
    if (!hasAnyMaterial(material)) continue
    const key = `${material.wall}|${material.floor}|${material.ceiling}`
    if (seen.has(key)) continue
    seen.add(key)
    options.push({
      key,
      title: `墙:${material.wall || '默认'} 地:${material.floor || '默认'} 顶:${material.ceiling || '默认'}`,
      shortTitle: `${material.wall || '默认'} / ${material.floor || '默认'} / ${material.ceiling || '默认'}`,
      material,
    })
  }
  return options
})

const isCustomSet = computed(() => draftSetName.value === '自定义')

const MaterialPill = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, default: '默认' },
    tone: { type: String, default: 'wall' },
  },
  setup(props) {
    return () => h('span', {
      class: [
        'inline-flex items-center gap-1.5 min-w-0 text-xs leading-none',
      ].join(' '),
    }, [
      h('span', { class: ['shrink-0 rounded px-1.5 py-1', materialPillClass(props.tone)].join(' ') }, props.label),
      h('span', { class: 'font-medium text-gray-700 truncate' }, props.value || '默认'),
    ])
  },
})

onMounted(loadCurrentBatch)

watch(refreshKey, () => {
  loadCurrentBatch()
})

async function loadCurrentBatch() {
  loading.value = true
  loadError.value = ''
  quoteError.value = ''
  quoteResult.value = null
  const res = await API.getCurrentFusionData()
  if (res.success) {
    currentData.value = res
    seedManualMaterials()
  } else {
    currentData.value = null
    loadError.value = res.message || '暂无当前批次识别结果'
  }
  loading.value = false
}

function seedManualMaterials() {
  const next = {}
  for (const space of cadSpaces.value) {
    const spaceName = space.space_name || space.name
    if (spaceName) next[spaceName] = manualMaterials.value[spaceName] || { wall: '', floor: '', ceiling: '' }
  }
  manualMaterials.value = next
}

function openEditor(row) {
  editingRow.value = row
  const current = normalizeMaterial(row.material || manualMaterials.value[row.space_name] || {})
  if (!hasAnyMaterial(current) && row.candidates?.length) {
    draftMaterial.value = defaultMaterialFromCandidates(row.candidates)
    draftSetName.value = materialSetNameForMaterial(draftMaterial.value) || materialSetOptions.value[0]?.title || '自定义'
    return
  }
  draftMaterial.value = current
  draftSetName.value = materialSetNameForMaterial(current) || '自定义'
}

function closeEditor() {
  editingRow.value = null
}

function clearDraft() {
  draftSetName.value = '自定义'
  draftMaterial.value = { wall: '', floor: '', ceiling: '' }
}

function saveEditor() {
  if (!editingRow.value) return
  manualMaterials.value[editingRow.value.space_name] = normalizeMaterial(draftMaterial.value)
  closeEditor()
}

function applyMaterialSet(material) {
  draftMaterial.value = normalizeMaterial(material)
}

function applyMaterialSetByName() {
  if (draftSetName.value === '自定义') return
  const option = materialSetOptions.value.find(item => item.title === draftSetName.value)
  if (option) applyMaterialSet(option.material)
}

function isSameMaterialSet(left, right) {
  const a = normalizeMaterial(left)
  const b = normalizeMaterial(right)
  return a.wall === b.wall && a.floor === b.floor && a.ceiling === b.ceiling
}

function materialSetNameForMaterial(material) {
  const normalized = normalizeMaterial(material)
  const option = materialSetOptions.value.find(item => isSameMaterialSet(item.material, normalized))
  return option?.title || ''
}

function materialOptions(surfaceKey) {
  const seen = new Set()
  const options = []
  const preferredImages = editingRow.value?.candidates?.map(candidate => candidate.image) || []
  for (const image of preferredImages) {
    appendMaterialOption(options, seen, surfaceKey, image, true)
  }
  for (const image of imageResults.value) {
    appendMaterialOption(options, seen, surfaceKey, image, false)
  }
  return options
}

function appendMaterialOption(options, seen, surfaceKey, image, preferred) {
  const material = normalizeMaterial(image.material_info || image)
  const value = material[surfaceKey]
  if (!value) return
  const optionKey = `${surfaceKey}:${value}`
  if (seen.has(optionKey)) return
  seen.add(optionKey)
  options.push({
    key: optionKey,
    value,
    imageId: getImageKey(image),
    preferred,
  })
}

function defaultMaterialFromCandidates(candidates) {
  const material = { wall: '', floor: '', ceiling: '' }
  for (const surface of surfaces) {
    const candidate = candidates.find(item => item.material?.[surface.key])
    material[surface.key] = candidate?.material?.[surface.key] || ''
  }
  return material
}

async function generateQuote() {
  quoting.value = true
  quoteError.value = ''
  const manualBindings = fusionRows.value
    .filter(row => row.status === 'manual')
    .map(row => ({
      space_name: row.space_name,
      material_info: normalizeMaterial(row.material),
    }))
  const res = await API.quoteLatestFusion(manualBindings)
  if (res.success) {
    quoteResult.value = res
    refreshKey.value++
    emit('quote-exists', res.data?.quote_id)
  } else {
    quoteError.value = res.message || '生成融合报价失败'
  }
  quoting.value = false
}

function normalizeImageMaterial(image) {
  const material = normalizeMaterial(image.material_info || image)
  return { image, material }
}

function normalizeMaterial(material) {
  return {
    wall: material?.wall || material?.wall_material || material?.墙面材质 || '',
    floor: material?.floor || material?.floor_material || material?.地面材质 || '',
    ceiling: material?.ceiling || material?.ceiling_material || material?.顶面材质 || '',
  }
}

function hasAnyMaterial(material) {
  return !!(material?.wall || material?.floor || material?.ceiling)
}

function hasMaterialResult(row) {
  return row.status === 'manual' || row.status === 'auto'
}

function namesMatch(cadName = '', imageName = '') {
  const left = String(cadName).trim()
  const right = String(imageName).trim()
  if (!left || !right) return false
  if (left === right) return true
  if (left.includes(right) || right.includes(left)) return true
  const groups = [
    ['客厅', '大厅', '起居室', '客餐厅'],
    ['主卧', '主人房'],
    ['次卧', '卧室', '客房', '儿童房', '老人房'],
    ['厨房', '西厨', '中厨'],
    ['卫生间', '主卫', '客卫', '卫浴'],
    ['餐厅', '饭厅'],
    ['阳台', '生活阳台', '入户花园'],
    ['衣帽间', '衣帽区'],
  ]
  return groups.some(group => group.some(name => left.includes(name)) && group.some(name => right.includes(name)))
}

function materialSummary(image) {
  return materialText(normalizeMaterial(image.material_info || image))
}

function materialText(material) {
  return [
    material.wall ? `墙面：${material.wall}` : '',
    material.floor ? `地面：${material.floor}` : '',
    material.ceiling ? `顶面：${material.ceiling}` : '',
  ].filter(Boolean).join('；')
}

function getImageKey(image) {
  return String(image?.id || image?.image_result_id || image?.filename || image?.original_filename || '')
}

function shortStatusText(status) {
  return {
    auto: '自动',
    manual: '已编',
    candidate: '候选',
    unmatched: '待填',
  }[status] || '未知'
}

function statusClass(status) {
  return {
    auto: 'bg-green-50 text-green-700',
    manual: 'bg-blue-50 text-blue-700',
    candidate: 'bg-orange-50 text-orange-700',
    unmatched: 'bg-yellow-50 text-yellow-700',
  }[status] || 'bg-gray-50 text-gray-600'
}

function materialPillClass(tone) {
  return {
    wall: 'border-sky-100 bg-sky-50 text-sky-800',
    floor: 'border-amber-100 bg-amber-50 text-amber-800',
    ceiling: 'border-violet-100 bg-violet-50 text-violet-800',
  }[tone] || 'border-gray-100 bg-gray-50 text-gray-700'
}

function formatNum(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function formatConfidence(value) {
  const num = Number(value || 0)
  return num ? `${Math.round(num * 100)}%` : '—'
}

function handleExport() {}
</script>
