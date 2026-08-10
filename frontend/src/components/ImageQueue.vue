<template>
  <div>
    <div
      class="upload-zone h-[220px] mb-3 flex flex-col overflow-hidden !p-0"
      :class="{ active: dragging }"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
      @click="selectFile"
    >
      <input ref="input" type="file" accept=".jpg,.jpeg,.png,.webp" multiple class="hidden" @change="onSelect" />

      <div v-if="queueItems.length === 0" class="flex-1 flex flex-col items-center justify-center text-center p-8">
        <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-purple-50 flex items-center justify-center">
          <svg class="w-7 h-7 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <p class="text-sm font-medium text-gray-700">上传效果图（可多选）</p>
        <p class="text-xs text-gray-400 mt-1">支持 .jpg / .png / .webp，单张或多张都可添加</p>
      </div>

      <div v-else class="w-full h-full flex flex-col" @click.stop>
        <div class="flex items-center justify-between gap-3 px-3 pt-3 pb-2 flex-shrink-0">
          <p class="text-xs font-medium text-gray-500">{{ queueSummaryText }}</p>
          <div class="flex items-center gap-2 flex-shrink-0">
            <button type="button"
                    class="text-xs text-primary-600 hover:text-primary-700 font-medium"
                    @click="selectFile">
              继续添加
            </button>
            <button v-if="pendingFiles.length > 0"
                    type="button"
                    class="text-xs text-gray-500 hover:text-primary-700 disabled:opacity-50"
                    :disabled="queueRunning"
                    @click="startQueue()">
              {{ queueButtonText }}
            </button>
            <button v-if="!queueRunning"
                    type="button"
                    class="text-xs text-gray-400 hover:text-red-500"
                    @click="clearAll">
              清空
            </button>
          </div>
        </div>

        <div class="flex-1 min-h-0 overflow-y-auto px-3 pb-3 space-y-2">
          <div v-for="item in queueItems" :key="item.key"
               class="relative group flex items-center gap-3 rounded-lg border border-gray-200 bg-white/80 p-2 hover:bg-gray-50 transition-colors cursor-pointer"
               @click="enlargeImage(item.preview)">
            <div class="w-14 h-14 rounded-md overflow-hidden border border-gray-200 bg-gray-50 flex-shrink-0">
              <img :src="item.preview" class="w-full h-full object-cover" />
            </div>
            <div class="min-w-0 flex-1 text-left">
              <div class="flex items-center gap-2">
                <p class="text-xs font-medium text-gray-700 truncate" :title="item.filename">{{ item.filename }}</p>
                <span v-if="item.statusText"
                      class="text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0"
                      :class="item.success === false ? 'bg-red-100 text-red-600' : item.done ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'">
                  {{ item.statusText }}
                </span>
              </div>
              <p class="text-[11px] text-gray-400 mt-1 truncate">{{ item.metaText }}</p>
            </div>
            <button v-if="item.pending"
                    class="absolute top-1.5 right-1.5 w-5 h-5 bg-black/45 text-white rounded-full text-xs leading-none flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-black/65 transition-opacity"
                    @click.stop="removePending(item.index)">&times;</button>
          </div>
        </div>
      </div>
    </div>

  </div>

  <div v-if="lightbox.show"
       class="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
       @click.self="lightbox.show = false">
    <div class="relative max-w-[90vw] max-h-[90vh]">
      <img :src="lightbox.url" class="max-w-full max-h-[85vh] rounded-lg shadow-2xl object-contain" />
      <button class="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/35 text-white/80 hover:bg-black/55 hover:text-white flex items-center justify-center text-sm transition-colors"
              @click="lightbox.show = false">&times;</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import API from '../services/api.js'

