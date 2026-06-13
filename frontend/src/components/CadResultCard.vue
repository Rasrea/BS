<template>
  <div class="card mb-6" v-if="data">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
        <span>📐</span> CAD 解析结果
      </h3>
      <span class="px-2.5 py-1 text-xs font-medium rounded-full"
        :class="data.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
        {{ data.success ? '解析成功' : '解析失败' }}
      </span>
    </div>

    <!-- 错误显示 -->
    <div v-if="!data.success" class="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 mb-4">
      {{ data.message || data.error }}
    </div>

    <!-- 错误时无data.data，直接返回 -->
    <template v-if="!data.success || !data.data"> </template>

    <!-- 汇总卡片 -->
    <template v-else>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="bg-blue-50 rounded-xl p-3 text-center">
          <p class="text-xl font-bold text-blue-700">{{ data.data.space_count || data.data.spaces?.length || 0 }}</p>
          <p class="text-xs text-blue-600 mt-0.5">识别空间 (个)</p>
        </div>
        <div class="bg-green-50 rounded-xl p-3 text-center">
          <p class="text-xl font-bold text-green-700">{{ formatNum(data.data.total_area) }}</p>
          <p class="text-xs text-green-600 mt-0.5">总面积 (㎡)</p>
        </div>
        <div class="bg-orange-50 rounded-xl p-3 text-center">
          <p class="text-xl font-bold text-orange-700">¥{{ formatPrice(data.data.base_price) }}</p>
          <p class="text-xs text-orange-600 mt-0.5">基础价</p>
        </div>
        <div class="bg-purple-50 rounded-xl p-3 text-center">
          <p class="text-xl font-bold text-purple-700">¥{{ formatPrice(data.data.final_price) }}</p>
          <p class="text-xs text-purple-600 mt-0.5">最终报价</p>
        </div>
      </div>

      <!-- 空间清单表格 -->
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-2 px-3 font-medium text-gray-600">#</th>
              <th class="text-left py-2 px-3 font-medium text-gray-600">空间名称</th>
              <th class="text-right py-2 px-3 font-medium text-gray-600">面积 (㎡)</th>
              <th class="text-right py-2 px-3 font-medium text-gray-600">周长 (m)</th>
              <th class="text-right py-2 px-3 font-medium text-gray-600">宽度 (m)</th>
              <th class="text-right py-2 px-3 font-medium text-gray-600">高度 (m)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in data.data.spaces" :key="i"
                class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              <td class="py-2 px-3 text-gray-400 text-xs">{{ i + 1 }}</td>
              <td class="py-2 px-3 font-medium text-gray-800">{{ s.name || '未命名空间' }}</td>
              <td class="py-2 px-3 text-right text-gray-700">{{ formatNum(s.area || s.area_sqm) }}</td>
              <td class="py-2 px-3 text-right text-gray-700">{{ formatNum(s.perimeter_m) }}</td>
              <td class="py-2 px-3 text-right text-gray-700">{{ formatNum(s.dimensions?.width_m) }}</td>
              <td class="py-2 px-3 text-right text-gray-700">{{ formatNum(s.dimensions?.height_m) }}</td>
            </tr>
            <tr v-if="!data.data.spaces?.length" class="text-center text-gray-400 py-4">
              <td colspan="6" class="py-4">暂无空间数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 未命名空间预警 -->
      <div v-if="unnamedCount > 0" class="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-xl">
        <p class="text-sm text-yellow-700">
          ⚠️ {{ unnamedCount }} 个空间未能识别房间名称，可在「融合报价」页进行人工绑定
        </p>
      </div>

      <!-- 图纸ID -->
      <p class="text-xs text-gray-400 mt-3">
        图纸ID: {{ data.data.drawing_id }} | 项目: {{ data.data.project_name || '装修工程' }}
        | 单价: ¥{{ formatPrice(data.data.unit_price) }}/㎡
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ data: Object })

const unnamedCount = computed(() =>
  props.data?.data?.spaces?.filter(s => !s.name || s.name === '未命名空间').length || 0
)

function formatNum(v) { return v ? Number(v).toFixed(2) : '-' }
function formatPrice(v) { return v ? Number(v).toLocaleString() : '0' }
</script>
