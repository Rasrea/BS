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

      <div v-else class="space-y-5">
        <section v-if="autoRows.length" class="rounded-xl border border-green-100 overflow-hidden">
          <div class="flex items-center justify-between px-4 py-2.5 bg-green-50 border-b border-green-100">
            <div>
              <h4 class="text-sm font-semibold text-green-800">自动识别完成</h4>
            </div>
            <span class="text-xs text-green-700">{{ autoRows.length }} 个空间</span>
          </div>
          <table class="min-w-full divide-y divide-gray-200 text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-600">空间名称</th>
              <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-600">面积(㎡)</th>
              <th class="px-3 py-2.5 text-center text-xs font-semibold text-gray-600">匹配状态</th>
              <th class="px-3 py-2.5 text-left text-xs font-semibold text-blue-700 bg-blue-50">墙面材质</th>
              <th class="px-3 py-2.5 text-left text-xs font-semibold text-green-700 bg-green-50">地面材质</th>
              <th class="px-3 py-2.5 text-left text-xs font-semibold text-purple-700 bg-purple-50">顶面材质</th>
              <th class="px-3 py-2.5 text-center text-xs font-semibold text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 bg-white">
            <tr v-for="row in autoRows" :key="row.key"
                class="hover:bg-gray-50/60 transition-colors"
                :class="{ 'bg-yellow-50/30': row.status === 'candidate' || row.status === 'unmatched' }">
              <td class="px-4 py-2.5 font-medium text-gray-800 whitespace-nowrap">{{ row.space_name }}</td>
              <td class="px-4 py-2.5 text-right text-gray-600 whitespace-nowrap">{{ formatNum(row.area) }}</td>
              <td class="px-3 py-2.5 text-center whitespace-nowrap">
                <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium" :class="statusClass(row.status)">
                  {{ shortStatusText(row.status) }}
                </span>
              </td>
              <td class="px-3 py-2.5 text-xs text-blue-700 bg-blue-50/50 max-w-[180px] truncate" :title="row.material.wall || ''">
                {{ row.material.wall || '—' }}
              </td>
              <td class="px-3 py-2.5 text-xs text-green-700 bg-green-50/50 max-w-[180px] truncate" :title="row.material.floor || ''">
                {{ row.material.floor || '—' }}
              </td>
              <td class="px-3 py-2.5 text-xs text-purple-700 bg-purple-50/50 max-w-[180px] truncate" :title="row.material.ceiling || ''">
                {{ row.material.ceiling || '—' }}
              </td>
              <td class="px-3 py-2.5 text-center whitespace-nowrap">
                <button type="button" class="text-xs text-blue-600 hover:text-blue-800 hover:underline" @click="openEditor(row)">
                  修改识别
                </button>
              </td>
            </tr>
          </tbody>
          </table>
        </section>

        <section v-if="manualNeededRows.length" class="rounded-xl border border-orange-100 overflow-hidden">
          <div class="flex items-center justify-between px-4 py-2.5 bg-orange-50 border-b border-orange-100">
            <div>
              <h4 class="text-sm font-semibold text-orange-800">待人工匹配</h4>
            </div>
            <span class="text-xs text-orange-700">{{ manualNeededRows.length }} 个空间</span>
          </div>
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-600">空间名称</th>
                <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-600">面积(㎡)</th>
                <th class="px-3 py-2.5 text-center text-xs font-semibold text-gray-600">匹配状态</th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-blue-700 bg-blue-50">墙面材质</th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-green-700 bg-green-50">地面材质</th>
                <th class="px-3 py-2.5 text-left text-xs font-semibold text-purple-700 bg-purple-50">顶面材质</th>
                <th class="px-3 py-2.5 text-center text-xs font-semibold text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white">
              <tr v-for="row in manualNeededRows" :key="row.key"
                  class="hover:bg-orange-50/40 transition-colors">
                <td class="px-4 py-2.5 font-medium text-gray-800 whitespace-nowrap">{{ row.space_name }}</td>
                <td class="px-4 py-2.5 text-right text-gray-600 whitespace-nowrap">{{ formatNum(row.area) }}</td>
                <td class="px-3 py-2.5 text-center whitespace-nowrap">
                  <span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium" :class="statusClass(row.status)">{{ shortStatusText(row.status) }}</span>
                </td>
                <td class="px-3 py-2.5 text-xs text-blue-700 bg-blue-50/50 max-w-[180px] truncate">{{ row.material.wall || '—' }}</td>
                <td class="px-3 py-2.5 text-xs text-green-700 bg-green-50/50 max-w-[180px] truncate">{{ row.material.floor || '—' }}</td>
                <td class="px-3 py-2.5 text-xs text-purple-700 bg-purple-50/50 max-w-[180px] truncate">{{ row.material.ceiling || '—' }}</td>
                <td class="px-3 py-2.5 text-center whitespace-nowrap">
                  <button type="button" class="text-xs text-blue-600 hover:text-blue-800 hover:underline" @click="openEditor(row)">修改识别</button>
                </td>
              </tr>
            </tbody>
          </table>
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

    <div v-if="editingRow" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
      <div class="w-full max-w-4xl rounded-xl bg-white shadow-xl border border-gray-100 overflow-hidden">
        <div class="flex items-start justify-between gap-4 px-5 py-4 border-b border-gray-100">
          <div>
            <h3 class="text-base font-semibold text-gray-800">编辑空间材质：{{ editingRow.space_name }}</h3>
            <p class="text-xs text-gray-400 mt-1">从本批次识别结果中选择，或在下方单独修改墙、地、顶材质。</p>
          </div>
          <button class="text-gray-400 hover:text-gray-600" @click="closeEditor">×</button>
        </div>

        <div class="px-5 py-4 space-y-5 max-h-[72vh] overflow-y-auto">
          <section>
            <div class="flex items-center justify-between gap-3 mb-2">
              <h4 class="text-sm font-semibold text-gray-700">效果图识别结果</h4>
              <span class="text-xs text-gray-400">共 {{ materialSetOptions.length }} 条</span>
            </div>
            <div v-if="materialSetOptions.length <= 2 && materialSetOptions.length" class="border border-gray-200 rounded-lg divide-y divide-gray-100 overflow-hidden">
              <button v-for="option in materialSetOptions" :key="option.key" type="button"
                      class="w-full px-4 py-3 text-left hover:bg-blue-50/50 transition-colors"
                      :class="draftSetName === option.key ? 'bg-blue-50 ring-1 ring-inset ring-blue-200' : 'bg-white'"
                      @click="selectMaterialSet(option)">
                <div class="flex items-start gap-3">
                  <span class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border"
                        :class="draftSetName === option.key ? 'border-blue-500' : 'border-gray-300'">
                    <span v-if="draftSetName === option.key" class="h-2 w-2 rounded-full bg-blue-500"></span>
                  </span>
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-1">
                      <span class="text-sm font-medium text-gray-800">{{ option.source }}</span>
                      <span v-if="option.preferred" class="text-[10px] text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded-full self-start">当前空间相关</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">{{ option.relationship }}</p>
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-1.5 mt-2 text-xs">
                      <span class="px-2 py-1 bg-blue-50 text-blue-700 rounded">墙面：{{ option.material.wall || '—' }}</span>
                      <span class="px-2 py-1 bg-green-50 text-green-700 rounded">地面：{{ option.material.floor || '—' }}</span>
                      <span class="px-2 py-1 bg-purple-50 text-purple-700 rounded">顶面：{{ option.material.ceiling || '—' }}</span>
                    </div>
                  </div>
                </div>
              </button>
            </div>
            <div v-else-if="materialSetOptions.length > 2" class="max-h-[250px] overflow-y-auto pr-1 space-y-2">
              <div class="space-y-2">
                <button v-for="option in materialSetOptions" :key="option.key" type="button"
                        class="w-full rounded-xl border p-3 text-left transition-colors hover:border-blue-300 hover:bg-blue-50/40"
                        :class="draftSetName === option.key ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-200' : 'border-gray-200 bg-white'"
                        @click="selectMaterialSet(option)">
                  <div class="flex items-start justify-between gap-2">
                    <span class="text-sm font-medium text-gray-800 leading-5">{{ option.source }}</span>
                    <span v-if="option.preferred" class="shrink-0 text-[10px] text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded-full">当前空间相关</span>
                  </div>
                  <p class="text-xs text-gray-500 mt-1.5 min-h-[2.5rem]">{{ option.relationship }}</p>
                  <div class="grid grid-cols-1 sm:grid-cols-3 gap-1.5 mt-2 text-xs">
                    <span class="px-2 py-1 bg-blue-50 text-blue-700 rounded">墙面：{{ option.material.wall || '—' }}</span>
                    <span class="px-2 py-1 bg-green-50 text-green-700 rounded">地面：{{ option.material.floor || '—' }}</span>
                    <span class="px-2 py-1 bg-purple-50 text-purple-700 rounded">顶面：{{ option.material.ceiling || '—' }}</span>
                  </div>
                </button>
              </div>
            </div>
            <div v-else class="border border-dashed border-gray-200 rounded-lg py-5 text-center text-xs text-gray-400">本批次没有可用的材质识别结果</div>
          </section>

          <section class="border-t border-gray-100 pt-4">
            <div class="flex items-center justify-between gap-3 mb-3">
              <h4 class="text-sm font-semibold text-gray-700">人工修改</h4>
              <button v-if="draftSetName !== '自定义'" type="button" class="text-xs text-blue-600 hover:underline" @click="enableCustomSet">单独调整材质</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <label v-for="surface in surfaces" :key="surface.key" class="block">
                <span class="text-xs font-medium text-gray-600">{{ surface.label }}</span>
                <input v-model="draftMaterial[surface.key]"
                       class="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                       :class="isCustomSet ? 'border-gray-300 bg-white' : 'border-gray-200 bg-gray-50 text-gray-500'"
                       :disabled="!isCustomSet"
                       :placeholder="surface.placeholder" />
              </label>
            </div>
          </section>
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
import { computed, inject, onMounted, ref, watch } from 'vue'
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

