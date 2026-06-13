<template>
  <div class="card" v-if="data">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
        <span>💰</span> {{ title }}
      </h3>
      <button v-if="data.data?.quote_id" class="btn-primary text-sm !px-4 !py-2" :disabled="exporting" @click="doExport">
        <svg v-if="exporting" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        {{ exporting ? '导出中...' : '📥 导出Excel' }}
      </button>
    </div>

    <div v-if="!data.success" class="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
      {{ data.message }}
    </div>

    <template v-if="data.success">
      <!-- 报价汇总 -->
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <div class="bg-gray-50 rounded-xl p-3 text-center">
          <p class="text-xs text-gray-500">总面积</p>
          <p class="text-lg font-bold text-gray-800">{{ formatNum(data.data?.total_area || quoteData?.total_area) }} ㎡</p>
        </div>
        <div class="bg-blue-50 rounded-xl p-3 text-center">
          <p class="text-xs text-blue-600">基础报价</p>
          <p class="text-lg font-bold text-blue-700">¥{{ formatPrice(data.data?.base_price || quoteData?.base_price) }}</p>
        </div>
        <div class="bg-green-50 rounded-xl p-3 text-center">
          <p class="text-xs text-green-600">材质差价</p>
          <p class="text-lg font-bold text-green-700">+¥{{ formatPrice(data.data?.material_diff || quoteData?.material_diff) }}</p>
        </div>
        <div class="bg-orange-50 rounded-xl p-3 text-center">
          <p class="text-xs text-orange-600">损耗</p>
          <p class="text-lg font-bold text-orange-700">+¥{{ formatPrice(data.data?.loss_price || quoteData?.loss_price) }}</p>
        </div>
        <div class="bg-purple-50 rounded-xl p-3 text-center">
          <p class="text-xs text-purple-600">管理费</p>
          <p class="text-lg font-bold text-purple-700">+¥{{ formatPrice(data.data?.manage_fee || quoteData?.manage_fee) }}</p>
        </div>
        <div class="bg-yellow-50 rounded-xl p-3 text-center">
          <p class="text-xs text-yellow-600">税费</p>
          <p class="text-lg font-bold text-yellow-700">+¥{{ formatPrice(data.data?.tax_fee || quoteData?.tax_fee) }}</p>
        </div>
      </div>

      <!-- 最终报价 -->
      <div class="p-4 bg-gradient-to-r from-primary-50 to-blue-50 rounded-xl border border-primary-200 mb-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-primary-600 mb-1">最终报价</p>
            <p class="text-2xl font-bold text-primary-800">¥{{ formatPrice(data.data?.final_price || quoteData?.final_price) }}</p>
          </div>
          <span class="text-3xl">🏷️</span>
        </div>
      </div>

      <!-- 分项明细 -->
      <div class="overflow-x-auto" v-if="(data.data?.items || quoteData?.items || []).length > 0">
        <h4 class="text-sm font-medium text-gray-700 mb-2">分项明细</h4>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-2 px-3 text-gray-600 font-medium">空间</th>
              <th class="text-left py-2 px-3 text-gray-600 font-medium">类别</th>
              <th class="text-left py-2 px-3 text-gray-600 font-medium">项目</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">数量</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">单价</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">小计</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, i) in (data.data?.items || quoteData?.items || [])" :key="i"
                class="border-b border-gray-100 hover:bg-gray-50">
              <td class="py-2 px-3 text-gray-800">{{ item.space_name || '-' }}</td>
              <td class="py-2 px-3 text-gray-600">{{ item.category || '-' }}</td>
              <td class="py-2 px-3 text-gray-600">{{ item.project_name || '-' }}</td>
              <td class="py-2 px-3 text-right text-gray-700">{{ formatNum(item.quantity) }}</td>
              <td class="py-2 px-3 text-right text-gray-700">¥{{ formatPrice(item.material_unit_price) }}</td>
              <td class="py-2 px-3 text-right text-gray-700">¥{{ formatPrice(item.subtotal || (item.quantity * item.material_unit_price)) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 导出状态 -->
      <div v-if="exportResult" class="mt-4 p-3 rounded-xl text-sm"
        :class="exportResult.success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'">
        {{ exportResult.message }}
        <span v-if="exportResult.data?.file_path" class="block text-xs mt-1 text-green-500">
          路径: {{ exportResult.data.file_path }}
        </span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import API from '../services/api.js'

const props = defineProps({
  data: Object,
  title: { type: String, default: '融合报价' },
})

const exporting = ref(false)
const exportResult = ref(null)

// 兼容从详细历史传入的quote数据
const quoteData = props.data?.data?.quote_detail_json || props.data?.data

function formatNum(v) { return v ? Number(v).toFixed(2) : '-' }
function formatPrice(v) { return v ? Number(v).toLocaleString() : '0' }

async function doExport() {
  exporting.value = true
  exportResult.value = null
  const quoteId = props.data?.data?.quote_id
  if (!quoteId) { exportResult.value = { success: false, message: '缺少报价ID' }; exporting.value = false; return }
  const res = await API.exportExcel(quoteId)
  exportResult.value = res
  exporting.value = false
}
</script>
