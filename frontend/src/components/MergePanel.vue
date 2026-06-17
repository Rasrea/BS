<template>
  <div>
    <!-- 步骤1：选择CAD结果 -->
    <div class="card mb-4">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">① 选择CAD解析结果</h3>
      <select v-model="selectedCadId" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
        <option value="">-- 请选择CAD结果 --</option>
        <option v-for="r in cadResults" :key="r.id" :value="r.id">
          {{ r.drawing_name || ('图纸#' + r.id) }} — {{ r.space_count || 0 }}个空间
        </option>
      </select>
    </div>

    <!-- 步骤2：选择图片识别结果 -->
    <div class="card mb-4">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">② 选择效果图识别结果（可多选）</h3>
      <div v-if="imageResults.length === 0" class="text-sm text-gray-400 py-4 text-center">
        暂无效果图识别记录，请先在「首页」上传效果图
      </div>
      <div v-else class="space-y-2 max-h-48 overflow-y-auto">
        <label v-for="r in imageResults" :key="r.id"
               class="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer border border-gray-100">
          <input type="checkbox" :value="r.id" v-model="selectedImageIds" class="rounded text-primary-600" />
          <div class="flex-1 text-sm">
            <span class="font-medium text-gray-800">{{ r.recognized_space || '未识别空间' }}</span>
            <span class="text-gray-400 ml-2">{{ r.original_filename || ('图片#' + r.id) }}</span>
          </div>
          <span v-if="r.confidence" class="text-xs px-2 py-0.5 rounded-full"
            :class="r.confidence > 0.7 ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'">
            {{ (r.confidence * 100).toFixed(0) }}%
          </span>
        </label>
      </div>
    </div>

    <!-- 步骤2.5：自动匹配建议 -->
    <div class="card mb-4" v-if="showSuggestions && suggestionMatches.length > 0">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">③ 自动匹配建议 <span class="text-xs font-normal text-gray-400 ml-1">— 同义词引擎自动匹配CAD空间</span></h3>
      <div class="text-xs text-gray-500 mb-3">系统已为每个AI识别空间自动推荐匹配的CAD空间。点击「确认绑定」将材质写入CAD空间。</div>
      <div class="space-y-3">
        <div v-for="m in suggestionMatches" :key="m.image_id"
             class="border border-gray-200 rounded-lg p-3"
             :class="getMatchCardClass(m)">
          <!-- 头部：AI识别空间 -->
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">AI</span>
              <span class="font-medium text-gray-800">{{ m.recognized_space }}</span>
              <span v-if="m.confidence" class="text-xs text-gray-400">
                置信度 {{ (m.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <span v-if="isConfirmed(m)" class="text-xs text-green-600 font-medium">✓ 已绑定</span>
          </div>
          <!-- 材质预览 -->
          <div class="text-xs text-gray-500 mb-2 pl-6">
            <span v-if="m.material_info.wall" class="mr-3">墙面: {{ m.material_info.wall }}</span>
            <span v-if="m.material_info.floor" class="mr-3">地面: {{ m.material_info.floor }}</span>
            <span v-if="m.material_info.ceiling">顶面: {{ m.material_info.ceiling }}</span>
            <span v-if="!m.material_info.wall && !m.material_info.floor && !m.material_info.ceiling" class="text-gray-400">未识别到具体材质</span>
          </div>
          <!-- 匹配的CAD空间列表 -->
          <div v-if="m.matched_cad_spaces.length > 0" class="space-y-1 pl-6">
            <div v-for="cad in m.matched_cad_spaces" :key="cad.cad_id"
                 class="flex items-center justify-between bg-gray-50 rounded px-2 py-1 text-sm">
              <div class="flex items-center gap-2">
                <span class="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">CAD</span>
                <span>{{ cad.cad_name }}</span>
                <span class="text-xs text-gray-400">{{ cad.area ? cad.area.toFixed(1) + '㎡' : '' }}</span>
              </div>
              <button v-if="!isCadConfirmed(m.image_id, cad.cad_id)"
                      @click="confirmMatch(m.image_id, cad.cad_id)"
                      class="text-xs px-3 py-1 rounded bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
                      :disabled="confirmingMatch[m.image_id+'-'+cad.cad_id]">
                {{ confirmingMatch[m.image_id+'-'+cad.cad_id] ? '绑定中...' : '确认绑定' }}
              </button>
              <span v-else class="text-xs text-green-600">✓ 已绑定</span>
            </div>
          </div>
          <div v-else class="pl-6 text-sm text-yellow-600">
            ⚠ 未找到匹配的CAD空间
          </div>
        </div>
      </div>
    </div>

    <!-- 步骤3：人工绑定（备选方案） -->
    <div class="card mb-4" v-if="selectedCadId">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">④ 人工空间-材质绑定（可选，修正未命名空间）</h3>
      <div class="text-xs text-gray-400 mb-3">当自动匹配不准确时，可手动将CAD空间绑定到材质描述。</div>
      <div class="space-y-2">
        <div v-for="(cadId, idx) in cadBindingOptions" :key="cadId" class="flex items-center gap-3">
          <select v-model="bindings[idx].cad_space_name" class="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
            <option value="">-- CAD空间 --</option>
            <option v-for="s in currentCadSpaces" :key="s.id" :value="s.name || ('未命名#' + s.id)">
              {{ s.name || ('未命名#' + s.id) }} ({{ s.area ? s.area.toFixed(1) : 0 }}㎡)
            </option>
          </select>
          <input v-model="bindings[idx].material_desc" placeholder="材质描述（如：乳胶漆墙面）"
                 class="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm" />
          <button @click="addBinding" class="text-primary-600 hover:text-primary-800 text-lg leading-none">＋</button>
          <button v-if="bindings.length > 1" @click="removeBinding(idx)"
                  class="text-red-400 hover:text-red-600 text-lg leading-none">×</button>
        </div>
      </div>
    </div>

    <!-- 执行融合 -->
    <div class="flex items-center gap-4 mb-6">
      <button class="btn-primary" :disabled="!selectedCadId || merging || loadingSuggestions"
              @click="doMerge">
        <svg v-if="merging" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        {{ merging ? '融合中...' : '🔄 执行数据融合' }}
      </button>
      <span v-if="loadingSuggestions" class="text-xs text-blue-500 animate-pulse">正在分析匹配建议...</span>
      <span v-if="mergeResult" class="text-xs text-green-600">✓ 融合完成</span>
      <span v-if="mergeError" class="text-xs text-red-600">{{ mergeError }}</span>
    </div>

    <!-- 融合结果 -->
    <QuoteDisplay v-if="mergeResult" :data="mergeResult" @export="handleExport" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, inject } from 'vue'
import API from '../services/api.js'
import QuoteDisplay from './QuoteDisplay.vue'

const refreshKey = inject('refreshKey', ref(0))

const emit = defineEmits(['quote-exists'])

const cadResults = ref([])
const imageResults = ref([])
const selectedCadId = ref(null)
const selectedImageIds = ref([])
const merging = ref(false)
const mergeResult = ref(null)
const mergeError = ref('')
const bindings = ref([{ cad_space_name: '', material_desc: '' }])

// 空间列表
const spaces = ref([])
const spacesLoading = ref(false)

// 自动匹配建议
const loadingSuggestions = ref(false)
const suggestionMatches = ref([])
const confirmedMatches = ref({})  // { "imageId-cadId": true }
const confirmingMatch = ref({})   // { "imageId-cadId": true }

const cadBindingOptions = computed(() => bindings.value.map((_, i) => i))

const currentCadSpaces = computed(() => {
  // 优先从实时加载的空间列表取
  if (spaces.value.length > 0) return spaces.value
  // 备选：从CAD结果中提取
  const cad = cadResults.value.find(r => r.id === selectedCadId.value)
  return cad?.detail_json?.spaces || cad?.spaces || []
})

const showSuggestions = computed(() => {
  return selectedCadId.value && selectedImageIds.value.length > 0
})

function isConfirmed(m) {
  return m.matched_cad_spaces.some(cad => confirmedMatches.value[m.image_id + '-' + cad.cad_id])
}

function isCadConfirmed(imageId, cadId) {
  return !!confirmedMatches.value[imageId + '-' + cadId]
}

function getMatchCardClass(m) {
  if (isConfirmed(m)) return 'border-green-200 bg-green-50'
  if (m.matched_cad_spaces.length === 0) return 'border-yellow-200 bg-yellow-50'
  return ''
}

function addBinding() { bindings.value.push({ cad_space_name: '', material_desc: '' }) }
function removeBinding(idx) { bindings.value.splice(idx, 1) }

async function loadResults() {
  // 加载所有已解析CAD图纸（不限量）
  try {
    const drawingsRes = await API.get('/drawings')
    if (drawingsRes.success && Array.isArray(drawingsRes.data)) {
      const parsed = drawingsRes.data.filter(d => d.parse_status === 'completed' && d.cad_result_json)
      cadResults.value = parsed.map(d => ({
        id: d.id,
        drawing_name: d.filename || ('图纸#' + d.id),
        space_count: d.cad_result_json?.space_count || d.cad_result_json?.spaces_count || d.space_count || 0,
        detail_json: d.cad_result_json,
        total_area: d.cad_result_json?.total_area || d.total_area || 0,
      }))
    }
  } catch (e) {}
  // 如果没从drawings取到，回退到从历史记录取
  if (cadResults.value.length === 0) {
    const h = await API.getHistory(1, 50)
    if (h.success && h.data?.quotes?.items) {
      const seen = new Set()
      h.data.quotes.items.forEach(q => {
        if (q.cad_result_id && !seen.has(q.cad_result_id)) {
          seen.add(q.cad_result_id)
          cadResults.value.push({
            id: q.cad_result_id,
            drawing_name: q.project_name || ('图纸#' + q.cad_result_id),
            space_count: q.space_count || 0,
            detail_json: q.cad_detail_json || q.detail_json,
          })
        }
      })
    }
  }
  // 自动选中最新一条
  if (cadResults.value.length > 0 && !selectedCadId.value) {
    selectedCadId.value = cadResults.value[0].id
    await loadSpaces()
  }
  // 🌟 加载效果图识别结果：尝试专用接口 + 历史记录回退
  await loadImageResults()
}

// 🌟 加载效果图识别结果（独立函数，便于复用）
async function loadImageResults() {
  imageResults.value = []
  // 1. 优先尝试专用接口
  try {
    const imgRes = await API.getImageResults()
    if (imgRes.success && Array.isArray(imgRes.data)) {
      imgRes.data.forEach(img => {
        imageResults.value.push({
          id: img.id || img.image_result_id,
          recognized_space: img.recognized_space || img.space_name || '未识别',
          original_filename: img.original_filename || img.filename || ('图片#' + (img.id || 0)),
          confidence: img.confidence || 0,
        })
      })
      return  // 成功获取到数据就直接返回
    }
  } catch (e) { /* 静默降级到历史记录回退 */ }
  // 2. 回退：从历史记录中提取
  try {
    const resp = await fetch('/api/history?page=1&page_size=10')
    const body = await resp.json()
    if (body.success && body.data?.quotes?.items) {
      const seen = new Set()
      body.data.quotes.items.forEach(q => {
        if (q.image_results) {
          (Array.isArray(q.image_results) ? q.image_results : [q.image_results]).forEach(img => {
            const id = img.id || img.image_result_id
            if (id && !seen.has(id)) {
              seen.add(id)
              imageResults.value.push({
                id,
                recognized_space: img.recognized_space || img.space_name || '未识别',
                original_filename: img.original_filename || img.filename || ('图片#' + id),
                confidence: img.confidence || 0,
              })
            }
          })
        }
      })
    }
  } catch(e) {}
}

async function loadSpaces() {
  if (!selectedCadId.value) return
  spacesLoading.value = true
  try {
    // 先尝试获取分层明细
    const res = await API.getBreakdown(parseInt(selectedCadId.value))
    if (res.success && res.data?.spaces) {
      spaces.value = res.data.spaces.map(s => ({
        id: s.id || s.space_id,
        name: s.space_name || ('未命名#' + (s.id || 0)),
        area: s.area || 0,
      }))
    } else {
      // 回退：从CAD结果JSON提取
      const cad = cadResults.value.find(r => r.id === selectedCadId.value)
      const raw = cad?.detail_json?.spaces || cad?.spaces || []
      spaces.value = raw.map((s, i) => ({
        id: s.id || i,
        name: s.name || s.space_name || ('未命名#' + (s.id || i)),
        area: s.area || s.area_sqm || 0,
      }))
    }
  } catch (e) {
    spaces.value = []
  }
  spacesLoading.value = false
}

onMounted(loadResults)

// 当选中的CAD变更时加载空间列表 并刷新效果图列表
watch(selectedCadId, async (newId) => {
  if (newId) {
    await loadSpaces()
    await loadImageResults()
  } else {
    spaces.value = []
  }
})

// 当选择变更时自动触发匹配建议
watch([selectedCadId, selectedImageIds], async ([newCadId, newImgIds]) => {
  if (newCadId && newImgIds && newImgIds.length > 0) {
    await loadSuggestions()
  } else {
    suggestionMatches.value = []
    confirmedMatches.value = {}
  }
})

// 🌟 当 App 中分析完成时自动重新加载
watch(refreshKey, async () => {
  await loadResults()
})

async function loadSuggestions() {
  loadingSuggestions.value = true
  suggestionMatches.value = []
  confirmedMatches.value = {}
  const res = await API.autoSuggestMatch(selectedCadId.value, selectedImageIds.value)
  if (res.success && res.data?.matches) {
    suggestionMatches.value = res.data.matches
  }
  loadingSuggestions.value = false
}

async function confirmMatch(imageId, cadId) {
  const key = imageId + '-' + cadId
  confirmingMatch.value[key] = true
  const res = await API.autoConfirmMatch(cadId, imageId)
  if (res.success) {
    confirmedMatches.value[key] = true
  }
  confirmingMatch.value[key] = false
}

async function doMerge() {
  merging.value = true
  mergeError.value = ''
  mergeResult.value = null
  const bindingsJson = bindings.value
    .filter(b => b.cad_space_name && b.material_desc)
    .map(b => ({ space_name: b.cad_space_name, material: b.material_desc }))
  const res = await API.dataMerge(selectedCadId.value, selectedImageIds.value, bindingsJson)
  if (res.success) {
    mergeResult.value = res
    emit('quote-exists', res.data?.quote_id)
  } else {
    mergeError.value = res.message || '融合失败'
  }
  merging.value = false
}

function handleExport(quoteId) {
  emit('quote-exists', quoteId)
}
</script>
