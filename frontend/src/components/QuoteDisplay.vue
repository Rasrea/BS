<template>
  <div class="card" v-if="data">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
        <span>💰</span> {{ title }}
      </h3>
      <div class="flex items-center gap-2">
        <button v-if="editing" class="btn-primary text-sm !px-3 !py-1.5" :disabled="saving" @click="saveEdits">
          {{ saving ? '保存中...' : '💾 保存修改' }}
        </button>
        <button v-if="!editing && items.length > 0" class="btn-secondary text-sm !px-3 !py-1.5" @click="editing=true">
          ✏️ 编辑报价
        </button>
        <button v-if="editing" class="btn-secondary text-sm !px-3 !py-1.5" @click="editing=false; cancelEdits()">
          取消
        </button>
        <button v-if="data.data?.quote_id" class="btn-primary text-sm !px-4 !py-2" :disabled="exporting" @click="doExport">
          <svg v-if="exporting" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ exporting ? '导出中...' : '📥 导出Excel' }}
        </button>
      </div>
    </div>

    <!-- 编辑提示 -->
    <div v-if="editing" class="p-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 mb-3">
      ✏️ 编辑模式：可修改数量、材料名称、材料单价、人工单价。修改材料名后系统自动匹配标准单价。
    </div>

    <div v-if="!data.success" class="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
      {{ data.message }}
    </div>

    <template v-if="data.success">
      <!-- 报价汇总 -->
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <div class="bg-gray-50 rounded-xl p-3 text-center">
          <p class="text-xs text-gray-500">总面积</p>
          <p class="text-lg font-bold text-gray-800">{{ formatNum(totalArea) }} ㎡</p>
        </div>
        <div class="bg-blue-50 rounded-xl p-3 text-center">
          <p class="text-xs text-blue-600">基础报价</p>
          <p class="text-lg font-bold text-blue-700">¥{{ formatPrice(displayTotals.base_price) }}</p>
        </div>
        <div class="bg-green-50 rounded-xl p-3 text-center">
          <p class="text-xs text-green-600">材质差价</p>
          <p class="text-lg font-bold text-green-700">+¥{{ formatPrice(displayTotals.material_diff_price) }}</p>
        </div>
        <div class="bg-orange-50 rounded-xl p-3 text-center">
          <p class="text-xs text-orange-600">损耗</p>
          <p class="text-lg font-bold text-orange-700">+¥{{ formatPrice(displayTotals.loss_price) }}</p>
        </div>
        <div class="bg-purple-50 rounded-xl p-3 text-center">
          <p class="text-xs text-purple-600">管理费</p>
          <p class="text-lg font-bold text-purple-700">+¥{{ formatPrice(displayTotals.manage_fee) }}</p>
        </div>
        <div class="bg-yellow-50 rounded-xl p-3 text-center">
          <p class="text-xs text-yellow-600">税费</p>
          <p class="text-lg font-bold text-yellow-700">+¥{{ formatPrice(displayTotals.tax_fee) }}</p>
        </div>
      </div>

      <!-- 最终报价 -->
      <div class="p-4 bg-gradient-to-r from-primary-50 to-blue-50 rounded-xl border border-primary-200 mb-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-primary-600 mb-1">最终报价</p>
            <p class="text-2xl font-bold text-primary-800">¥{{ formatPrice(displayTotals.final_price) }}</p>
          </div>
          <span class="text-3xl">🏷️</span>
        </div>
      </div>

      <!-- 分项明细 -->
      <div class="overflow-x-auto" v-if="items.length > 0">
        <h4 class="text-sm font-medium text-gray-700 mb-2">分项明细</h4>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-2 px-3 text-gray-600 font-medium">空间</th>
              <th class="text-left py-2 px-3 text-gray-600 font-medium">类别</th>
              <th class="text-left py-2 px-3 text-gray-600 font-medium">项目</th>
              <th class="text-left py-2 px-3 text-gray-600 font-medium">材质来源</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">数量</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">材料单价</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">人工单价</th>
              <th class="text-right py-2 px-3 text-gray-600 font-medium">小计</th>
              <th v-if="editing" class="text-center py-2 px-3 text-gray-600 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, i) in items" :key="i"
                class="border-b border-gray-100 hover:bg-gray-50"
                :class="{ 'bg-yellow-50': (editing && editDirty[i]) || item.price_matched === false }">
              <td class="py-2 px-3 text-gray-800">{{ item.space_name || '-' }}</td>
              <td class="py-2 px-3 text-gray-600">
                <select v-if="editing" v-model="item.category"
                        class="border border-gray-300 rounded px-1 py-0.5 text-xs w-20">
                  <option>墙面工程</option><option>地面工程</option><option>吊顶工程</option>
                </select>
                <span v-else>{{ item.category || '-' }}</span>
              </td>
              <td class="py-2 px-3">
                <input v-if="editing" v-model="item.project_name"
                       class="border border-gray-300 rounded px-1 py-0.5 text-xs w-24" />
                <template v-else>
                  <span class="text-gray-600">{{ item.project_name || '-' }}</span>
                  <div v-if="item.price_matched === false" class="text-[10px] text-yellow-700 mt-0.5">
                    {{ item.price_warning || '未匹配到材质价格，已使用默认单价，请人工确认' }}
                  </div>
                </template>
              </td>
              <td class="py-2 px-3">
                <span class="text-[10px] px-1.5 py-0.5 rounded"
                      :class="materialSourceClass(item)"
                      :title="item.material_source_note || materialSourceText(item)">
                  {{ item.material_source_label || materialSourceText(item) }}
                </span>
              </td>
              <td class="py-2 px-3 text-right">
                <input v-if="editing" v-model.number="item.quantity" type="number" step="0.01"
                       class="border border-gray-300 rounded px-1 py-0.5 text-xs w-20 text-right"
                       @input="onEdit(i)" />
                <span v-else class="text-gray-700">{{ formatNum(item.quantity) }}</span>
              </td>
              <td class="py-2 px-3 text-right">
                <input v-if="editing" v-model.number="item.material_unit_price" type="number" step="0.01"
                       class="border border-gray-300 rounded px-1 py-0.5 text-xs w-20 text-right"
                       @input="onEdit(i)" />
                <span v-else class="text-gray-700">
                  ¥{{ formatPrice(item.material_unit_price) }}
                  <span v-if="item.price_matched === false"
                        class="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700"
                        :title="item.price_warning || '未匹配到材质价格，已使用默认单价，请人工确认'">
                    需确认
                  </span>
                </span>
              </td>
              <td class="py-2 px-3 text-right">
                <input v-if="editing" v-model.number="item.labor_unit_price" type="number" step="0.01"
                       class="border border-gray-300 rounded px-1 py-0.5 text-xs w-20 text-right"
                       @input="onEdit(i)" />
                <span v-else class="text-gray-700">¥{{ formatPrice(item.labor_unit_price) }}</span>
              </td>
              <td class="py-2 px-3 text-right text-gray-700 font-medium">
                ¥{{ formatPrice(item.subtotal || (item.quantity * (item.material_unit_price + item.labor_unit_price))) }}
              </td>
              <td v-if="editing" class="py-2 px-3 text-center">
                <select v-model="item.material_name"
                        class="border border-gray-300 rounded px-1 py-0.5 text-xs w-22"
                        @change="onMaterialChange(i)">
                  <option value="">-- 选材料 --</option>
                  <optgroup label="墙面">
                    <option value="乳胶漆">乳胶漆</option>
                    <option value="瓷砖">瓷砖</option>
                    <option value="墙纸">墙纸</option>
                    <option value="木饰面">木饰面</option>
                  </optgroup>
                  <optgroup label="地面">
                    <option value="地砖">地砖</option>
                    <option value="实木地板">实木地板</option>
                    <option value="复合地板">复合地板</option>
                    <option value="大理石">大理石</option>
                  </optgroup>
                  <optgroup label="顶面">
                    <option value="石膏板">石膏板</option>
                    <option value="铝扣板">铝扣板</option>
                    <option value="乳胶漆">乳胶漆顶面</option>
                  </optgroup>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 保存状态 -->
      <div v-if="saveResult" class="mt-4 p-3 rounded-xl text-sm"
        :class="saveResult.success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'">
        {{ saveResult.message }}
      </div>

      <!-- 导出状态 -->
      <div v-if="exportResult" class="mt-2 p-3 rounded-xl text-sm"
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
import { ref, computed } from 'vue'
import API from '../services/api.js'

