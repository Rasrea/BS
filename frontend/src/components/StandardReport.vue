<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="card">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-gray-900">📊 标准报价表</h2>
          <p class="text-xs text-gray-500">综合汇总 · 空间分项 · 工序明细 三表合一</p>
        </div>
        <div class="flex items-center gap-3">
          <select v-model="selectedQuoteId" class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white">
            <option value="">-- 选择报价 --</option>
            <option v-for="q in quotes" :key="q.id" :value="q.id">
              #{{ q.id }} {{ q.project_name }} — ¥{{ Number(q.final_price || 0).toLocaleString() }}
            </option>
          </select>
          <button class="btn-primary text-xs" :disabled="!selectedQuoteId || loading"
                  @click="loadReport">
            {{ loading ? '加载中...' : '🔄 加载报表' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 视图切换 -->
    <div v-if="report" class="flex gap-1 mb-2">
      <button v-for="tab in viewTabs" :key="tab.key" @click="activeView=tab.key"
              class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
              :class="activeView===tab.key ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'">
        {{ tab.label }}
      </button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card text-center py-8">
      <svg class="animate-spin w-8 h-8 mx-auto text-primary-500" viewBox="0 0 24 24">...</svg>
      <p class="text-sm text-gray-500 mt-2">加载报表中...</p>
    </div>

    <!-- ========== 视图1：综合报价总表 ========== -->
    <div v-if="report && activeView === 'summary'">
      <!-- 项目概况 -->
      <div class="card bg-gradient-to-r from-blue-50 to-indigo-50">
        <h3 class="text-sm font-semibold text-gray-700 mb-3">📋 项目概况</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="stat-box"><span class="stat-label">项目名称</span><span class="stat-value text-sm">{{ report.project_name }}</span></div>
          <div class="stat-box"><span class="stat-label">报价编号</span><span class="stat-value text-sm">#{{ report.quote_id }}</span></div>
          <div class="stat-box"><span class="stat-label">生成时间</span><span class="stat-value text-sm">{{ report.create_time }}</span></div>
          <div class="stat-box"><span class="stat-label">工种数</span><span class="stat-value text-sm">{{ report.process_summary?.length || 0 }}</span></div>
        </div>
      </div>

      <!-- 费用汇总 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="card bg-blue-50 text-center"><p class="text-xs text-blue-600">基础报价</p><p class="text-xl font-bold text-blue-700">¥{{ fmt(report.base_price) }}</p></div>
        <div class="card bg-green-50 text-center"><p class="text-xs text-green-600">材质差价</p><p class="text-xl font-bold text-green-700">+¥{{ fmt(report.material_diff) }}</p></div>
        <div class="card bg-orange-50 text-center"><p class="text-xs text-orange-600">损耗</p><p class="text-xl font-bold text-orange-700">+¥{{ fmt(report.loss_price) }}</p></div>
        <div class="card bg-purple-50 text-center"><p class="text-xs text-purple-600">管理费</p><p class="text-xl font-bold text-purple-700">+¥{{ fmt(report.manage_fee) }}</p></div>
        <div class="card bg-yellow-50 text-center"><p class="text-xs text-yellow-600">税费</p><p class="text-xl font-bold text-yellow-700">+¥{{ fmt(report.tax_fee) }}</p></div>
        <div class="card col-span-2 bg-gradient-to-r from-primary-50 to-blue-50 text-center">
          <p class="text-xs text-primary-600">最终报价</p>
          <p class="text-2xl font-bold text-primary-800">¥{{ fmt(report.total_price) }}</p>
        </div>
      </div>

      <!-- 工种汇总 -->
      <div class="card">
        <h3 class="text-sm font-semibold text-gray-700 mb-3">🔧 工种费用汇总</h3>
        <table class="w-full text-sm">
          <thead><tr class="border-b border-gray-200">
            <th class="text-left py-2 text-gray-600 font-medium">工序</th>
            <th class="text-right py-2 text-gray-600 font-medium">空间数</th>
            <th class="text-right py-2 text-gray-600 font-medium">项目数</th>
            <th class="text-right py-2 text-gray-600 font-medium">金额(元)</th>
          </tr></thead>
          <tbody>
            <tr v-for="p in report.process_summary" :key="p.process_name" class="border-b border-gray-100">
              <td class="py-2 font-medium text-gray-800">{{ p.process_name }}</td>
              <td class="py-2 text-right text-gray-600">{{ p.space_count }}</td>
              <td class="py-2 text-right text-gray-600">{{ p.item_count }}</td>
              <td class="py-2 text-right font-medium text-gray-800">¥{{ fmt(p.subtotal) }}</td>
            </tr>
            <tr class="border-t-2 border-gray-300 bg-gray-50 font-bold">
              <td class="py-2 text-gray-800">合计</td>
              <td class="py-2 text-right text-gray-600">{{ totalSpaces }}</td>
              <td class="py-2 text-right text-gray-600">{{ totalItems }}</td>
              <td class="py-2 text-right text-primary-700">¥{{ fmt(report.total_price) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ========== 视图2：空间分项明细表 ========== -->
    <div v-if="report && activeView === 'space_detail'">
      <div class="space-y-3">
        <div v-for="sd in report.space_details" :key="sd.space_name" class="card">
          <div class="flex items-center justify-between mb-2">
            <h4 class="text-sm font-semibold text-gray-800">{{ sd.space_name }}</h4>
            <span class="text-sm font-bold text-primary-700">¥{{ fmt(sd.space_subtotal) }}</span>
          </div>
          <table class="w-full text-xs">
            <thead><tr class="border-b border-gray-200 text-gray-500">
              <th class="text-left py-1">项目</th>
              <th class="text-right py-1">数量</th>
              <th class="text-right py-1">材料单价</th>
              <th class="text-right py-1">人工单价</th>
              <th class="text-right py-1">小计(元)</th>
            </tr></thead>
            <tbody>
              <tr v-for="item in sd.items" :key="item.project_name" class="border-b border-gray-50">
                <td class="py-1 text-gray-700">{{ item.project_name }}</td>
                <td class="py-1 text-right text-gray-600">{{ item.quantity }} {{ item.unit }}</td>
                <td class="py-1 text-right text-gray-600">¥{{ fmt(item.material_unit_price) }}</td>
                <td class="py-1 text-right text-gray-600">¥{{ fmt(item.labor_unit_price) }}</td>
                <td class="py-1 text-right font-medium text-gray-800">¥{{ fmt(item.subtotal) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ========== 视图3：工序费用明细表 ========== -->
    <div v-if="report && activeView === 'process_detail'">
      <div class="overflow-x-auto rounded-xl border border-gray-200">
        <table class="min-w-full divide-y divide-gray-200 text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2.5 text-left font-semibold text-gray-600 text-xs">工序</th>
              <th class="px-3 py-2.5 text-left font-semibold text-gray-600 text-xs">涉及空间</th>
              <th class="px-3 py-2.5 text-right font-semibold text-gray-600 text-xs">空间数</th>
              <th class="px-3 py-2.5 text-right font-semibold text-blue-700 text-xs bg-blue-50">材料费</th>
              <th class="px-3 py-2.5 text-right font-semibold text-orange-700 text-xs bg-orange-50">人工费</th>
              <th class="px-3 py-2.5 text-right font-semibold text-green-700 text-xs bg-green-50">合计</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 bg-white">
            <tr v-for="p in report.process_details" :key="p.process_name" class="hover:bg-gray-50">
              <td class="px-3 py-2 font-medium text-gray-800">{{ p.process_name }}</td>
              <td class="px-3 py-2 text-xs text-gray-500 max-w-[200px] truncate" :title="p.spaces.join(', ')">
                {{ p.spaces.join(', ') || '-' }}
              </td>
              <td class="px-3 py-2 text-right text-gray-600">{{ p.space_count }}</td>
              <td class="px-3 py-2 text-right text-blue-700 bg-blue-50/50">¥{{ fmt(p.material_cost) }}</td>
              <td class="px-3 py-2 text-right text-orange-700 bg-orange-50/50">¥{{ fmt(p.labor_cost) }}</td>
              <td class="px-3 py-2 text-right font-medium text-green-700 bg-green-50/50">¥{{ fmt(p.subtotal) }}</td>
            </tr>
            <tr class="bg-gray-50 font-bold border-t-2 border-gray-300">
              <td class="px-3 py-2 text-gray-800" colspan="2">合计</td>
              <td class="px-3 py-2 text-right text-gray-600">{{ totalProcessSpaces }}</td>
              <td class="px-3 py-2 text-right text-blue-700">¥{{ fmt(totalMaterialCost) }}</td>
              <td class="px-3 py-2 text-right text-orange-700">¥{{ fmt(totalLaborCost) }}</td>
              <td class="px-3 py-2 text-right text-green-700">¥{{ fmt(report.total_price) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import API from '../services/api.js'

const quotes = ref([])
const selectedQuoteId = ref('')
const loading = ref(false)
const report = ref(null)
const activeView = ref('summary')

const viewTabs = [
  { key: 'summary', label: '📋 综合报价总表' },
  { key: 'space_detail', label: '🏠 空间分项明细' },
  { key: 'process_detail', label: '🔧 工序费用明细' },
]

function fmt(v) { return v ? Number(v).toLocaleString() : '0' }

const totalSpaces = computed(() => report.value?.space_details?.length || 0)
const totalItems = computed(() => report.value?.process_summary?.reduce((s, p) => s + p.item_count, 0) || 0)
const totalProcessSpaces = computed(() => {
  const set = new Set()
  report.value?.process_details?.forEach(p => p.spaces?.forEach(s => set.add(s)))
  return set.size
})
const totalMaterialCost = computed(() => report.value?.process_details?.reduce((s, p) => s + p.material_cost, 0) || 0)
const totalLaborCost = computed(() => report.value?.process_details?.reduce((s, p) => s + p.labor_cost, 0) || 0)

onMounted(async () => {
  const h = await API.getHistory(1, 50)
  if (h.success && h.data?.quotes?.items) {
    quotes.value = h.data.quotes.items
  }
})

async function loadReport() {
  if (!selectedQuoteId.value) return
  loading.value = true
  const res = await API.get(`/quote/${selectedQuoteId.value}/standard_report`)
  if (res.success && res.data) {
    report.value = res.data
  } else {
    report.value = null
    alert(res.message || '加载失败')
  }
  loading.value = false
}
</script>
