<template>
  <div class="card mb-6" v-if="data">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
        <span>🖼️</span> 效果图识别结果
      </h3>
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">{{ data.data?.filename || '' }}</span>
        <span class="px-2.5 py-1 text-xs font-medium rounded-full"
          :class="data.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
          {{ data.success ? '识别成功' : '识别失败' }}
        </span>
      </div>
    </div>

    <div v-if="!data.success" class="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
      {{ data.message || data.error }}
    </div>

    <template v-if="data.success && data.data">
      <!-- 识别结果 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-1.5 mb-4">
        <div class="p-1.5 bg-gray-50 rounded">
          <div class="text-[9px] text-gray-400">空间</div>
          <div class="text-xs font-medium">{{ data.data.recognized_space || '-' }}</div>
        </div>
        <div class="p-1.5 bg-gray-50 rounded">
          <div class="text-[9px] text-gray-400">墙面</div>
          <div class="text-xs font-medium">{{ data.data.wall_material || '-' }}</div>
        </div>
        <div class="p-1.5 bg-gray-50 rounded">
          <div class="text-[9px] text-gray-400">地面</div>
          <div class="text-xs font-medium">{{ data.data.floor_material || '-' }}</div>
        </div>
        <div class="p-1.5 bg-gray-50 rounded">
          <div class="text-[9px] text-gray-400">顶面</div>
          <div class="text-xs font-medium">{{ data.data.ceiling_material || '-' }}</div>
        </div>
      </div>
      <div v-if="data.data.other" class="p-3 bg-gray-50 rounded-xl mb-3">
        <p class="text-xs text-gray-500">其他描述</p>
        <p class="text-sm text-gray-700 mt-1">{{ data.data.other }}</p>
      </div>

      <!-- image_result_id -->
      <p class="text-xs text-gray-400 mt-2">结果ID: {{ data.data.image_result_id }}</p>
    </template>
  </div>
</template>

<script setup>
defineProps({ data: Object })
</script>
