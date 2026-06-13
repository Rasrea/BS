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
      <!-- 识别空间 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4" v-if="data.data.recognized_space">
        <div class="bg-blue-50 rounded-xl p-4">
          <p class="text-xs text-blue-600 mb-1">识别空间</p>
          <p class="text-base font-semibold text-blue-800">{{ data.data.recognized_space }}</p>
        </div>
        <div class="bg-purple-50 rounded-xl p-4">
          <p class="text-xs text-purple-600 mb-1">置信度</p>
          <div class="flex items-center gap-2">
            <div class="flex-1 bg-purple-200 rounded-full h-2">
              <div class="bg-purple-500 h-2 rounded-full" :style="{ width: (data.data.confidence * 100) + '%' }"></div>
            </div>
            <span class="text-sm font-semibold text-purple-700">{{ (data.data.confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- 材质信息 -->
      <div class="grid grid-cols-3 gap-3 mb-4">
        <div class="bg-white border border-gray-200 rounded-xl p-3" v-if="data.data.wall_material">
          <p class="text-[10px] text-gray-400 uppercase mb-1">墙面</p>
          <p class="text-sm font-medium text-gray-800">{{ data.data.wall_material }}</p>
        </div>
        <div class="bg-white border border-gray-200 rounded-xl p-3" v-if="data.data.floor_material">
          <p class="text-[10px] text-gray-400 uppercase mb-1">地面</p>
          <p class="text-sm font-medium text-gray-800">{{ data.data.floor_material }}</p>
        </div>
        <div class="bg-white border border-gray-200 rounded-xl p-3" v-if="data.data.ceiling_material">
          <p class="text-[10px] text-gray-400 uppercase mb-1">吊顶</p>
          <p class="text-sm font-medium text-gray-800">{{ data.data.ceiling_material }}</p>
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
