<template>
  <div>
    <!-- 上传区（支持多选） -->
    <div
      class="upload-zone mb-3"
      :class="{ active: dragging }"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
      @click="selectFile"
    >
      <input ref="input" type="file" accept=".jpg,.jpeg,.png,.webp" multiple class="hidden" @change="onSelect" />
      <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-purple-50 flex items-center justify-center">
        <svg class="w-7 h-7 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <p class="text-sm font-medium text-gray-700">上传效果图（可多选）</p>
      <p class="text-xs text-gray-400 mt-1">支持 .jpg / .png / .webp，可多张</p>
    </div>

    <!-- 文件列表（已选未上传） -->
    <div v-if="pendingFiles.length > 0" class="card !p-3 mb-3">
      <p class="text-xs font-medium text-gray-500 mb-2">已选择 {{ pendingFiles.length }} 张效果图</p>
      <div class="flex flex-wrap gap-2">
        <div v-for="(f, i) in pendingFiles" :key="'pending-'+i"
             class="relative w-20 h-20 rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex-shrink-0 cursor-pointer hover:opacity-80 transition-opacity"
             @click="enlargeImage(f.preview)">
          <img :src="f.preview" class="w-full h-full object-cover" />
          <button class="absolute top-0.5 right-0.5 w-4 h-4 bg-red-500 text-white rounded-full text-[10px] leading-none flex items-center justify-center hover:bg-red-600"
                  @click.stop="removePending(i)">×</button>
        </div>
      </div>
    </div>

    <!-- 队列控制 -->
    <div v-if="pendingFiles.length > 0" class="flex items-center gap-3 mb-3">
      <button class="btn-primary text-sm !px-4 !py-2" :disabled="queueRunning"
              @click="startQueue">
        {{ queueRunning ? '队列运行中...' : '🚀 开始串行识别（' + pendingFiles.length + '张）' }}
      </button>
      <button v-if="!queueRunning" class="btn-secondary text-sm !px-3 !py-1.5" @click="clearAll">
        清空
      </button>
    </div>

    <!-- 队列进度条 -->
    <div v-if="queueRunning || finishedCount > 0" class="card !p-3 mb-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-gray-600">
          {{ queueRunning ? '识别中' : '已完成' }}
        </span>
        <span class="text-xs text-gray-400">{{ finishedCount }}/{{ totalCount }}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div class="bg-primary-500 h-2 rounded-full transition-all duration-300"
             :style="{ width: totalCount > 0 ? (finishedCount / totalCount * 100) + '%' : '0%' }"></div>
      </div>
      <p v-if="currentProcessing" class="text-xs text-primary-600 mt-2 animate-pulse">
        🖼️ 正在识别第 {{ finishedCount + 1 }}/{{ totalCount }} 张: {{ currentProcessing.name }}
      </p>
      <p v-if="queueError" class="text-xs text-red-500 mt-1">{{ queueError }}</p>
    </div>

    <!-- 结果列表 -->
    <div v-if="results.length > 0" class="space-y-2">
      <div v-for="(r, i) in results" :key="'result-'+i"
           class="card !p-3 flex items-start gap-3 cursor-pointer hover:bg-gray-50/50"
           :class="r.success ? 'border-green-200' : 'border-red-200'"
           @click="enlargeImage(r.preview)">
        <div class="w-14 h-14 rounded-lg overflow-hidden border border-gray-200 flex-shrink-0 bg-gray-50">
          <img :src="r.preview" class="w-full h-full object-cover" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-gray-800 truncate">{{ r.filename }}</span>
            <span class="text-xs px-1.5 py-0.5 rounded-full"
              :class="r.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
              {{ r.success ? '成功' : '失败' }}
            </span>
          </div>
          <div v-if="r.success" class="text-xs text-gray-500 mt-0.5">
            <span>空间: {{ r.recognized_space || '-' }}</span>
            <span class="ml-2">墙面: {{ r.wall || '-' }}</span>
            <span class="ml-2">地面: {{ r.floor || '-' }}</span>
            <span class="ml-2">顶面: {{ r.ceiling || '-' }}</span>
          </div>
          <div v-else class="text-xs text-red-500 mt-0.5">{{ r.error }}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- 图片预览放大 -->
  <div v-if="lightbox.show"
       class="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
       @click.self="lightbox.show = false">
    <div class="relative max-w-[90vw] max-h-[90vh]">
      <img :src="lightbox.url" class="max-w-full max-h-[85vh] rounded-lg shadow-2xl object-contain" />
      <button class="absolute -top-3 -right-3 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center text-gray-600 hover:text-gray-900 text-sm font-bold"
              @click="lightbox.show = false">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import API from '../services/api.js'

