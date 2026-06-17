<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
        <span>📋</span> 施工工序管理
      </h3>
      <div class="flex gap-2">
        <button @click="toggleFlow" class="btn-secondary text-sm !px-3 !py-1.5">
          {{ showFlow ? '📋 列表模式' : '📊 流程图模式' }}
        </button>
        <button @click="addNew" class="btn-primary text-sm !px-3 !py-1.5">＋ 新增工序</button>
      </div>
    </div>

    <!-- 流程图模式 -->
    <div v-if="showFlow" class="card overflow-x-auto mb-6">
      <svg viewBox="0 0 1100 180" class="w-full" style="min-width:900px">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="8" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
          </marker>
          <filter id="shadow" x="-10%" y="-10%" width="130%" height="130%">
            <feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.15" />
          </filter>
        </defs>
        <g v-for="(p, i) in processes" :key="p.id">
          <!-- 箭头 -->
          <line v-if="i < processes.length - 1"
                :x1="60 + i * 100 + 50" y1="125"
                :x2="60 + (i+1) * 100 + 10" y2="125"
                stroke="#94a3b8" stroke-width="2" marker-end="url(#arrowhead)" />
          <!-- 节点 -->
          <rect :x="60 + i * 100" y="70" width="80" height="80" rx="12" ry="12"
                :fill="p.color" filter="url(#shadow)" />
          <text :x="60 + i * 100 + 40" y="100" text-anchor="middle" fill="white" font-size="13" font-weight="bold">
            {{ p.name.substring(0, 4) }}
          </text>
          <text :x="60 + i * 100 + 40" y="118" text-anchor="middle" fill="rgba(255,255,255,0.85)" font-size="10">
            {{ p.standard_days }}工日
          </text>
          <text :x="60 + i * 100 + 40" y="135" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="8">
            #{{ p.sort_order }}
          </text>
          <!-- 序号圈 -->
          <circle :cx="60 + i * 100" :cy="70" r="10" fill="white" stroke="#e2e8f0" />
          <text :x="60 + i * 100" :y="74" text-anchor="middle" fill="#64748b" font-size="10" font-weight="bold">
            {{ p.sort_order }}
          </text>
          <!-- 工期 -->
          <text :x="60 + i * 100 + 40" y="172" text-anchor="middle" fill="#64748b" font-size="11">
            累计 {{ cumDays(i) }}天
          </text>
        </g>
      </svg>
      <div class="border-t border-gray-100 pt-3 mt-2 text-xs text-gray-400 text-center">
        总工期: <strong class="text-gray-700">{{ totalDays }}</strong> 天 |
        <span v-for="p in processes" :key="p.id" class="inline-flex items-center gap-1 ml-3">
          <span class="w-2 h-2 rounded-full inline-block" :style="{background: p.color}"></span>
          {{ p.name }}({{ p.standard_days }}d)
        </span>
      </div>
    </div>

    <!-- 列表模式 -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200">
            <th class="text-center py-2 px-2 w-10">#</th>
            <th class="text-left py-2 px-3 text-gray-600 font-medium">工序名称</th>
            <th class="text-left py-2 px-3 text-gray-600 font-medium">工种</th>
            <th class="text-center py-2 px-3 text-gray-600 font-medium">工期(天)</th>
            <th class="text-left py-2 px-3 text-gray-600 font-medium">适用空间</th>
            <th class="text-left py-2 px-3 text-gray-600 font-medium">说明</th>
            <th class="text-center py-2 px-3 text-gray-600 font-medium">颜色</th>
            <th class="text-center py-2 px-3 text-gray-600 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(p, i) in processes" :key="p.id"
              class="border-b border-gray-100 hover:bg-gray-50">
            <td class="text-center py-2 px-2">
              <div class="flex items-center justify-center gap-1">
                <button @click="moveUp(i)" :disabled="i===0"
                        class="text-gray-400 hover:text-gray-600 disabled:opacity-20 text-xs">▲</button>
                <span class="text-gray-500 text-xs font-mono w-4 text-center">{{ p.sort_order }}</span>
                <button @click="moveDown(i)" :disabled="i===processes.length-1"
                        class="text-gray-400 hover:text-gray-600 disabled:opacity-20 text-xs">▼</button>
              </div>
            </td>
            <td class="py-2 px-3">
              <input v-model="editForms[p.id].name" @blur="saveField(p.id)"
                     class="w-full bg-transparent border-b border-transparent hover:border-gray-300 focus:border-primary-500 focus:outline-none px-1 py-0.5" />
            </td>
            <td class="py-2 px-3">
              <select v-model="editForms[p.id].work_type" @change="saveField(p.id)"
                      class="border border-gray-200 rounded px-1 py-0.5 text-xs">
                <option v-for="wt in workTypes" :key="wt" :value="wt">{{ workTypeLabel(wt) }}</option>
              </select>
            </td>
            <td class="py-2 px-3 text-center">
              <input type="number" step="0.5" min="0.5" max="30"
                     v-model.number="editForms[p.id].standard_days"
                     @blur="saveField(p.id)"
                     class="w-16 text-center border border-gray-200 rounded px-1 py-0.5 text-xs" />
            </td>
            <td class="py-2 px-3">
              <input v-model="editForms[p.id].applicable_spaces" @blur="saveField(p.id)"
                     placeholder="逗号分隔"
                     class="w-full bg-transparent border-b border-transparent hover:border-gray-300 focus:border-primary-500 focus:outline-none px-1 py-0.5 text-xs" />
            </td>
            <td class="py-2 px-3 max-w-[150px]">
              <input v-model="editForms[p.id].description" @blur="saveField(p.id)"
                     class="w-full bg-transparent border-b border-transparent hover:border-gray-300 focus:border-primary-500 focus:outline-none px-1 py-0.5 text-xs truncate" />
            </td>
            <td class="py-2 px-3 text-center">
              <input type="color" v-model="editForms[p.id].color"
                     @change="saveField(p.id)"
                     class="w-8 h-6 rounded cursor-pointer border-0 p-0" />
            </td>
            <td class="py-2 px-3 text-center">
              <button @click="confirmDeleteProcess(p)" class="text-red-400 hover:text-red-600 text-xs"
                      :disabled="processes.length <= 1">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 自定义删除确认弹窗 -->
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="确认删除"
      :message="deleteMessage"
      @confirm="doDeleteProcess"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import API from '../services/api.js'
