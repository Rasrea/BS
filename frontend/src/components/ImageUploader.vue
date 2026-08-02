<template>
  <div
    class="upload-zone min-h-[220px]"
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
      <div class="flex items-center gap-4 w-full">
        <div v-if="preview" class="relative w-32 h-28 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden group shrink-0">
          <button class="w-full h-full flex items-center justify-center" @click.stop="previewImage">
            <img :src="preview" class="max-w-full max-h-full object-contain" />
            <span class="absolute inset-0 hidden group-hover:flex items-center justify-center bg-black/35 text-xs text-white">
              预览大图
            </span>
          </button>
        </div>
        <div class="min-w-0 flex-1 text-left">
          <div class="flex items-center gap-2 mb-1">
            <span class="w-2 h-2 rounded-full bg-green-500 shrink-0"></span>
            <span class="text-xs font-medium text-green-700">已选择效果图</span>
          </div>
          <p class="text-sm font-medium text-gray-800 truncate" :title="file.name">{{ file.name }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ formatSize(file.size) }}</p>
          <div class="flex items-center gap-3 mt-3">
            <button class="text-xs text-primary-600 hover:text-primary-800 font-medium" @click.stop="previewImage">
              🔍 预览大图
            </button>
            <button class="text-xs text-red-500 hover:text-red-700" @click.stop="remove">移除</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['file-change', 'preview'])
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
  if (!['jpg', 'jpeg', 'png', 'webp'].includes(ext)) { alert('仅支持 jpg/png/webp 格式'); return }
  file.value = f
  const reader = new FileReader()
  reader.onload = e => { preview.value = e.target.result }
  reader.readAsDataURL(f)
  emit('file-change', f)
}
function remove() {
  file.value = null
  preview.value = null
  resetNativeInput()
  emit('file-change', null)
}
function previewImage() {
  if (preview.value) emit('preview', preview.value)
}
</script>
