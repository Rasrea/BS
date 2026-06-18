<template>
  <div class="space-y-6">
    <!-- ====== 报价模板切换 ====== -->
    <div>
      <h3 class="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <span>📋</span> 报价模板
      </h3>
      <div class="card flex items-center gap-4 flex-wrap">
        <template v-if="templates.length === 0">
          <span class="text-sm text-gray-400">加载中...</span>
        </template>
        <template v-else>
          <span class="text-sm text-gray-600">当前模板:</span>
          <span class="text-sm font-semibold text-primary-700 bg-primary-50 px-3 py-1 rounded-lg">
            {{ activeTemplateLabel }}
          </span>
          <div class="flex gap-2">
            <button v-for="t in templates" :key="t.id"
              @click="switchTemplate(t.id)"
              class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
              :class="t.id === activeTemplateId
                ? 'bg-primary-100 text-primary-700 border border-primary-300 ring-2 ring-primary-400'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-gray-200'">
              {{ t.label }}
            </button>
          </div>
          <span v-if="tplMsg" class="text-xs text-green-600">{{ tplMsg }}</span>
        </template>
      </div>
    </div>

    <!-- ====== 视觉模型（已移至首页分析区） ====== -->

    <!-- ====== 费率配置（分组） ====== -->
    <div>
      <h3 class="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <span>⚙️</span> 费率配置
      </h3>
      <div v-if="!pricingLoaded" class="text-center text-gray-400 py-4">加载中...</div>
      <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- 费率组 -->
        <div v-for="(group, gkey) in groupedSettings" :key="gkey" class="card">
          <h4 class="text-sm font-semibold text-gray-700 mb-3 border-b border-gray-100 pb-2">{{ group.label }}</h4>
          <div v-for="item in group.items" :key="item.key" class="mb-3">
            <label class="text-xs text-gray-500 block mb-1">{{ item.desc }}</label>
            <div class="flex items-center gap-2">
              <input v-model.number="item.editValue" type="number" step="0.01"
                     @input="item.editValue = $event.target.valueAsNumber"
                     class="w-24 border border-gray-300 rounded px-2 py-1 text-sm text-right" />
              <span class="text-xs text-gray-400">{{ item.suffix }}</span>
              <button v-if="item.dirty" @click="saveOne(item.key, item.editValue)"
                      class="text-xs px-2 py-1 bg-primary-50 text-primary-700 rounded hover:bg-primary-100">
                保存
              </button>
            </div>
            <input v-if="item.suffix === '%'" type="range" min="0" max="30" step="0.5"
                   v-model.number="item.editValue"
                   @input="item.editValue = $event.target.valueAsNumber"
                   class="w-full mt-1 accent-primary-600" />
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 扣减系数配置 ====== -->
    <div>
      <h3 class="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <span>🔧</span> 洞口扣减系数
      </h3>
      <div v-if="!pricingLoaded" class="text-center text-gray-400 py-4">加载中...</div>
      <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="item in deductionItems" :key="item.key" class="card">
          <label class="text-xs text-gray-500 block mb-1">{{ item.desc }}</label>
          <div class="flex items-center gap-2">
            <input v-model.number="item.editValue" type="number" step="0.01" min="0" max="1"
                   @input="item.editValue = Math.min(1, Math.max(0, $event.target.valueAsNumber || 0))"
                   class="w-20 border border-gray-300 rounded px-2 py-1 text-sm text-right" />
              <span class="text-xs text-gray-400">{{ (item.editValue * 100).toFixed(0) }}%</span>
              <button v-if="item.dirty" @click="saveOne(item.key, item.editValue)"
                      class="text-xs px-2 py-1 bg-primary-50 text-primary-700 rounded hover:bg-primary-100">
                保存
              </button>
            </div>
            <input type="range" min="0" max="1" step="0.05"
                   v-model.number="item.editValue"
                   class="w-full mt-1 accent-primary-600" />
        </div>
      </div>
    </div>

    <!-- ====== 计价分项列表 ====== -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
          <span>💰</span> 计价分项明细
          <span class="text-xs font-normal text-gray-400">({{ activeTemplateLabel }})</span>
        </h3>
        <button @click="showAddItem = !showAddItem"
                class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 border border-green-200">
          {{ showAddItem ? '取消' : '+ 新增分项' }}
        </button>
      </div>

      <!-- 新增分项表单 -->
      <div v-if="showAddItem" class="card mb-4">
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div>
            <label class="text-xs text-gray-500 block mb-1">面类型</label>
            <select v-model="newItem.surface_type" class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="wall">墙面</option>
              <option value="floor">地面</option>
              <option value="ceiling">顶面</option>
              <option value="all">通用</option>
            </select>
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">项目名称</label>
            <input v-model="newItem.item_name" placeholder="如：乳胶漆墙面" class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">综合单价</label>
            <input v-model.number="newItem.unit_price" type="number" step="1" placeholder="0"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">单位</label>
            <input v-model="newItem.unit" placeholder="㎡" class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div class="flex items-end">
            <button @click="addNewItem" :disabled="!newItem.item_name"
                    class="btn-primary text-xs w-full">
              确认添加
            </button>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-3 mt-2">
          <div>
            <label class="text-xs text-gray-500 block mb-1">材料费</label>
            <input v-model.number="newItem.unit_price_material" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">人工费</label>
            <input v-model.number="newItem.unit_price_labor" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">辅料费</label>
            <input v-model.number="newItem.unit_price_aux" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
        </div>
      </div>

      <!-- 计价分项表格 -->
      <div v-if="pricingItems.length === 0" class="card text-center text-gray-400 py-6">
        当前模板暂无计价分项，请添加
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200 bg-gray-50">
              <th class="text-left py-2 px-2 font-medium text-gray-600">面类型</th>
              <th class="text-left py-2 px-2 font-medium text-gray-600">项目名称</th>
              <th class="text-right py-2 px-2 font-medium text-gray-600">综合单价</th>
              <th class="text-right py-2 px-2 font-medium text-gray-600">材料费</th>
              <th class="text-right py-2 px-2 font-medium text-gray-600">人工费</th>
              <th class="text-right py-2 px-2 font-medium text-gray-600">辅料费</th>
              <th class="text-center py-2 px-2 font-medium text-gray-600">单位</th>
              <th class="text-center py-2 px-2 font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in groupedItems" :key="item.id" class="border-b border-gray-100 hover:bg-gray-50">
              <td class="py-2 px-2">
                <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{{ surfaceLabel(item.surface_type) }}</span>
              </td>
              <td class="py-2 px-2 font-medium text-gray-800">{{ item.item_name }}</td>
              <td class="py-2 px-2 text-right text-primary-700 font-medium">¥{{ item.unit_price }}</td>
              <td class="py-2 px-2 text-right text-gray-600">¥{{ item.unit_price_material }}</td>
              <td class="py-2 px-2 text-right text-gray-600">¥{{ item.unit_price_labor }}</td>
              <td class="py-2 px-2 text-right text-gray-600">¥{{ item.unit_price_aux }}</td>
              <td class="py-2 px-2 text-center text-gray-500">{{ item.unit }}</td>
              <td class="py-2 px-2 text-center">
                <button @click="editItemId = item.id; editForm = {...item}"
                        class="text-xs text-primary-600 hover:text-primary-800 mr-2">编辑</button>
                <button @click="confirmDeleteItem(item.id, item.item_name)" class="text-xs text-red-500 hover:text-red-700">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 编辑分项弹窗 -->
    <div v-if="editItemId" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
         @click.self="editItemId = null">
      <div class="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl border">
        <h4 class="text-sm font-semibold text-gray-800 mb-4">编辑计价分项</h4>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-xs text-gray-500 block mb-1">项目名称</label>
            <input v-model="editForm.item_name" class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">面类型</label>
            <select v-model="editForm.surface_type" class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="wall">墙面</option>
              <option value="floor">地面</option>
              <option value="ceiling">顶面</option>
              <option value="all">通用</option>
            </select>
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">综合单价</label>
            <input v-model.number="editForm.unit_price" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">单位</label>
            <input v-model="editForm.unit" class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">材料费</label>
            <input v-model.number="editForm.unit_price_material" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">人工费</label>
            <input v-model.number="editForm.unit_price_labor" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">辅料费</label>
            <input v-model.number="editForm.unit_price_aux" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">排序</label>
            <input v-model.number="editForm.sort_order" type="number" step="1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button @click="editItemId = null" class="btn-secondary text-xs px-4">取消</button>
          <button @click="saveEditItem" class="btn-primary text-xs px-4">保存修改</button>
        </div>
      </div>
    </div>

    <!-- ====== 工序单价概况 ====== -->
    <div>
      <h3 class="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
        <span>🔨</span> 工序单价概况
      </h3>
      <div v-if="processes.length === 0" class="card text-center text-gray-400 py-4">暂无工序数据</div>
      <div v-else class="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div v-for="p in processes" :key="p.id" class="card">
          <div class="flex items-center gap-1.5 mb-1">
            <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: p.color }"></span>
            <span class="text-sm font-medium text-gray-700">{{ p.name }}</span>
          </div>
          <div class="flex items-center gap-1">
            <span class="text-xs text-gray-400">单价:</span>
            <span class="text-sm font-semibold text-primary-700">¥{{ p.unit_price || 0 }}/{{ p.unit || '㎡' }}</span>
          </div>
          <div class="text-xs text-gray-400 mt-1">{{ p.standard_days }}天</div>
        </div>
      </div>
    </div>

    <!-- 批注 -->
    <div class="text-xs text-gray-400 text-center py-2">
      💡 修改费率/单价后点击「保存」写入数据库，下次融合报价生效
    </div>

    <!-- 自定义删除确认弹窗 -->
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="确认删除"
      :message="deleteMessage"
      @confirm="doDeleteItem"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import API from '../services/api.js'
