<template>
  <div>
    <div class="card mb-4">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">🔬 视觉模型独立测试</h3>
      <p class="text-xs text-gray-500 mb-3">
        上传一张效果图 → 直接调用视觉模型 → 查看各步骤耗时 + 原始响应。
        不经过数据库、不经过融合流程，纯诊断用途。
      </p>

      <!-- 上传 -->
      <div class="flex items-center gap-4 mb-4">
        <label class="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 text-sm font-medium">
          📁 选择图片
          <input type="file" accept="image/jpeg,image/png,image/webp" @change="onFileChange" class="hidden" />
        </label>
        <span v-if="file" class="text-sm text-gray-600">{{ file.name }}</span>
      </div>

      <!-- 按钮 -->
      <div class="flex items-center gap-3 mb-4">
        <button class="btn-primary" :disabled="!file || testing" @click="startTest">
          <svg v-if="testing" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ testing ? '测试中...' : '🚀 开始测试' }}
        </button>
        <span v-if="testing" class="text-xs text-primary-600 animate-pulse">⏱ 正在调用模型...</span>
      </div>

      <!-- 进度指示器 -->
      <div v-if="testing" class="mb-4">
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-primary-400 animate-pulse"></div>
          <span class="text-xs text-gray-500">预处理 → 模型推理 → 解析中...</span>
        </div>
      </div>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="space-y-3">
      <!-- 计时信息 -->
      <div class="card">
        <h4 class="text-xs font-semibold text-gray-600 mb-2">⏱ 耗时</h4>
        <div class="grid grid-cols-3 gap-3 text-center">
          <div class="p-2 bg-gray-50 rounded">
            <div class="text-lg font-bold" :class="timingColor(result.timings.preprocess)">{{ result.timings.preprocess }}s</div>
            <div class="text-[10px] text-gray-400">预处理</div>
          </div>
          <div class="p-2 bg-gray-50 rounded">
            <div class="text-lg font-bold" :class="timingColor(result.timings.inference)">{{ result.timings.inference }}s</div>
            <div class="text-[10px] text-gray-400">模型推理</div>
          </div>
          <div class="p-2 bg-gray-50 rounded">
            <div class="text-lg font-bold" :class="timingColor(result.timings.total)">{{ result.timings.total }}s</div>
            <div class="text-[10px] text-gray-400">总耗时</div>
          </div>
        </div>
      </div>

      <!-- 图片信息 -->
      <div class="card">
        <h4 class="text-xs font-semibold text-gray-600 mb-2">🖼️ 图片信息</h4>
        <div class="text-xs text-gray-600 space-y-1">
          <p>文件名: {{ result.image_info.filename }}</p>
          <p>原图: {{ result.image_info.original_size_kb }} KB → 压缩后: {{ result.image_info.processed_size_kb }} KB</p>
          <p>当前模型: <span class="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{{ result.model_used }}</span></p>
        </div>
      </div>

      <!-- 识别结果 -->
      <div class="card">
        <h4 class="text-xs font-semibold text-gray-600 mb-2">🎯 识别结果</h4>
        <div v-if="result.raw_result" class="space-y-2">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div class="p-2 bg-gray-50 rounded">
              <div class="text-[10px] text-gray-400">空间</div>
              <div class="text-sm font-medium">{{ result.raw_result.structured?.space_type || result.raw_result.spaces?.[0]?.type || '-' }}</div>
            </div>
            <div class="p-2 bg-gray-50 rounded">
              <div class="text-[10px] text-gray-400">墙面</div>
              <div class="text-sm font-medium">{{ result.raw_result.structured?.wall_material || '-' }}</div>
            </div>
            <div class="p-2 bg-gray-50 rounded">
              <div class="text-[10px] text-gray-400">地面</div>
              <div class="text-sm font-medium">{{ result.raw_result.structured?.floor_material || '-' }}</div>
            </div>
            <div class="p-2 bg-gray-50 rounded">
              <div class="text-[10px] text-gray-400">顶面</div>
              <div class="text-sm font-medium">{{ result.raw_result.structured?.ceiling_material || '-' }}</div>
            </div>
          </div>
          <div v-if="result.raw_result.success === false" class="mt-2 p-2 bg-red-50 rounded text-xs text-red-600">
            ⚠️ 识别失败: {{ result.raw_result.error || '未知错误' }}
          </div>
        </div>
      </div>

      <!-- 原始模型响应 -->
      <div class="card">
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-xs font-semibold text-gray-600">📄 原始模型响应</h4>
          <button class="text-xs text-primary-600 hover:text-primary-800" @click="showRaw = !showRaw">
            {{ showRaw ? '收起' : '展开' }}
          </button>
        </div>
        <pre v-if="showRaw" class="text-xs bg-gray-900 text-green-300 p-3 rounded overflow-x-auto max-h-80 overflow-y-auto">{{ JSON.stringify(result.raw_result, null, 2) }}</pre>
      </div>

      <!-- 故障诊断 -->
      <div v-if="result.timings.total > 5" class="card border-l-4 border-yellow-400">
        <h4 class="text-xs font-semibold text-yellow-700 mb-1">⚠️ 诊断提示</h4>
        <ul class="text-xs text-yellow-600 space-y-1 list-disc list-inside">
          <li v-if="result.timings.preprocess > 2">预处理耗时过长（>2s），图片可能过大</li>
          <li v-if="result.timings.inference > 10">模型推理耗时过长（>10s），检查 Ollama 服务状态</li>
          <li v-if="result.timings.total > 20">总耗时超过20s，建议检查网络/模型负载</li>
        </ul>
      </div>
      <div v-if="!result.raw_result?.success" class="card border-l-4 border-red-400">
        <h4 class="text-xs font-semibold text-red-700 mb-1">❌ 识别失败 - 可能原因</h4>
        <ul class="text-xs text-red-600 space-y-1 list-disc list-inside">
          <li>Ollama 服务未运行 → 终端执行 <code class="bg-red-100 px-1 rounded">ollama serve</code></li>
          <li>模型未安装 → 终端执行 <code class="bg-red-100 px-1 rounded">ollama pull {{ result.model_used }}</code></li>
          <li>Ollama 端口非 11434 → 检查 <code class="bg-red-100 px-1 rounded">curl localhost:11434</code></li>
          <li>图片格式/大小异常</li>
        </ul>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!file && !result" class="card text-center text-gray-400 py-8">
      <p class="text-4xl mb-3">🧪</p>
      <p class="text-sm">选择一张效果图，测试视觉模型能否正常识别</p>
      <p class="text-xs mt-2">不写数据库、不走融合流程、纯模型诊断</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import API from '../services/api.js'

const file = ref(null)
const testing = ref(false)
const result = ref(null)
const showRaw = ref(false)

function onFileChange(e) {
  file.value = e.target.files[0] || null
  result.value = null
  showRaw.value = false
}

function timingColor(sec) {
  if (sec < 2) return 'text-green-600'
  if (sec < 10) return 'text-yellow-600'
  return 'text-red-600'
}

async function startTest() {
  if (!file.value) return
  testing.value = true
  result.value = null
  showRaw.value = false

  const fd = new FormData()
  fd.append('image_file', file.value)
  const res = await API.post('/vision_test', fd)
  if (res.success && res.data) {
    result.value = res.data
  } else {
    result.value = {
      timings: { preprocess: 0, inference: 0, total: 0 },
      model_used: 'unknown',
      image_info: { filename: file.value.name, original_size_kb: 0, processed_size_kb: 0 },
      raw_result: { success: false, error: res.message || '请求失败' },
    }
  }
  testing.value = false
}
</script>