const emit = defineEmits(['results-update', 'pending-update', 'progress-update'])
const latestImageResultIds = inject('latestImageResultIds', ref([]))
const props = defineProps({
  // 当前 CAD 图纸 ID。为 0 时保持旧行为：效果图只进入历史库，不归属到当前图纸。
  drawingId: { type: Number, default: 0 },
  model: { type: String, default: '' },
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

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}

function emitPendingUpdate() {
  emit('pending-update', pendingFiles.value.length)
}

function emitProgressUpdate() {
  emit('progress-update', {
    running: queueRunning.value,
    finished: finishedCount.value,
    total: totalCount.value,
    currentName: currentProcessing.value?.name || '',
    error: queueError.value,
  })
}

const finishedCount = computed(() => results.value.length)
const totalCount = computed(() => pendingFiles.value.length + results.value.length)
const queueItems = computed(() => [
  ...pendingFiles.value.map((item, index) => ({
    key: `pending-${index}-${item.file.name}`,
    pending: true,
    done: false,
    success: null,
    index,
    filename: item.file.name,
    preview: item.preview,
    statusText: queueRunning.value && currentProcessing.value?.name === item.file.name ? '识别中' : '待识别',
    metaText: formatSize(item.file.size),
  })),
  ...results.value.map((item, index) => ({
    key: `result-${index}-${item.filename}`,
    pending: false,
    done: true,
    success: item.success,
    index,
    filename: item.filename,
    preview: item.preview,
    statusText: item.success ? '成功' : '失败',
    metaText: item.success
      ? `空间: ${item.recognized_space || '-'} · 墙面: ${item.wall || '-'} · 地面: ${item.floor || '-'} · 顶面: ${item.ceiling || '-'}`
      : (item.error || '识别失败'),
  })),
])
const queueSummaryText = computed(() => {
  if (pendingFiles.value.length > 0 && results.value.length > 0) {
    return `待识别 ${pendingFiles.value.length} 张，已识别 ${results.value.length} 张`
  }
  if (pendingFiles.value.length > 0) return `已选择 ${pendingFiles.value.length} 张效果图`
  return `已识别 ${results.value.length} 张效果图`
})
const queueButtonText = computed(() => (
  queueRunning.value
    ? '\u961f\u5217\u8fd0\u884c\u4e2d...'
    : `\u4ec5\u4e32\u884c\u8bc6\u522b\u6548\u679c\u56fe\uff08${pendingFiles.value.length}\u5f20\uff09`
))

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
      emitPendingUpdate()
    }
    reader.readAsDataURL(f)
  }
}

function removePending(idx) {
  pendingFiles.value.splice(idx, 1)
  emitPendingUpdate()
}

function removePendingItem(item) {
  const index = pendingFiles.value.indexOf(item)
  if (index >= 0) {
    pendingFiles.value.splice(index, 1)
    emitPendingUpdate()
  }
}

function clearAll() {
  pendingFiles.value = []
  results.value = []
  queueError.value = ''
  currentProcessing.value = null
  emitPendingUpdate()
  emitProgressUpdate()
}

async function startQueue(drawingIdOverride = null) {
  if (queueRunning.value || pendingFiles.value.length === 0) return []
  queueRunning.value = true
  queueError.value = ''
  emitProgressUpdate()
  // 新队列开始时清空“本次上传”集合，避免融合报价继续展示上一轮结果。
  latestImageResultIds.value = []

  const files = [...pendingFiles.value]
  const effectiveDrawingId = Number(drawingIdOverride ?? props.drawingId) || 0

  for (let i = 0; i < files.length; i++) {
    const item = files[i]
    currentProcessing.value = item.file
    emitProgressUpdate()

    try {
      const res = await API.analyzeImage(item.file, {
        // 多张队列与单张上传使用同一归属规则：有 CAD 图纸 ID 才绑定到当前图纸。
        drawingId: effectiveDrawingId,
        model: props.model,
        fileCount: files.length,
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
      removePendingItem(item)
      emitProgressUpdate()
    } catch (e) {
      results.value.push({
        success: false,
        filename: item.file.name,
        preview: item.preview,
        error: e.message || '未知错误',
      })
      removePendingItem(item)
      emitProgressUpdate()
    }

    // 每张处理完后等一小段时间确保后端释放锁
    if (i < files.length - 1) {
      await new Promise(r => setTimeout(r, 500))
    }
  }

  currentProcessing.value = null
  queueRunning.value = false
  emitProgressUpdate()
  emit('results-update', results.value)
  return results.value
}

function hasPendingFiles() {
  return pendingFiles.value.length > 0
}

defineExpose({
  startQueue,
  hasPendingFiles,
  clearAll,
})
</script>