import ConfirmDialog from './ConfirmDialog.vue'

// ======== 模版 ========
const templates = ref([])
const activeTemplateId = ref(1)
const activeTemplateLabel = ref('标准型')
const tplMsg = ref('')

async function loadTemplates() {
  const res = await API.get('/pricing/templates')
  if (res.success && res.data) {
    templates.value = res.data
    const active = res.data.find(t => t.is_default)
    if (active) {
      activeTemplateId.value = active.id
      activeTemplateLabel.value = active.label
    }
  }
}

async function switchTemplate(tid) {
  const fd = new FormData()
  fd.append('template_id', tid)
  const res = await API.post('/pricing/templates/switch', fd)
  if (res.success) {
    activeTemplateId.value = tid
    const t = templates.value.find(t => t.id === tid)
    activeTemplateLabel.value = t ? t.label : `模板#${tid}`
    tplMsg.value = `已切换至 ${activeTemplateLabel.value}`
    setTimeout(() => tplMsg.value = '', 2000)
    loadPricingItems()
  }
}

// ======== 视觉模型（已迁移至App.vue首页） ========

// ======== 定价配置（分组） ========
const pricingLoaded = ref(false)
const allSettings = ref([])
const groupedSettings = computed(() => {
  const groups = {
    rates: { label: '费率配置', items: [] },
    area: { label: '面积系数', items: [] },
    other: { label: '其他', items: [] },
  }
  for (const s of allSettings.value) {
    const item = { ...s, editValue: parseFloat(s.value) || 0, dirty: false, suffix: '' }
    if (['manage_fee_rate', 'tax_rate', 'loss_rate'].includes(s.key)) {
      item.suffix = '%'
      item.editValue = (parseFloat(s.value) || 0) * 100
      groups.rates.items.push(item)
    } else if (['wall_area_factor', 'ceiling_factor', 'perimeter_factor'].includes(s.key)) {
      groups.area.items.push(item)
    } else if (!s.key.startsWith('deduct_') && !s.key.startsWith('niche_') && !s.key.startsWith('pillar_') && !s.key.startsWith('bay_window_') && s.key !== 'active_vl_model') {
      groups.other.items.push(item)
    }
  }
  // 监听变化
  for (const g of Object.values(groups)) {
    for (const item of g.items) {
      const orig = parseFloat(item.value) || 0
      const current = item.suffix === '%' ? (item.editValue / 100) : item.editValue
      item.dirty = Math.abs(current - orig) > 0.001
    }
  }
  return groups
})