const props = defineProps({
  data: Object,
  title: { type: String, default: '融合报价' },
})

const emit = defineEmits(['quote-exists'])

const exporting = ref(false)
const exportResult = ref(null)
const editing = ref(false)
const saving = ref(false)
const saveResult = ref(null)
const editDirty = ref({})

// 从 data 中提取 items
const rawItems = computed(() => {
  const src = props.data?.data?.items || props.data?.data?.quote_detail_json || []
  return JSON.parse(JSON.stringify(src))
})

const items = ref([])

// 初始化 items
function initItems() {
  items.value = rawItems.value
  editDirty.value = {}
}
initItems()

// 待计算的总预览
const displayTotals = computed(() => {
  if (!editing.value) {
    return {
      base_price: props.data?.data?.base_price || 0,
      material_diff_price: props.data?.data?.material_diff_price || 0,
      process_add_price: props.data?.data?.process_add_price || 0,
      loss_price: props.data?.data?.loss_price || 0,
      manage_fee: props.data?.data?.manage_fee || 0,
      tax_fee: props.data?.data?.tax_fee || 0,
      final_price: props.data?.data?.final_price || 0,
    }
  }
  // 编辑模式：实时计算
  const base = items.value.reduce((s, i) => {
    const q = Number(i.quantity) || 0
    const mp = Number(i.material_unit_price) || 0
    const lp = Number(i.labor_unit_price) || 0
    return s + q * (mp + lp)
  }, 0)
  const loss = base * 0.03
  const mgmt = base * 0.05
  const tax = (base + loss + mgmt) * 0.03
  return {
    base_price: base,
    material_diff_price: 0,
    process_add_price: 0,
    loss_price: loss,
    manage_fee: mgmt,
    tax_fee: tax,
    final_price: base + loss + mgmt + tax,
  }
})

