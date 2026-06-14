<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="card">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-gray-900">📋 双源数据核对表</h2>
          <p class="text-xs text-gray-500">CAD物理空间 ↔ AI图像识别 逐项比对，异常自动标红</p>
        </div>
        <div class="flex items-center gap-3">
          <select v-model="selectedDrawingId" class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white"
                  @change="loadComparison">
            <option value="">-- 选择图纸 --</option>
            <option v-for="d in drawings" :key="d.id" :value="d.id">
              #{{ d.id }} - {{ d.filename }}
            </option>
          </select>
          <button class="btn-primary text-xs" :disabled="!selectedDrawingId || loading"
                  @click="loadComparison">
            {{ loading ? '加载中...' : '🔄 加载核对数据' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 统计摘要 -->
    <div v-if="stats" class="grid grid-cols-4 gap-3">
      <div class="card bg-gray-50 text-center">
        <p class="text-2xl font-bold text-gray-800">{{ stats.total_spaces }}</p>
        <p class="text-xs text-gray-500">总空间</p>
      </div>
      <div class="card bg-green-50 text-center">
        <p class="text-2xl font-bold text-green-700">{{ stats.normal_count }}</p>
        <p class="text-xs text-green-600">正常</p>
      </div>
      <div class="card bg-red-50 text-center">
        <p class="text-2xl font-bold text-red-700">{{ stats.anomaly_count }}</p>
        <p class="text-xs text-red-600">异常</p>
      </div>
      <div class="card bg-blue-50 text-center">
        <p class="text-2xl font-bold text-blue-700">{{ anomalyRate }}%</p>
        <p class="text-xs text-blue-600">异常率</p>
      </div>
    </div>

    <!-- 筛选器 -->
    <div v-if="rows.length > 0" class="flex items-center gap-3">
      <div class="flex gap-1">
        <button v-for="f in filters" :key="f.key" @click="activeFilter=f.key"
                class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
                :class="activeFilter===f.key ? f.activeClass : 'bg-gray-100 text-gray-500 hover:bg-gray-200'">
          {{ f.label }}
        </button>
      </div>
      <input v-model="searchQuery" placeholder="🔍 搜索空间名..." class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm flex-1 max-w-xs" />
      <span class="text-xs text-gray-400 ml-auto">{{ filteredRows.length }} / {{ rows.length }}</span>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card text-center py-8">
      <svg class="animate-spin w-8 h-8 mx-auto text-primary-500" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <p class="text-sm text-gray-500 mt-2">加载核对数据中...</p>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && !rows.length && selectedDrawingId" class="card text-center py-8 text-gray-400">
      <p class="text-3xl mb-2">📋</p>
      <p>请点击「加载核对数据」</p>
    </div>

    <!-- 核对表 -->
    <div v-if="filteredRows.length > 0" class="overflow-x-auto rounded-xl border border-gray-200">
      <table class="min-w-full divide-y divide-gray-200 text-sm">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-3 py-2.5 text-left font-semibold text-gray-600 text-xs">#</th>
            <th class="px-3 py-2.5 text-left font-semibold text-gray-600 text-xs">空间名称</th>
            <th class="px-3 py-2.5 text-right font-semibold text-gray-600 text-xs">面积(㎡)</th>
            <th class="px-3 py-2.5 text-left font-semibold text-green-700 text-xs bg-green-50">墙面材质(AI)</th>
            <th class="px-3 py-2.5 text-left font-semibold text-green-700 text-xs bg-green-50">地面材质(AI)</th>
            <th class="px-3 py-2.5 text-left font-semibold text-green-700 text-xs bg-green-50">顶面材质(AI)</th>
            <th class="px-3 py-2.5 text-center font-semibold text-xs" :class="statusHeaderClass">状态</th>
            <th class="px-3 py-2.5 text-left font-semibold text-gray-600 text-xs">异常原因</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 bg-white">
          <tr v-for="(s, i) in paginatedRows" :key="s.space_id"
              class="hover:bg-gray-50/50 transition-colors"
              :class="{ 'bg-red-50/30': s.status === '异常', 'bg-green-50/30': s.status === '正常' }">
            <td class="px-3 py-2 text-xs text-gray-400">{{ (page-1)*pageSize + i + 1 }}</td>
            <td class="px-3 py-2 font-medium text-gray-800 whitespace-nowrap">
              {{ s.space_name }}
              <button v-if="s.space_name.startsWith('未命名')"
                      class="ml-1 text-[10px] text-primary-600 hover:text-primary-800"
                      @click="$emit('rename-space', s.space_id, s.space_name)">
                ✏️
              </button>
            </td>
            <td class="px-3 py-2 text-right" :class="s.area_sqm <= 0 ? 'text-red-600 font-medium' : 'text-gray-700'">
              {{ s.area_sqm > 0 ? s.area_sqm.toFixed(1) : '⚠ 0' }}
            </td>
            <td class="px-3 py-2 text-xs bg-green-50/50"
                :class="s.wall_material ? 'text-green-700' : 'text-red-500 italic'">
              {{ s.wall_material || '未识别' }}
            </td>
            <td class="px-3 py-2 text-xs bg-green-50/50"
                :class="s.floor_material ? 'text-green-700' : 'text-red-500 italic'">
              {{ s.floor_material || '未识别' }}
            </td>
            <td class="px-3 py-2 text-xs bg-green-50/50"
                :class="s.ceiling_material ? 'text-green-700' : 'text-red-500 italic'">
              {{ s.ceiling_material || '未识别' }}
            </td>
            <td class="px-3 py-2 text-center">
              <span class="text-xs px-2 py-0.5 rounded-full font-medium"
                    :class="s.status === '正常' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
                {{ s.status }}
              </span>
            </td>
            <td class="px-3 py-2 text-xs text-red-600 max-w-[200px] truncate" :title="s.anomalies.join('; ')">
              {{ s.anomalies.length > 0 ? s.anomalies.join('; ') : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex items-center justify-between text-xs text-gray-500">
      <span>共 {{ filteredRows.length }} 条</span>
      <div class="flex gap-2">
        <button class="px-2 py-1 rounded border hover:bg-gray-50" :disabled="page<=1" @click="page--">上一页</button>
        <span class="px-2 py-1">第 {{ page }} / {{ totalPages }} 页</span>
        <button class="px-2 py-1 rounded border hover:bg-gray-50" :disabled="page>=totalPages" @click="page++">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import API from '../services/api.js'

const emit = defineEmits(['rename-space'])

const drawings = ref([])
const selectedDrawingId = ref('')
const loading = ref(false)
const rows = ref([])
const stats = ref(null)
const activeFilter = ref('all')
const searchQuery = ref('')
const page = ref(1)
const pageSize = 20

const filters = [
  { key: 'all', label: '全部', activeClass: 'bg-gray-800 text-white' },
  { key: 'normal', label: '✅ 正常', activeClass: 'bg-green-600 text-white' },
  { key: 'anomaly', label: '⚠️ 异常', activeClass: 'bg-red-600 text-white' },
]

const anomalyRate = computed(() => {
  if (!stats.value || stats.value.total_spaces === 0) return 0
  return ((stats.value.anomaly_count / stats.value.total_spaces) * 100).toFixed(1)
})

const statusHeaderClass = computed(() => {
  return stats.value?.anomaly_count > 0 ? 'text-red-700 bg-red-50' : 'text-green-700 bg-green-50'
})

const filteredRows = computed(() => {
  let list = rows.value
  if (activeFilter.value === 'normal') {
    list = list.filter(r => r.status === '正常')
  } else if (activeFilter.value === 'anomaly') {
    list = list.filter(r => r.status === '异常')
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r => r.space_name.toLowerCase().includes(q))
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize)))

const paginatedRows = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredRows.value.slice(start, start + pageSize)
})

onMounted(async () => {
  const res = await API.get('/drawings')
  if (res.success && Array.isArray(res.data)) {
    drawings.value = res.data
  }
})

async function loadComparison() {
  if (!selectedDrawingId.value) return
  loading.value = true
  page.value = 1
  const res = await API.get(`/spaces/${selectedDrawingId.value}/comparison`)
  if (res.success && res.data) {
    rows.value = res.data.rows || []
    stats.value = {
      total_spaces: res.data.total_spaces,
      normal_count: res.data.normal_count,
      anomaly_count: res.data.anomaly_count,
    }
  } else {
    rows.value = []
    stats.value = null
  }
  loading.value = false
}
</script>