// 扣减系数
const deductionItems = computed(() => {
  return allSettings.value
    .filter(s => s.key.startsWith('deduct_') || s.key.startsWith('niche_') || s.key.startsWith('pillar_') || s.key.startsWith('bay_window_'))
    .map(s => {
      const val = parseFloat(s.value) || 0
      const snapped = Math.round(val / 0.05) * 0.05
      return {
        ...s,
        editValue: snapped,
        dirty: Math.abs(snapped - val) > 0.001,
        desc: s.description?.replace(/_/g, ' ') || s.key,
      }
    })
})

async function loadPricing() {
  pricingLoaded.value = false
  const res = await API.getPricing()
  if (res.success && res.data) {
    const arr = []
    const descMap = {
      base_unit_price: '基础单价',
      manage_fee_rate: '管理费',
      tax_rate: '税费',
      loss_rate: '材料损耗',
      wall_area_factor: '墙面面积系数',
      ceiling_factor: '吊顶面积系数',
      perimeter_factor: '周长系数',
      switch_per_10sqm: '每10㎡开关',
      garbage_per_30sqm: '每30㎡垃圾车',
      deduct_door: '木门扣减',
      deduct_window: '铝合金窗扣减',
      deduct_sliding_door: '推拉门扣减',
      deduct_bg_wall: '背景墙扣减',
      deduct_niche: '壁龛扣减',
      deduct_pillar: '立柱扣减',
      deduct_bay_window: '飘窗扣减',
      deduct_door_window: '门窗洞口扣减(通用)',
      deduct_wc_kitchen: '卫生间/厨房扣减',
      deduct_balcony: '阳台扣减',
      niche_add_rate: '壁龛增量',
      pillar_add_rate: '立柱增量',
      bay_window_add_rate: '飘窗增量',
    }
    for (const [key, value] of Object.entries(res.data)) {
      if (typeof value === 'string' || typeof value === 'number') {
        arr.push({ key, value: String(value), description: descMap[key] || key })
      }
    }
    allSettings.value = arr
  }
  pricingLoaded.value = true
}

