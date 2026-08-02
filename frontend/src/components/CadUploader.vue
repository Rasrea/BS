<template>
  <div
    class="upload-zone min-h-[220px]"
    :class="{ active: dragging }"
    @dragover.prevent="dragging = true"
    @dragleave="dragging = false"
    @drop.prevent="onDrop"
    @click="selectFile"
  >
    <input ref="input" type="file" accept=".dxf,.dwg,.pdf" class="hidden" @change="onSelect" />
    <template v-if="!file">
      <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-blue-50 flex items-center justify-center">
        <svg class="w-7 h-7 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p class="text-sm font-medium text-gray-700">上传 CAD 图纸</p>
      <p class="text-xs text-gray-400 mt-1">支持 .dxf / .dwg / .pdf 格式</p>
      <p class="text-xs text-gray-400 mt-1">拖拽或点击选择文件</p>
    </template>
    <template v-else>
      <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-green-50 flex items-center justify-center">
        <svg class="w-7 h-7 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p class="text-sm font-medium text-green-700 break-all">{{ file.name }}</p>
      <p class="text-xs text-gray-400 mt-1">{{ formatSize(file.size) }}</p>
      <div class="flex items-center gap-2 mt-2">
        <button v-if="canAnnotate(file)" class="preview-btn" @click.stop="preview">标注</button>
        <span v-if="annotationCount" class="annotation-saved">已保存 {{ annotationCount }} 个区域</span>
        <span v-if="reviewHint" class="review-hint" :title="reviewReason || '建议核对自动识别区域'">建议人工复核</span>
        <button class="text-xs text-red-500 hover:text-red-700 underline" @click.stop="remove">移除</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { canAnnotate } from '../utils/annotationCapabilities.js'
defineProps({
  reviewHint: { type: Boolean, default: false },
  reviewReason: { type: String, default: '' },
  annotationCount: { type: Number, default: 0 },
})
const emit = defineEmits(['file-change', 'preview'])
const file = ref(null)
const dragging = ref(false)
const input = ref(null)

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}
function selectFile() { input.value?.click() }
function onSelect(e) {
  setFile(e.target.files[0])
  resetNativeInput()
}
function onDrop(e) { dragging.value = false; setFile(e.dataTransfer.files[0]) }
function resetNativeInput() {
  // 清空原生文件框的上次选择，保证再次选择同一个文件也会触发 change。
  if (input.value) input.value.value = ''
}
function setFile(f) {
  if (!f) return
  const ext = f.name.split('.').pop().toLowerCase()
  if (!['dxf', 'dwg', 'pdf'].includes(ext)) { alert('仅支持 .dxf / .dwg / .pdf 格式'); return }
  file.value = f
  emit('file-change', f)
}
function preview() {
  if (file.value) {
    const reader = new FileReader()
    reader.onload = (e) => {
      emit('preview', { name: file.value.name, buffer: e.target.result })
    }
    reader.readAsArrayBuffer(file.value)
  }
}
function remove() {
  file.value = null
  resetNativeInput()
  emit('file-change', null)
}

// Add preview button style
const style = document.createElement('style')
style.textContent = `
  .preview-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 14px;
    border: 1px solid #6366f1;
    border-radius: 8px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(99,102,241,0.25);
  }
  .preview-btn:hover {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(99,102,241,0.35);
  }
  .review-hint {
    color: #a16207;
    font-size: 11px;
    font-weight: 600;
  }
  .annotation-saved {
    color: #047857;
    font-size: 11px;
    font-weight: 600;
  }
`
document.head.appendChild(style)
</script>
