<template>
  <div
    class="upload-zone"
    :class="{ active: dragging }"
    @dragover.prevent="dragging = true"
    @dragleave="dragging = false"
    @drop.prevent="onDrop"
    @click="selectFile"
  >
    <input ref="input" type="file" accept=".dxf,.dwg" class="hidden" @change="onSelect" />
    <template v-if="!file">
      <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-blue-50 flex items-center justify-center">
        <svg class="w-7 h-7 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p class="text-sm font-medium text-gray-700">上传 CAD 图纸</p>
      <p class="text-xs text-gray-400 mt-1">仅支持 .dxf / .dwg 格式</p>
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
      <button class="mt-2 text-xs text-red-500 hover:text-red-700 underline" @click.stop="remove">移除</button>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['file-change'])
const file = ref(null)
const dragging = ref(false)
const input = ref(null)

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(2) + ' MB'
}
function selectFile() { input.value?.click() }
function onSelect(e) { setFile(e.target.files[0]) }
function onDrop(e) { dragging.value = false; setFile(e.dataTransfer.files[0]) }
function setFile(f) {
  if (!f) return
  const ext = f.name.split('.').pop().toLowerCase()
  if (!['dxf', 'dwg'].includes(ext)) { alert('仅支持 .dxf / .dwg 格式'); return }
  file.value = f
  emit('file-change', f)
}
function remove() { file.value = null; emit('file-change', null) }
</script>