const imageSequenceByKey = computed(() => {
  const result = new Map()
  imageResults.value.forEach((image, index) => {
    result.set(getImageKey(image), index + 1)
  })
  return result
})

const imagesByRecognizedSpace = computed(() => {
  const result = new Map()
  for (const image of imageResults.value) {
    const spaceName = getImageSpace(image)
    const images = result.get(spaceName) || []
    images.push(image)
    result.set(spaceName, images)
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
    const key = `${getImageKey(image)}|${material.wall}|${material.floor}|${material.ceiling}`
    if (seen.has(key)) continue
    seen.add(key)
    const source = sourceLabel(image)
    const relationship = imageRelationshipText(image)
    const preferred = editingRow.value?.candidates?.some(candidate => getImageKey(candidate.image) === getImageKey(image)) || false
    options.push({
      key,
      source,
      relationship,
      material,
      preferred,
    })
  }
  return options
})

const isCustomSet = computed(() => draftSetName.value === '自定义')

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
    draftSetName.value = materialSetNameForMaterial(draftMaterial.value) || '自定义'
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

function selectMaterialSet(option) {
  draftSetName.value = option.key
  applyMaterialSet(option.material)
}

function enableCustomSet() {
  draftSetName.value = '自定义'
}

function isSameMaterialSet(left, right) {
  const a = normalizeMaterial(left)
  const b = normalizeMaterial(right)
  return a.wall === b.wall && a.floor === b.floor && a.ceiling === b.ceiling
}