import ConfirmDialog from './ConfirmDialog.vue'

const processes = ref([])
const editForms = ref({})
const showFlow = ref(true)
const saving = ref({})

const workTypes = ['demolition', 'plumbing_electric', 'waterproofing', 'tiling', 'woodwork', 'painting', 'installation', 'cleaning', 'inspection', 'furnishing', 'finishing', 'other']

function workTypeLabel(wt) {
  const labels = {
    demolition: '拆除', plumbing_electric: '水电', waterproofing: '防水',
    tiling: '瓦工', woodwork: '木工', painting: '油漆',
    installation: '安装', cleaning: '保洁', inspection: '验收',
    furnishing: '软装', finishing: '收尾', other: '其他',
  }
  return labels[wt] || wt
}

const totalDays = computed(() => {
  return processes.value.reduce((s, p) => s + (p.standard_days || 0), 0)
})

function cumDays(idx) {
  return processes.value.slice(0, idx + 1).reduce((s, p) => s + (p.standard_days || 0), 0)
}

async function load() {
  const res = await API.get('/processes')
  if (res.success && res.data?.processes) {
    processes.value = res.data.processes
    processes.value.forEach(p => {
      editForms.value[p.id] = {
        name: p.name,
        work_type: p.work_type,
        standard_days: p.standard_days,
        applicable_spaces: p.applicable_spaces || '',
        description: p.description || '',
        color: p.color || '#6366f1',
      }
    })
  }
}

async function saveField(id) {
  if (saving.value[id]) return
  saving.value[id] = true
  const form = editForms.value[id]
  const fd = new FormData()
  for (const [k, v] of Object.entries(form)) {
    fd.append(k, String(v))
  }
  try {
    await API.put(`/processes/${id}`, fd)
  } catch (e) {}
  saving.value[id] = false
}

async function moveUp(i) {
  if (i <= 0) return
  const a = processes.value[i]
  const b = processes.value[i - 1]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  processes.value.splice(i, 1, b)
  processes.value.splice(i - 1, 1, a)
  await reorderAll()
}

async function moveDown(i) {
  if (i >= processes.value.length - 1) return
  await moveUp(i + 1)
}

async function reorderAll() {
  for (let i = 0; i < processes.value.length; i++) {
    processes.value[i].sort_order = i + 1
    editForms.value[processes.value[i].id].sort_order = i + 1
    const fd = new FormData()
    fd.append('sort_order', String(i + 1))
    try { await API.put(`/processes/${processes.value[i].id}`, fd) } catch (e) {}
  }
}

async function addNew() {
  const fd = new FormData()
  const nextOrder = processes.value.length + 1
  fd.append('name', '新工序')
  fd.append('sort_order', String(nextOrder))
  fd.append('work_type', 'other')
  fd.append('standard_days', '1')
  fd.append('color', '#6366f1')
  const res = await API.post('/processes', fd)
  if (res.success) await load()
}

// 删除确认弹窗
const showDeleteDialog = ref(false)
const pendingDeleteP = ref(null)
const deleteMessage = ref('')

function confirmDeleteProcess(p) {
  pendingDeleteP.value = p
  deleteMessage.value = `确认删除工序「${p.name}」？此操作不可撤销。`
  showDeleteDialog.value = true
}

function doDeleteProcess() {
  const p = pendingDeleteP.value
  if (!p) return
  showDeleteDialog.value = false
  API.delete(`/processes/${p.id}`).then(() => load())
  pendingDeleteP.value = null
}

function toggleFlow() { showFlow.value = !showFlow.value }

onMounted(load)
</script>
