<template>
  <div>
    <!-- 工序→空间对照表 -->
    <div v-if="loading" class="card text-center text-gray-400 py-8">加载中...</div>

    <template v-else>
      <!-- 已关联报价的工序汇总 -->
      <div v-if="summary.length > 0" class="card mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <span>📊</span> 工序×空间 工程量汇总
        </h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200">
                <th class="text-left py-2 px-3 text-gray-600 font-medium">工序</th>
                <th class="text-center py-2 px-3 text-gray-600 font-medium">排序</th>
                <th class="text-center py-2 px-3 text-gray-600 font-medium">工期(天)</th>
                <th class="text-center py-2 px-3 text-gray-600 font-medium">涉及空间数</th>
                <th class="text-left py-2 px-3 text-gray-600 font-medium">施工区域</th>
                <th class="text-right py-2 px-3 text-gray-600 font-medium">工程量</th>
                <th class="text-right py-2 px-3 text-gray-600 font-medium">报价(元)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in summary" :key="p.process_id"
                  class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td class="py-2.5 px-3">
                  <div class="flex items-center gap-2">
                    <span class="w-3 h-3 rounded-full inline-block flex-shrink-0" :style="{background: p.color}"></span>
                    <span class="font-medium text-gray-800">{{ p.process_name }}</span>
                  </div>
                </td>
                <td class="py-2.5 px-3 text-center text-gray-500 text-xs">{{ p.sort_order }}</td>
                <td class="py-2.5 px-3 text-center text-gray-700">{{ p.standard_days }}</td>
                <td class="py-2.5 px-3 text-center">
                  <span class="px-2 py-0.5 bg-primary-50 text-primary-700 rounded-full text-xs font-medium">
                    {{ p.space_count }} 个
                  </span>
                </td>
                <td class="py-2.5 px-3 max-w-xs">
                  <div class="flex flex-wrap gap-1">
                    <span v-for="s in p.spaces" :key="s"
                          class="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-[10px]">
                      {{ s }}
                    </span>
                  </div>
                </td>
                <td class="py-2.5 px-3 text-right text-gray-700">{{ formatQty(p.total_quantity) }}</td>
                <td class="py-2.5 px-3 text-right font-medium text-primary-700">
                  ¥{{ formatPrice(p.total_amount) }}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t-2 border-gray-200 bg-gray-50">
                <td class="py-3 px-3 font-semibold text-gray-700" colspan="4">合计</td>
                <td class="py-3 px-3"></td>
                <td class="py-3 px-3"></td>
                <td class="py-3 px-3 text-right font-bold text-primary-800 text-base">
                  ¥{{ formatPrice(totalQuote) }}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- 无报价时的工序预设区域 -->
      <div v-if="summary.length === 0" class="card mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <span>🏗️</span> 工序预设施工区域
        </h3>
        <p class="text-xs text-gray-400 mb-4">工序的默认适用空间（可在工序管理页编辑），执行融合报价后自动关联实际工程量</p>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200">
                <th class="text-left py-2 px-3 text-gray-600 font-medium">#</th>
                <th class="text-left py-2 px-3 text-gray-600 font-medium">工序</th>
                <th class="text-left py-2 px-3 text-gray-600 font-medium">工种</th>
                <th class="text-center py-2 px-3 text-gray-600 font-medium">工期</th>
                <th class="text-left py-2 px-3 text-gray-600 font-medium">预设施工区域</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in processes" :key="p.id"
                  class="border-b border-gray-100 hover:bg-gray-50">
                <td class="py-2 px-3 text-gray-400 text-xs">{{ p.sort_order }}</td>
                <td class="py-2 px-3">
                  <div class="flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full inline-block" :style="{background: p.color}"></span>
                    <span class="font-medium text-gray-800">{{ p.name }}</span>
                  </div>
                </td>
                <td class="py-2 px-3 text-gray-600 text-xs">{{ workTypeLabel(p.work_type) }}</td>
                <td class="py-2 px-3 text-center text-gray-700">{{ p.standard_days }}天</td>
                <td class="py-2 px-3">
                  <div v-if="p.applicable_spaces" class="flex flex-wrap gap-1">
                    <span v-for="s in p.applicable_spaces.split(',')" :key="s"
                          class="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-[10px]">
                      {{ s.trim() }}
                    </span>
                  </div>
                  <span v-else class="text-xs text-gray-400">全屋</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const processes = ref([])
const summary = ref([])
const totalQuote = ref(0)
const loading = ref(true)

function workTypeLabel(wt) {
  const labels = {
    demolition: '拆除', plumbing_electric: '水电', waterproofing: '防水',
    tiling: '瓦工', woodwork: '木工', painting: '油漆',
    installation: '安装', cleaning: '保洁', inspection: '验收',
    furnishing: '软装', finishing: '收尾', other: '其他',
  }
  return labels[wt] || wt
}

function formatQty(v) { return v ? Number(v).toFixed(1) : '-' }
function formatPrice(v) { return v ? Number(v).toLocaleString() : '0' }

function get(path) {
  return fetch(path).then(r => r.json())
}

onMounted(async () => {
  try {
    // 加载工序
    const r1 = await get('/api/processes')
    if (r1.success) processes.value = r1.data.processes

    // 加载工序报价汇总
    const r2 = await get('/api/processes/quotes/summary')
    if (r2.success) {
      summary.value = r2.data.process_summary || []
      totalQuote.value = r2.data.total_quote || 0
    }
  } catch (e) {}
  loading.value = false
})
</script>
