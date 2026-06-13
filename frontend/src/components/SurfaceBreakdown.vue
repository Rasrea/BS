<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="card">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="text-lg font-bold text-gray-900">📐 分层工程量明细</h2>
          <p class="text-xs text-gray-500">每个空间的墙面/地面/顶面独立工程量 + 材质关联</p>
        </div>
        <div class="flex items-center gap-2">
          <select v-model="selectedDrawingId"
                  class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white"
                  @change="onDrawingChange">
            <option value="">-- 选择图纸 --</option>
            <option v-for="d in drawings" :key="d.id" :value="d.id">
              #{{ d.id }} - {{ d.filename }}
            </option>
          </select>
          <button class="btn-primary text-xs" :disabled="!selectedDrawingId || loading"
                  @click="computeAndFetch">
            {{ loading ? '计算中...' : '🔄 计算分层数据' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card text-center py-8">
      <svg class="animate-spin w-8 h-8 mx-auto text-primary-500" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <p class="text-sm text-gray-500 mt-2">计算分层工程量中...</p>
    </div>

    <!-- 汇总统计 -->
    <div v-if="summary" class="card bg-gradient-to-r from-blue-50 to-indigo-50">
      <h3 class="text-sm font-semibold text-gray-700 mb-2">📊 汇总统计</h3>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div class="stat-box">
          <span class="stat-label">空间数</span>
          <span class="stat-value">{{ summary.space_count || summary.total_spaces || 0 }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">地面面积</span>
          <span class="stat-value">{{ summary.total_floor_area }} ㎡</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">墙面净面积</span>
          <span class="stat-value">{{ summary.total_wall_net_area }} ㎡</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">顶面面积</span>
          <span class="stat-value">{{ summary.total_ceiling_area }} ㎡</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">材质匹配</span>
          <span class="stat-value" :class="summary.matched_spaces > 0 ? 'text-green-600' : 'text-yellow-600'">
            {{ summary.matched_spaces }}/{{ (summary.matched_spaces || 0) + (summary.unmatched_spaces || 0) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 无数据提示 -->
    <div v-if="!loading && !error && !spaces.length && selectedDrawingId" class="card text-center py-8 text-gray-400">
      <p class="text-3xl mb-2">📋</p>
      <p class="text-sm">请点击「计算分层数据」生成该图纸的分层工程量</p>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="card bg-red-50 border border-red-200">
      <p class="text-sm text-red-600">{{ error }}</p>
    </div>

    <!-- 空间明细表 -->
    <div v-if="spaces.length > 0" class="space-y-3">
      <!-- 搜索过滤 -->
      <div class="flex items-center gap-3 flex-wrap">
        <input v-model="searchQuery" placeholder="🔍 搜索空间名称..."
               class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm flex-1 max-w-xs" />
        <select v-model="filterMatched" class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white">
          <option value="all">全部空间</option>
          <option value="matched">已匹配材质</option>
          <option value="unmatched">未匹配材质</option>
        </select>
        <span class="text-xs text-gray-400 ml-auto">{{ filteredSpaces.length }} / {{ spaces.length }} 个空间</span>
      </div>

      <!-- 表格 -->
      <div class="overflow-x-auto rounded-xl border border-gray-200">
      <table class="min-w-full divide-y divide-gray-200 text-sm">
      <thead class="bg-gray-50">
      <tr>
        <th class="px-4 py-2.5 text-left font-semibold text-gray-600 text-xs">空间名称</th>
        <th class="px-4 py-2.5 text-right font-semibold text-gray-600 text-xs">面积(㎡)</th>
        <!-- 地面 -->
        <th class="px-3 py-2.5 text-right font-semibold text-green-700 text-xs bg-green-50">地面(㎡)</th>
        <th class="px-3 py-2.5 text-left font-semibold text-green-700 text-xs bg-green-50">地面材质</th>
        <!-- 墙面 -->
        <th class="px-3 py-2.5 text-right font-semibold text-blue-700 text-xs bg-blue-50">墙面毛(㎡)</th>
        <th class="px-3 py-2.5 text-right font-semibold text-blue-700 text-xs bg-blue-50">墙面净(㎡)</th>
        <th class="px-3 py-2.5 text-left font-semibold text-blue-700 text-xs bg-blue-50">墙面材质</th>
        <!-- 顶面 -->
        <th class="px-3 py-2.5 text-right font-semibold text-purple-700 text-xs bg-purple-50">顶面(㎡)</th>
        <th class="px-3 py-2.5 text-left font-semibold text-purple-700 text-xs bg-purple-50">顶面材质</th>
        <!-- 操作 -->
        <th class="px-2 py-2.5 text-center font-semibold text-gray-600 text-xs">操作</th>
      </tr>
      </thead>
      <tbody class="divide-y divide-gray-100 bg-white">
      <tr v-for="s in paginatedSpaces" :key="s.id"
                class="hover:bg-gray-50/50 transition-colors"
                :class="{ 'bg-yellow-50/30': !s.material_source && !hasManualMat(s) }">
              <td class="px-4 py-2 font-medium text-gray-800 whitespace-nowrap">
                {{ s.space_name }}
                <span v-if="!s.material_source && !hasManualMat(s)"
                      class="ml-1.5 text-[10px] text-yellow-600 bg-yellow-100 px-1.5 py-0.5 rounded-full">未匹配</span>
                <span v-else-if="s.material_source"
                      class="ml-1.5 text-[10px] text-green-600 bg-green-100 px-1.5 py-0.5 rounded-full">AI</span>
                <span v-else
                      class="ml-1.5 text-[10px] text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded-full">手动</span>
              </td>
              <td class="px-4 py-2 text-right text-gray-600">{{ s.area.toFixed(1) }}</td>
              <!-- 地面 -->
              <td class="px-3 py-2 text-right text-green-700 font-medium bg-green-50/50">
                {{ getSurface(s, 'floor', 'area') }}
              </td>
              <td class="px-3 py-2 text-left text-green-700 text-xs bg-green-50/50 truncate max-w-[100px]"
                  :title="getSurfaceMat(s, 'floor')">
                {{ getSurfaceMat(s, 'floor') || '—' }}
              </td>
              <!-- 墙面 -->
              <td class="px-3 py-2 text-right text-blue-700 bg-blue-50/50">
                {{ getSurface(s, 'wall', 'area') }}
              </td>
              <td class="px-3 py-2 text-right text-blue-700 font-medium bg-blue-50/50">
                {{ getSurface(s, 'wall', 'net_area') }}
              </td>
              <td class="px-3 py-2 text-left text-blue-700 text-xs bg-blue-50/50 truncate max-w-[100px]"
                  :title="getSurfaceMat(s, 'wall')">
                {{ getSurfaceMat(s, 'wall') || '—' }}
              </td>
              <!-- 顶面 -->
              <td class="px-3 py-2 text-right text-purple-700 font-medium bg-purple-50/50">
                {{ getSurface(s, 'ceiling', 'area') }}
              </td>
              <td class="px-3 py-2 text-left text-purple-700 text-xs bg-purple-50/50 truncate max-w-[100px]"
                  :title="getSurfaceMat(s, 'ceiling')">
                {{ getSurfaceMat(s, 'ceiling') || '—' }}
              </td>
              <!-- 操作按钮 -->
              <td class="px-2 py-2 text-center">
                <button class="text-[10px] text-primary-600 hover:text-primary-800"
                        @click="showBindDialog(s)">
                  ✏️ 绑定
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="flex items-center justify-between text-xs text-gray-500">
        <span>共 {{ spaces.length }} 个空间</span>
        <div class="flex gap-2">
          <button class="px-2 py-1 rounded border hover:bg-gray-50"
                  :disabled="page <= 1" @click="page--">上一页</button>
          <span class="px-2 py-1">第 {{ page }} / {{ totalPages }} 页</span>
          <button class="px-2 py-1 rounded border hover:bg-gray-50"
                  :disabled="page >= totalPages" @click="page++">下一页</button>
        </div>
      </div>
    </div>

    <!-- 材质绑定对话框 -->
    <div v-if="bindDialog.show"
         class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
         @click.self="bindDialog.show = false">
      <div class="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
        <h3 class="text-sm font-bold text-gray-900 mb-3">绑定材质</h3>
        <p class="text-xs text-gray-500 mb-3">
          {{ bindDialog.spaceName }} → <span class="font-medium">{{ surfaceLabel(bindDialog.surface) }}</span>
        </p>

        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-500 block mb-1">材质名称</label>
            <input v-model="bindDialog.materialName" placeholder="例如: 乳胶漆、木地板、石膏板..."
                   class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">材质编码（可选）</label>
            <input v-model="bindDialog.materialCode" placeholder="例如: FL001"
                   class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          </div>

          <!-- 快速选择 -->
          <div>
            <label class="text-xs text-gray-500 block mb-1">快速选择</label>
            <div class="flex flex-wrap gap-1.5">
              <button v-for="opt in quickMaterials" :key="opt.name"
                      class="text-[10px] px-2 py-1 rounded-full border"
                      :class="bindDialog.materialName === opt.name
                        ? 'bg-primary-100 border-primary-300 text-primary-700'
                        : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
                      @click="bindDialog.materialName = opt.name">
                {{ opt.name }}
              </button>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-5">
          <button class="btn-secondary text-sm" @click="bindDialog.show = false">取消</button>
          <button class="btn-primary text-sm" :disabled="!bindDialog.materialName"
                  @click="doBindMaterial">
            ✅ 确认绑定
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import API from '../services/api.js'

const selectedDrawingId = ref('')
const drawings = ref([])
const spaces = ref([])
const summary = ref(null)
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')
const filterMatched = ref('all')
const page = ref(1)
const pageSize = 20

const quickMaterials = [
  { name: '乳胶漆' }, { name: '墙布/壁纸' }, { name: '瓷砖' },
  { name: '木地板' }, { name: '大理石' }, { name: '石膏板吊顶' },
  { name: '铝扣板吊顶' }, { name: '木饰面' },
]

const bindDialog = ref({
  show: false,
  cadId: null,
  spaceName: '',
  surface: 'floor',
  materialName: '',
  materialCode: '',
})

const filteredSpaces = computed(() => {
  let list = spaces.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(s => s.space_name.toLowerCase().includes(q))
  }
  if (filterMatched.value === 'matched') {
    list = list.filter(s => s.material_source || hasManualMat(s))
  } else if (filterMatched.value === 'unmatched') {
    list = list.filter(s => !s.material_source && !hasManualMat(s))
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredSpaces.value.length / pageSize)))

const paginatedSpaces = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredSpaces.value.slice(start, start + pageSize)
})

// 实际上我们用 filteredSpaces 直接在表格显示，加上分页控制

onMounted(async () => {
  await loadDrawings()
})

async function loadDrawings() {
  const res = await API.get('/drawings')
  if (res.success && Array.isArray(res.data)) {
    drawings.value = res.data
  }
}

function onDrawingChange() {
  spaces.value = []
  summary.value = null
  error.value = ''
  page.value = 1
}

async function computeAndFetch() {
  if (!selectedDrawingId.value) return
  loading.value = true
  error.value = ''

  // Step 1: 计算分层
  const computeRes = await API.computeBreakdown(parseInt(selectedDrawingId.value))
  if (!computeRes.success) {
    error.value = computeRes.message || '分层计算失败'
    loading.value = false
    return
  }

  // Step 2: 获取结果
  await fetchBreakdown()
}

async function fetchBreakdown() {
  if (!selectedDrawingId.value) return
  loading.value = true
  error.value = ''

  const res = await API.getBreakdown(parseInt(selectedDrawingId.value))
  if (res.success && res.data) {
    spaces.value = res.data.spaces || []
    summary.value = { ...res.data.summary, space_count: res.data.space_count }
  } else {
    error.value = res.message || '获取分层数据失败'
  }

  loading.value = false
}

function getSurface(space, surface, field) {
  const s = space.surface_breakdown?.surfaces?.[surface]
  if (!s) return '—'
  const v = s[field]
  return v !== undefined && v !== null ? v.toFixed(1) : '—'
}

function getSurfaceMat(space, surface) {
  // 优先取手动绑定的材质
  const detail = space.surface_breakdown?.surfaces?.[surface]
  if (detail?.material) return detail.material
  return ''
}

function hasManualMat(space) {
  return false
}

function surfaceLabel(surface) {
  const map = { floor: '地面', wall: '墙面', ceiling: '顶面' }
  return map[surface] || surface
}

function showBindDialog(space) {
  bindDialog.value = {
    show: true,
    cadId: space.id,
    spaceName: space.space_name,
    surface: 'floor',
    materialName: '',
    materialCode: '',
  }
}

async function doBindMaterial() {
  const bd = bindDialog.value
  if (!bd.cadId || !bd.materialName) return

  const res = await API.bindSurfaceMaterial(bd.cadId, bd.surface, bd.materialName, bd.materialCode)
  if (res.success) {
    bindDialog.value.show = false
    // 刷新数据
    await fetchBreakdown()
  } else {
    error.value = res.message || '绑定失败'
  }
}
</script>

<style scoped>
.card {
  @apply bg-white rounded-xl border border-gray-200 p-4 shadow-sm;
}
.btn-primary {
  @apply bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium
         hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors;
}
.btn-secondary {
  @apply bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium
         hover:bg-gray-200 transition-colors;
}
.stat-box {
  @apply bg-white/70 rounded-lg px-3 py-2 flex flex-col;
}
.stat-label {
  @apply text-[10px] text-gray-500 uppercase tracking-wide;
}
.stat-value {
  @apply text-lg font-bold text-gray-800;
}
</style>
