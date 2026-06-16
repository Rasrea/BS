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
      <input ref="input" type="file" accept=".dxf,.dwg" multiple class="hidden" @change="onSelect" />
      <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-blue-50 flex items-center justify-center">
        <svg class="w-7 h-7 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p class="text-sm font-medium text-gray-700">上传 CAD 图纸（可多选）</p>
      <p class="text-xs text-gray-400 mt-1">支持 .dxf / .dwg，可多张（串行处理）</p>
    </div>

    <!-- 文件列表（已选未处理） -->
    <div v-if="pendingFiles.length > 0" class="card !p-3 mb-3">
      <p class="text-xs font-medium text-gray-500 mb-2">已选择 {{ pendingFiles.length }} 张 CAD 图纸</p>
      <div class="space-y-1">
        <div v-for="(f, i) in pendingFiles" :key="'p-'+i"
             class="flex items-center gap-2 text-xs text-gray-700 bg-gray-50 rounded px-2 py-1">
          <span class="text-blue-500">📐</span>
          <span class="flex-1 truncate">{{ f.file.name }}</span>
          <span class="text-gray-400">{{ formatSize(f.file.size) }}</span>
          <button v-if="!queueRunning && f.file.name.toLowerCase().endsWith('.dxf')" class="text-indigo-500 hover:text-indigo-700 font-medium px-1"
                  @click.stop="previewFile(f.file)">🔍</button>
          <button v-if="!queueRunning" class="text-red-400 hover:text-red-600 ml-1"
                  @click.stop="removePending(i)">×</button>
        </div>
      </div>
    </div>

    <!-- 🖼️ 效果图上传（配套） -->
    <div class="border-t border-gray-200 pt-4 mt-4">
      <div class="flex items-center gap-2 mb-3">
        <span class="w-1 h-4 bg-purple-500 rounded-full"></span>
        <span class="text-xs font-semibold text-gray-600">🖼️ 效果图上传（配套）</span>
        <span class="text-[10px] text-gray-400">可多选，与CAD图纸配套使用</span>
      </div>
      <div
        class="upload-zone"
        :class="{ active: imgDragging }"
        @dragover.prevent="imgDragging = true"
        @dragleave="imgDragging = false"
        @drop.prevent="onImgDrop"
        @click="selectImgFile"
      >
        <input ref="imgInput" type="file" accept=".jpg,.jpeg,.png,.webp" multiple class="hidden" @change="onImgSelect" />
        <div class="w-12 h-12 mx-auto mb-2 rounded-2xl bg-purple-50 flex items-center justify-center">
          <svg class="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <p class="text-sm font-medium text-gray-700">上传效果图</p>
        <p class="text-xs text-gray-400 mt-1">支持 .jpg / .png / .webp，可多选</p>
      </div>

      <!-- 效果图缩略图预览 -->
      <div v-if="imageFiles.length > 0" class="flex flex-wrap gap-2 mt-3">
        <div v-for="(img, i) in imageFiles" :key="'img-'+i"
             class="relative w-16 h-16 rounded-lg overflow-hidden border border-gray-200 bg-gray-50 flex-shrink-0 cursor-pointer hover:opacity-90 transition-opacity"
             @click="enlargeImg(img.preview)">
          <img :src="img.preview" class="w-full h-full object-cover" />
          <button class="absolute top-0.5 right-0.5 w-4 h-4 bg-red-500 text-white rounded-full text-[10px] leading-none flex items-center justify-center hover:bg-red-600"
                  @click.stop="removeImg(i)">×</button>
        </div>
      </div>

      <!-- 图片放大预览 -->
      <div v-if="imgLightbox.show"
           class="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
           @click.self="imgLightbox.show = false">
        <div class="relative max-w-[90vw] max-h-[90vh]">
          <img :src="imgLightbox.url" class="max-w-full max-h-[85vh] rounded-lg shadow-2xl object-contain" />
          <button class="absolute -top-3 -right-3 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center text-gray-600 hover:text-gray-900 text-sm font-bold"
                  @click="imgLightbox.show = false">✕</button>
        </div>
      </div>
    </div>

    <!-- 项目名称 -->
    <div class="card !p-3 mb-3">
      <label class="text-xs text-gray-500 block mb-1">项目名称（可选）</label>
      <input v-model="projectName" placeholder="装修工程"
             class="w-full max-w-xs border border-gray-300 rounded-lg px-3 py-1.5 text-sm" />
    </div>

    <!-- 队列控制 -->
    <div v-if="pendingFiles.length > 0" class="flex items-center gap-3 mb-3">
      <button class="btn-primary text-sm !px-4 !py-2" :disabled="queueRunning"
              @click="startQueue">
        {{ queueRunning ? '队列运行中...' : '🚀 开始串行解析（' + pendingFiles.length + '张）' }}
      </button>
      <button v-if="!queueRunning" class="btn-secondary text-sm !px-3 !py-1.5" @click="clearAll">
        清空
      </button>
    </div>

    <!-- 队列进度 -->
    <div v-if="queueRunning || finishedCount > 0" class="card !p-3 mb-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-medium text-gray-600">
          {{ queueRunning ? '解析中' : '已完成' }}
        </span>
        <span class="text-xs text-gray-400">{{ finishedCount }}/{{ totalCount }}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div class="bg-primary-500 h-2 rounded-full transition-all duration-300"
             :style="{ width: totalCount > 0 ? (finishedCount / totalCount * 100) + '%' : '0%' }"></div>
      </div>
      <p v-if="currentProcessing" class="text-xs text-primary-600 mt-2 animate-pulse">
        📐 正在解析第 {{ finishedCount + 1 }}/{{ totalCount }} 张: {{ currentProcessing.name }}
      </p>
      <p v-if="queueError" class="text-xs text-red-500 mt-1">{{ queueError }}</p>
      <!-- 单步耗时 -->
      <p v-if="lastStepTime" class="text-[10px] text-gray-400 mt-0.5">上一步: {{ lastStepTime }}</p>
    </div>

    <!-- 结果列表 -->
    <div v-if="results.length > 0" class="space-y-2">
      <div v-for="(r, i) in results" :key="'r-'+i"
           class="card !p-3"
           :class="r.success ? 'border-green-200' : 'border-red-200'">
        <div class="flex items-start gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-800 truncate">{{ r.filename }}</span>
              <span :class="r.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                    class="text-xs px-1.5 py-0.5 rounded-full">
                {{ r.success ? '解析成功' : '失败' }}
              </span>
            </div>
            <div v-if="r.success" class="text-xs text-gray-500 mt-1 space-x-3">
              <span>{{ r.space_count }} 个空间</span>
              <span>{{ r.total_area }} ㎡</span>
              <span v-if="r.duration" class="text-gray-400">{{ r.duration }}</span>
            </div>
            <div v-else class="text-xs text-red-500 mt-1">{{ r.error }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import API from '../services/api.js'

const emit = defineEmits(['results-update', 'preview'])

const dragging = ref(false)
const input = ref(null)
const pendingFiles = ref([])
const queueRunning = ref(false)
const currentProcessing = ref(null)
const queueError = ref('')
const results = ref([])
const projectName = ref('装修工程')
const lastStepTime = ref('')

// 效果图相关
const imgDragging = ref(false)
const imgInput = ref(null)
const imageFiles = ref([])
const imgLightbox = ref({ show: false, url: '' })

function enlargeImg(url) {
  imgLightbox.value = { show: true, url }
}

function selectImgFile() { imgInput.value?.click() }
function onImgSelect(e) { addImgFiles(e.target.files) }
function onImgDrop(e) { imgDragging.value = false; addImgFiles(e.dataTransfer.files) }

function addImgFiles(fileList) {
  const allowed = ['jpg', 'jpeg', 'png', 'webp']
  for (const f of fileList) {
    const ext = f.name.split('.').pop().toLowerCase()
    if (!allowed.includes(ext)) continue
    const reader = new FileReader()
    reader.onload = (e) => {
      imageFiles.value.push({ file: f, preview: e.target.result })
    }
    reader.readAsDataURL(f)
  }
}

function removeImg(idx) {
  imageFiles.value.splice(idx, 1)
}

const finishedCount = computed(() => results.value.length)
const totalCount = computed(() => pendingFiles.value.length + results.value.length)

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}

