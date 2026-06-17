<template>
  <Teleport to="body">
    <div v-if="visible"
         class="fixed inset-0 z-[9999] flex items-center justify-center"
         @click.self="$emit('cancel')">
      <!-- 背景遮罩 -->
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm"></div>
      <!-- 弹窗 -->
      <div class="relative bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-sm mx-4 p-6 animate-confirm-in">
        <!-- 图标 -->
        <div class="mx-auto w-12 h-12 flex items-center justify-center rounded-full bg-red-50 mb-4">
          <svg class="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <!-- 标题 -->
        <h3 class="text-center text-base font-semibold text-gray-800 mb-2">{{ title }}</h3>
        <!-- 消息 -->
        <p class="text-center text-sm text-gray-500 mb-6">{{ message }}</p>
        <!-- 按钮 -->
        <div class="flex gap-3">
          <button @click="$emit('cancel')"
                  class="flex-1 px-4 py-2.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-xl
                         hover:bg-gray-200 transition-colors">
            取消
          </button>
          <button @click="$emit('confirm')"
                  class="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-500 rounded-xl
                         hover:bg-red-600 transition-colors shadow-sm">
            确认删除
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '确认删除' },
  message: { type: String, default: '此操作不可撤销，确定要删除吗？' },
})

defineEmits(['confirm', 'cancel'])
</script>

<style scoped>
.animate-confirm-in {
  animation: confirm-pop 0.2s ease-out;
}
@keyframes confirm-pop {
  from {
    opacity: 0;
    transform: scale(0.92);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