const totalArea = computed(() => props.data?.data?.total_area || 0)

function formatNum(v) { return v ? Number(v).toFixed(2) : '-' }
function formatPrice(v) { return v ? Number(v).toLocaleString() : '0' }

function materialSourceText(item) {
  if (item.material_source === 'ai') return 'AI材质'
  if (item.material_source === 'manual') return '人工绑定'
  return '默认计价'
}

function materialSourceClass(item) {
  if (item.material_source === 'ai') return 'bg-blue-100 text-blue-700'
  if (item.material_source === 'manual') return 'bg-green-100 text-green-700'
  return 'bg-gray-100 text-gray-600'
}

function onEdit(i) {
  editDirty.value[i] = true
  const item = items.value[i]
  const q = Number(item.quantity) || 0
  const mp = Number(item.material_unit_price) || 0
  const lp = Number(item.labor_unit_price) || 0
  item.subtotal = q * (mp + lp)
}

function onMaterialChange(i) {
  editDirty.value[i] = true
  // 自动匹配——后端做，前端先不重复
}

function cancelEdits() {
  initItems()
}

async function saveEdits() {
  saving.value = true
  saveResult.value = null
  const quoteId = props.data?.data?.quote_id || props.data?.data?.id
  if (!quoteId) {
    saveResult.value = { success: false, message: '缺少报价ID' }
    saving.value = false
    return
  }
  const res = await API.put(`/quote/${quoteId}/items`, { items: items.value })
  if (res.success) {
    saveResult.value = { success: true, message: '✅ 报价已更新' }
    editing.value = false
    emit('quote-exists', quoteId)
  } else {
    saveResult.value = { success: false, message: res.message || '保存失败' }
  }
  saving.value = false
}

async function doExport() {
  exporting.value = true
  exportResult.value = null
  const quoteId = props.data?.data?.quote_id || props.data?.data?.id
  if (!quoteId) { exportResult.value = { success: false, message: '缺少报价ID' }; exporting.value = false; return }
  const res = await API.downloadExcelBlob(quoteId)
  exportResult.value = res
  exporting.value = false
}
</script>