function selectFile() { input.value?.click() }
function onSelect(e) { addFiles(e.target.files) }
function onDrop(e) { dragging.value = false; addFiles(e.dataTransfer.files) }

function addFiles(fileList) {
  if (queueRunning.value) return
  const allowed = ['dxf', 'dwg']
  for (const f of fileList) {
    const ext = f.name.split('.').pop().toLowerCase()
    if (!allowed.includes(ext)) continue
    if (pendingFiles.value.some(p => p.file.name === f.name && p.file.size === f.size)) continue
    if (results.value.some(r => r.filename === f.name)) continue
    pendingFiles.value.push({ file: f })
  }
}

function removePending(idx) {
  pendingFiles.value.splice(idx, 1)
}

function clearAll() {
  pendingFiles.value = []
  results.value = []
  queueError.value = ''
  lastStepTime.value = ''
}

function previewFile(file) {
  const reader = new FileReader()
  reader.onload = () => {
    emit('preview', { name: file.name, buffer: reader.result })
  }
  reader.onerror = () => {
    console.error('[CadBatchUploader] 文件读取失败:', file.name)
  }
  reader.readAsArrayBuffer(file)
}

async function startQueue() {
  if (queueRunning.value || pendingFiles.value.length === 0) return
  queueRunning.value = true
  queueError.value = ''
  lastStepTime.value = ''

  const files = [...pendingFiles.value]
  pendingFiles.value = []

  for (let i = 0; i < files.length; i++) {
    const item = files[i]
    currentProcessing.value = item.file

    try {
      const t0 = Date.now()
      const res = await API.analyzeCad(item.file, projectName.value)
      const dur = ((Date.now() - t0) / 1000).toFixed(1) + 's'
      lastStepTime.value = `${item.file.name}: ${dur}`

      const spaces = res.data?.spaces || res.data?.data?.spaces || []
      results.value.push({
        success: res.success,
        filename: item.file.name,
        space_count: res.data?.space_count || spaces.length || 0,
        total_area: res.data?.total_area ? Number(res.data.total_area).toFixed(1) : '-',
        duration: dur,
        error: res.message || '',
        result_data: res,
      })
    } catch (e) {
      results.value.push({
        success: false,
        filename: item.file.name,
        space_count: 0,
        total_area: '-',
        error: e.message || '未知错误',
      })
    }

    // 串行间隔，确保后端释放锁
    if (i < files.length - 1) {
      await new Promise(r => setTimeout(r, 800))
    }
  }

  currentProcessing.value = null
  queueRunning.value = false
  emit('results-update', results.value)
}
</script>