function materialSetNameForMaterial(material) {
  const normalized = normalizeMaterial(material)
  const option = materialSetOptions.value.find(item => isSameMaterialSet(item.material, normalized))
  return option?.key || ''
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
  return { image, material, optionKey: `${getImageKey(image)}:${material.wall}|${material.floor}|${material.ceiling}` }
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

function getImageSpace(image) {
  return image?.space_name || image?.recognized_space || '未识别空间'
}

function getImageFilename(image) {
  return image?.filename || image?.original_filename || (getImageKey(image) ? `图片#${getImageKey(image)}` : '未知图片')
}

function sourceLabel(image) {
  return `${getImageSpace(image)} · 图${imageSequenceByKey.value.get(getImageKey(image)) || '?'} · ${getImageFilename(image)}`
}

function imageRelationshipText(image) {
  const spaceName = getImageSpace(image)
  const sameSpaceImages = imagesByRecognizedSpace.value.get(spaceName) || []
  const matchedSpaces = cadMatchesByImage.value.get(getImageKey(image)) || []
  const parts = []
  if (sameSpaceImages.length > 1) parts.push(`该空间有 ${sameSpaceImages.length} 张效果图`)
  if (matchedSpaces.length > 1) parts.push(`该图对应 ${matchedSpaces.length} 个 CAD 空间：${matchedSpaces.map(space => space.space_name || space.name).join('、')}`)
  if (matchedSpaces.length === 1) parts.push(`对应 CAD 空间：${matchedSpaces[0].space_name || matchedSpaces[0].name}`)
  return parts.join('；') || '当前图仅对应一个识别空间'
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

function formatNum(value) {
  const num = Number(value || 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}

function handleExport() {}
</script>