async function saveOne(key, val) {
  const displayVal = ['manage_fee_rate', 'tax_rate', 'loss_rate'].includes(key)
    ? (val / 100).toString()
    : String(val)
  const res = await API.updatePricing(key, displayVal)
  if (res.success) {
    const idx = allSettings.value.findIndex(s => s.key === key)
    if (idx >= 0) {
      allSettings.value[idx].value = displayVal
    }
  }
}

// ======== 计价分项 ========
const pricingItems = ref([])
const showAddItem = ref(false)
const editItemId = ref(null)
const editForm = ref({})

const newItem = ref({
  template_id: 1,
  surface_type: 'wall',
  item_name: '',
  unit: '㎡',
  unit_price: 0,
  unit_price_material: 0,
  unit_price_labor: 0,
  unit_price_aux: 0,
  sort_order: 0,
  description: '',
})

const surfaceLabel = (st) => ({ wall: '墙面', floor: '地面', ceiling: '顶面', all: '通用' })[st] || st

const groupedItems = computed(() => {
  return [...pricingItems.value].sort((a, b) => a.sort_order - b.sort_order)
})

async function loadPricingItems() {
  const res = await API.get(`/pricing/items?template_id=${activeTemplateId.value}`)
  if (res.success && res.data) {
    pricingItems.value = res.data
  }
}

async function addNewItem() {
  if (!newItem.value.item_name) return
  const fd = new FormData()
  fd.append('template_id', activeTemplateId.value)
  fd.append('surface_type', newItem.value.surface_type)
  fd.append('item_name', newItem.value.item_name)
  fd.append('unit', newItem.value.unit)
  fd.append('unit_price', newItem.value.unit_price || 0)
  fd.append('unit_price_material', newItem.value.unit_price_material || 0)
  fd.append('unit_price_labor', newItem.value.unit_price_labor || 0)
  fd.append('unit_price_aux', newItem.value.unit_price_aux || 0)
  fd.append('sort_order', newItem.value.sort_order || 0)
  fd.append('description', newItem.value.description || '')
  const res = await API.post('/pricing/items', fd)
  if (res.success) {
    newItem.value = { template_id: activeTemplateId.value, surface_type: 'wall', item_name: '', unit: '㎡', unit_price: 0, unit_price_material: 0, unit_price_labor: 0, unit_price_aux: 0, sort_order: 0, description: '' }
    showAddItem.value = false
    loadPricingItems()
  }
}

async function saveEditItem() {
  const f = editForm.value
  const fd = new FormData()
  if (f.item_name) fd.append('item_name', f.item_name)
  if (f.surface_type) fd.append('surface_type', f.surface_type)
  if (f.unit) fd.append('unit', f.unit)
  fd.append('unit_price', f.unit_price || 0)
  fd.append('unit_price_material', f.unit_price_material || 0)
  fd.append('unit_price_labor', f.unit_price_labor || 0)
  fd.append('unit_price_aux', f.unit_price_aux || 0)
  if (f.sort_order) fd.append('sort_order', f.sort_order)
  const res = await API.put(`/pricing/items/${editItemId.value}`, fd)
  if (res.success) {
    editItemId.value = null
    loadPricingItems()
  }
}

// 删除确认弹窗
const showDeleteDialog = ref(false)
const pendingDeletePid = ref(null)
const deleteMessage = ref('')

function confirmDeleteItem(pid, itemName) {
  pendingDeletePid.value = pid
  deleteMessage.value = `确认删除计价分项「${itemName}」？此操作不可撤销。`
  showDeleteDialog.value = true
}

async function doDeleteItem() {
  const pid = pendingDeletePid.value
  if (!pid) return
  showDeleteDialog.value = false
  const res = await API.delete(`/pricing/items/${pid}`)
  if (res.success) {
    loadPricingItems()
  }
  pendingDeletePid.value = null
}

// ======== 工序概况 ========
const processes = ref([])
async function loadProcesses() {
  const res = await API.get('/processes')
  if (res.success && res.data) {
    processes.value = res.data
  }
}

onMounted(() => {
  loadTemplates()
  loadPricing()
  loadPricingItems()
  loadProcesses()
})
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
  @apply bg-gray-100 text-gray-600 px-4 py-2 rounded-lg text-sm font-medium
         hover:bg-gray-200 transition-colors border border-gray-200;
}
</style>