const emit = defineEmits(['results-update'])
const latestImageResultIds = inject('latestImageResultIds', ref([]))
const props = defineProps({
  // 当前 CAD 图纸 ID。为 0 时保持旧行为：效果图只进入历史库，不归属到当前图纸。
  drawingId: { type: Number, default: 0 },
})

const dragging = ref(false)
const input = ref(null)
const pendingFiles = ref([])     // {file, preview}
const queueRunning = ref(false)
const currentProcessing = ref(null)
const queueError = ref('')
const results = ref([])          // {success, filename, preview, ...}

// 图片放大预览
const lightbox = ref({ show: false, url: '' })
function enlargeImage(url) {
  lightbox.value = { show: true, url }
}

const finishedCount = computed(() => results.value.length)
const totalCount = computed(() => pendingFiles.value.length + results.value.length)

function selectFile() { input.value?.click() }
function onSelect(e) { addFiles(e.target.files) }
function onDrop(e) { dragging.value = false; addFiles(e.dataTransfer.files) }

function addFiles(fileList) {
  if (queueRunning.value) return
  const allowed = ['jpg', 'jpeg', 'png', 'webp']
  for (const f of fileList) {
    const ext = f.name.split('.').pop().toLowerCase()
    if (!allowed.includes(ext)) continue
    // 检查是否已添加
    if (pendingFiles.value.some(p => p.file.name === f.name && p.file.size === f.size)) continue
    // 检查是否已处理过
    if (results.value.some(r => r.filename === f.name)) continue
    const reader = new FileReader()
    reader.onload = (e) => {
      pendingFiles.value.push({ file: f, preview: e.target.result })
    }
    reader.readAsDataURL(f)
  }
}

function removePending(idx) {
  pendingFiles.value.splice(idx, 1)
}

function clearAll() {
  pendingFiles.value = []
  results.value = []
  queueError.value = ''
}

async function startQueue() {
  if (queueRunning.value || pendingFiles.value.length === 0) return
  queueRunning.value = true
  queueError.value = ''
  // 新队列开始时清空“本次上传”集合，避免融合报价继续展示上一轮结果。
  latestImageResultIds.value = []

  const files = [...pendingFiles.value]
  pendingFiles.value = []

  for (let i = 0; i < files.length; i++) {
    const item = files[i]
    currentProcessing.value = item.file

    try {
      const res = await API.analyzeImage(item.file, {
        // 多张队列与单张上传使用同一归属规则：有 CAD 图纸 ID 才绑定到当前图纸。
        drawingId: props.drawingId,
      })
      results.value.push({
        success: res.success,
        image_result_id: res.data?.image_result_id || 0,
        filename: item.file.name,
        preview: item.preview,
        recognized_space: res.data?.recognized_space || '',
        wall: res.data?.wall_material || '',
        floor: res.data?.floor_material || '',
        ceiling: res.data?.ceiling_material || '',
        error: res.message || '',
        result_data: res,
      })
    } catch (e) {
      results.value.push({
        success: false,
        filename: item.file.name,
        preview: item.preview,
        error: e.message || '未知错误',
      })
    }

    // 每张处理完后等一小段时间确保后端释放锁
    if (i < files.length - 1) {
      await new Promise(r => setTimeout(r, 500))
    }
  }

  currentProcessing.value = null
  queueRunning.value = false
  emit('results-update', results.value)
}
</script>
