<template>
  <div
    class="upload-zone"
    :class="{ active: dragging }"
    @dragover.prevent="dragging = true"
    @dragleave="dragging = false"
    @drop.prevent="onDrop"
    @click="selectFile"
  >
    <input ref="input" type="file" accept=".jpg,.jpeg,.png,.webp" class="hidden" @change="onSelect" />
    <template v-if="!file">
      <div class="w-14 h-14 mx-auto mb-3 rounded-2xl bg-purple-50 flex items-center justify-center">
        <svg class="w-7 h-7 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <p class="text-sm font-medium text-gray-700">上传效果图</p>
      <p class="text-xs text-gray-400 mt-1">支持 .jpg / .png / .webp 格式</p>
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
      <div v-if="preview" class="mt-3">
        <img :src="preview" class="max-h-28 mx-auto rounded-lg shadow-sm border border-gray-200" />
      </div>
      <button class="mt-2 text-xs text-red-500 hover:text-red-700 underline" @click.stop="remove">移除</button>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['file-change'])
const file = ref(null)
const preview = ref(null)
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
  if (!['jpg', 'jpeg', 'png', 'webp', 'pdf'].includes(ext)) { alert('仅支持 jpg/png/webp/pdf 格式'); return }
  file.value = f
  const reader = new FileReader()
  reader.onload = e => { preview.value = e.target.result }
  reader.readAsDataURL(f)
  emit('file-change', f)
}
function remove() { file.value = null; preview.value = null; emit('file-change', null) }
</script>
