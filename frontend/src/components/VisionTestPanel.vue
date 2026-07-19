<template>
  <div>
    <div class="card mb-4">
      <h3 class="text-sm font-semibold text-gray-700 mb-3">🔬 视觉模型独立测试</h3>
      <p class="text-xs text-gray-500 mb-3">
        上传一张或多张效果图 → 选择模型 → 批量测试 → 查看各步骤耗时 + 原始响应。
        不经过数据库、不经过融合流程，纯诊断用途，方便对比不同模型效果。
      </p>

      <!-- 模型选择，云端调用和裁剪开关 -->
      <div class="flex flex-col gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
        <!-- 第一行：模型选择 + 环境切换（紧邻） -->
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-gray-500 whitespace-nowrap">🧠 测试模型:</span>
          <select v-model="selectedModel" class="border border-gray-300 rounded-lg px-2 py-1 text-xs bg-white min-w-0 max-w-[160px]">
            <option v-for="m in filteredModels" :key="m.key" :value="m.key" :disabled="!m.installed">
              {{ m.label }}{{ !m.installed ? ' (未安装)' : '' }}
            </option>
          </select>

          <!-- 环境切换开关 — 紧跟在模型选择后面 -->
          <div class="flex items-center gap-1.5 pl-2 border-l border-gray-200 shrink-0">
            <span class="text-[10px]" :class="useCloud ? 'text-gray-300' : 'text-gray-500 font-medium'">本地</span>
            <button
              @click="toggleEnv"
              class="relative inline-flex h-4 w-7 items-center rounded-full transition-colors focus:outline-none"
              :class="useCloud ? 'bg-blue-500' : 'bg-gray-300'"
            >
              <span
                class="inline-block h-3 w-3 transform rounded-full bg-white transition-transform"
                :class="useCloud ? 'translate-x-3.5' : 'translate-x-0.5'"
              />
            </button>
            <span class="text-[10px]" :class="useCloud ? 'text-blue-600 font-medium' : 'text-gray-300'">云端</span>
          </div>

          <span v-if="activeModel === selectedModel" class="text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded whitespace-nowrap">系统当前在用</span>
          <span v-else class="text-[10px] text-gray-400 whitespace-nowrap">仅测试用</span>
        </div>

        <!-- 第二行：裁剪开关 -->
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-gray-500 whitespace-nowrap">✂️ 分区域裁剪:</span>
          <button
            @click="cropEnabled = !cropEnabled"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0"
            :class="cropEnabled ? 'bg-primary-500' : 'bg-gray-300'"
          >
            <span class="sr-only">切换裁剪识别</span>
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
              :class="cropEnabled ? 'translate-x-5' : 'translate-x-0.5'"
            />
          </button>
          <span class="text-[10px] shrink-0" :class="cropEnabled ? 'text-green-600 bg-green-50' : 'text-gray-400 bg-gray-100'">
            {{ cropEnabled ? '启用' : '关闭' }}
          </span>
          <span class="text-[10px] text-gray-400">将图像分为天花板/墙面/地面分别识别</span>
        </div>
      </div>

      <!-- 上传区域 -->
      <div class="mb-4">
        <label class="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 text-sm font-medium">
          📁 选择图片（可多选）
          <input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="onFilesChange" class="hidden" />
        </label>
        <span class="text-xs text-gray-400 ml-3">支持多选，按顺序逐个测试</span>
      </div>

      <!-- 图片预览区 -->
      <div v-if="files.length > 0" class="mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-medium text-gray-600">已选 {{ files.length }} 张图片</span>
          <button class="text-xs text-red-500 hover:text-red-700" @click="clearAll">清空全部</button>
        </div>
        <div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          <div v-for="(f, i) in files" :key="f.name + i"
               class="relative group border rounded-lg overflow-hidden cursor-pointer"
               :class="{'ring-2 ring-primary-500': previewIndex === i, 'border-gray-200': previewIndex !== i, 'opacity-50': f.done || f.failed}"
               @click="previewIndex = i">
            <img :src="f.url" class="w-full h-20 object-cover" />
            <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-1 py-0.5">
              <span class="text-[9px] text-white truncate block">{{ f.name }}</span>
            </div>
            <!-- 状态标记 -->
            <div v-if="f.done" class="absolute top-1 right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
              <svg class="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
            </div>
            <div v-if="f.failed" class="absolute top-1 right-1 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center">
              <span class="text-[9px] text-white">!</span>
            </div>
            <div v-if="f.testing" class="absolute inset-0 bg-black/30 flex items-center justify-center">
              <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 大图预览 -->
      <div v-if="files.length > 0" class="card mb-4 p-0 overflow-hidden">
        <img :src="files[previewIndex]?.url" class="w-full max-h-64 object-contain bg-gray-100" />
        <div class="p-2 flex items-center justify-between bg-gray-50 border-t border-gray-200">
          <span class="text-xs text-gray-500 truncate">{{ files[previewIndex]?.name }}</span>
          <div class="flex items-center gap-2">
            <button v-if="previewIndex > 0" class="text-xs text-primary-600 hover:text-primary-800" @click="previewIndex--">◀ 上一张</button>
            <span class="text-[10px] text-gray-400">{{ previewIndex + 1 }}/{{ files.length }}</span>
            <button v-if="previewIndex < files.length - 1" class="text-xs text-primary-600 hover:text-primary-800" @click="previewIndex++">下一张 ▶</button>
          </div>
        </div>
      </div>

      <!-- 按钮 -->
      <div class="flex items-center gap-3 mb-4">
        <button class="btn-primary" :disabled="files.length === 0 || testing" @click="startBatchTest">
          <svg v-if="testing" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ testing ? `测试中 ${doneCount}/${files.length}...` : '🚀 批量测试' }}
        </button>
        <span v-if="testing" class="text-xs text-primary-600 animate-pulse">{{ testEnvStatus }}</span>
      </div>

      <!-- 进度条 -->
      <div v-if="testing && files.length > 1" class="mb-4">
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div class="bg-primary-500 h-2 rounded-full transition-all duration-300" :style="{width: (doneCount/files.length*100)+'%'}"></div>
        </div>
        <div class="text-[10px] text-gray-400 mt-1 text-right">{{ doneCount }}/{{ files.length }} 完成</div>
      </div>
    </div>

    <!-- 汇总结果 -->
    <div v-if="results.length > 0" class="space-y-3">
      <!-- 汇总表 -->
      <div class="card">
        <h4 class="text-xs font-semibold text-gray-600 mb-2">📊 测试汇总（{{ selectedModel }}）</h4>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="bg-gray-50">
                <th class="text-left py-1.5 px-2 font-medium text-gray-500">图片</th>
                <th class="text-center py-1.5 px-2 font-medium text-gray-500">耗时</th>
                <th class="text-center py-1.5 px-2 font-medium text-gray-500">空间</th>
                <th class="text-center py-1.5 px-2 font-medium text-gray-500">墙面</th>
                <th class="text-center py-1.5 px-2 font-medium text-gray-500">地面</th>
                <th class="text-center py-1.5 px-2 font-medium text-gray-500">顶面</th>
                <th class="text-center py-1.5 px-2 font-medium text-gray-500">相似度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in results" :key="i" class="border-t border-gray-100"
                  :class="{'bg-red-50': !r.success}">
                <td class="py-1.5 px-2 text-gray-700 truncate max-w-[120px]">{{ r.filename }}</td>
                <td class="py-1.5 px-2 text-center" :class="timingColor(r.total)">{{ r.total }}s</td>
                <td class="py-1.5 px-2 text-center">{{ r.space || '-' }}</td>
                <td class="py-1.5 px-2 text-center">{{ r.wall || '-' }}</td>
                <td class="py-1.5 px-2 text-center">{{ r.floor || '-' }}</td>
                <td class="py-1.5 px-2 text-center">{{ r.ceiling || '-' }}</td>
                <td class="py-1.5 px-2 text-center">
                  <span :class="similarityColor(r.similarity)">
                    {{ r.similarity || '-' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 在统计汇总卡片之前添加 -->
      <div v-if="results.length > 0" class="flex items-center justify-end gap-2 mb-2">
        <button 
          class="text-xs px-3 py-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
          @click="exportResults('csv')"
        >
          📥 导出 CSV
        </button>
        <button 
          class="text-xs px-3 py-1.5 bg-green-50 text-green-600 rounded hover:bg-green-100 transition-colors"
          @click="exportResults('json')"
        >
          📥 导出 JSON
        </button>
      </div>

      <!-- 统计汇总 -->
      <div v-if="results.length > 0" class="card mb-3">
        <h4 class="text-xs font-semibold text-gray-600 mb-2">⏱️ 性能统计（{{ selectedModel }}）</h4>
        <div class="grid grid-cols-4 gap-2">
          <div class="text-center p-2 bg-blue-50 rounded">
            <div class="text-lg font-bold text-blue-700">{{ stats.totalTime }}s</div>
            <div class="text-[9px] text-gray-500">总耗时</div>
          </div>
          <div class="text-center p-2 bg-green-50 rounded">
            <div class="text-lg font-bold text-green-700">{{ stats.avgTime }}s</div>
            <div class="text-[9px] text-gray-500">平均耗时</div>
          </div>
          <div class="text-center p-2 bg-purple-50 rounded">
            <div class="text-lg font-bold text-purple-700">{{ stats.testCount }}</div>
            <div class="text-[9px] text-gray-500">测试数量</div>
          </div>
          <div class="text-center p-2 bg-orange-50 rounded">
            <div class="text-lg font-bold text-orange-700">{{ stats.avgSimilarity }}%</div>
            <div class="text-[9px] text-gray-500">平均相似度</div>
          </div>
        </div>
      </div>


      <!-- 各图详情（折叠） -->
      <div v-for="(r, i) in results" :key="'detail-'+i" class="card">
        <div class="flex items-center justify-between cursor-pointer" @click="r.expanded = !r.expanded">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-gray-700">{{ i+1 }}. {{ r.filename }}</span>
            <span class="text-[10px]" :class="r.success ? 'text-green-600' : 'text-red-600'">
              {{ r.success ? `${r.total}s` : '失败' }}
            </span>
          </div>
          <svg class="w-3 h-3 text-gray-400 transition-transform" :class="{'rotate-180': r.expanded}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </div>

        <div v-if="r.expanded" class="mt-3 space-y-2 border-t border-gray-100 pt-3">
          <!-- 缩略图 -->
          <img :src="r.fileUrl" class="w-full max-h-32 object-contain bg-gray-50 rounded" />

          <!-- 计时 -->
          <div class="grid grid-cols-3 gap-2 text-center">
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-sm font-bold" :class="timingColor(r.timings?.preprocess || 0)">{{ (r.timings?.preprocess || 0) }}s</div>
              <div class="text-[9px] text-gray-400">预处理</div>
            </div>
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-sm font-bold" :class="timingColor(r.timings?.inference || 0)">{{ (r.timings?.inference || 0) }}s</div>
              <div class="text-[9px] text-gray-400">推理</div>
            </div>
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-sm font-bold" :class="timingColor(r.total)">{{ r.total }}s</div>
              <div class="text-[9px] text-gray-400">总耗时</div>
            </div>
          </div>

          <!-- 识别结果 -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-1.5">
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-[9px] text-gray-400">空间</div>
              <div class="text-xs font-medium">{{ r.space || '-' }}</div>
            </div>
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-[9px] text-gray-400">墙面</div>
              <div class="text-xs font-medium">{{ r.wall || '-' }}</div>
            </div>
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-[9px] text-gray-400">地面</div>
              <div class="text-xs font-medium">{{ r.floor || '-' }}</div>
            </div>
            <div class="p-1.5 bg-gray-50 rounded">
              <div class="text-[9px] text-gray-400">顶面</div>
              <div class="text-xs font-medium">{{ r.ceiling || '-' }}</div>
            </div>
          </div>

          <!-- 原始响应 -->
          <button class="text-[10px] text-primary-600 hover:text-primary-800" @click.stop="r.showRaw = !r.showRaw">
            {{ r.showRaw ? '收起原始响应' : '展开原始响应' }}
          </button>
          <pre v-if="r.showRaw" class="text-[10px] bg-gray-900 text-green-300 p-2 rounded overflow-x-auto max-h-40 overflow-y-auto">{{ JSON.stringify(r.rawData, null, 2) }}</pre>
        </div>
      </div>

      <!-- 多模型对比提示 -->
      <div class="card border-l-4 border-primary-400 bg-primary-50/30">
        <p class="text-xs text-primary-700">
          💡 换一个模型试试？下拉选其他模型 → 重新点「批量测试」，对比不同模型的耗时和识别效果。
        </p>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="files.length === 0 && results.length === 0" class="card text-center text-gray-400 py-8">
      <p class="text-4xl mb-3">🧪</p>
      <p class="text-sm">选择一张或多张效果图，测试视觉模型识别效果</p>
      <p class="text-xs mt-2">不写数据库、不走融合流程、纯模型诊断 + 对比</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import API from '../services/api.js'

const files = ref([])
const testing = ref(false)
const results = ref([])
const previewIndex = ref(0)
const selectedModel = ref('qwen2.5:7b')
const activeModel = ref('')
const availableModels = ref([])// 这个现在存的是后端返回的全量列表
const doneCount = ref(0)

// ========== 新增：环境切换状态 ==========
// 默认使用本地模型（false），切换云端为 true
const useCloud = ref(false)

// 计算属性：根据开关状态过滤模型列表
const filteredModels = computed(() => {
  return availableModels.value.filter(m => {
    // 判断是否为云端模型（你的后端逻辑是 dashscope: 开头）
    const isCloudModel = m.key.startsWith('dashscope:')
    // 如果开关是云端，只返回云端模型；否则只返回本地模型
    return useCloud.value ? isCloudModel : !isCloudModel
  })
})

// 切换环境的方法
function toggleEnv() {
  useCloud.value = !useCloud.value

  // 切换后，自动选中当前列表里的第一个可用模型
  const targetList = filteredModels.value
  if (targetList.length > 0) {
    // 优先选已安装的
    const installed = targetList.find(m => m.installed)
    selectedModel.value = installed ? installed.key : targetList[0].key
  }
}

// 顺便优化一下状态文本，区分本地和云端
const testEnvStatus = computed(() => {
  if (!testing.value) return ''
  const env = useCloud.value ? '云端' : '本地'
  const done = doneCount.value
  const total = files.value.length
  const current = files.value.find(f => f.testing)
  return `${env}测试 ${done + 1}/${total}: ${current?.name || '...'}`
})
// ========== 新增结束 ==========
const cropEnabled = ref(true)  // 默认开启裁剪识别

const stats = computed(() => {
  const successful = results.value.filter(r => r.success)
  if (successful.length === 0) {
    return { totalTime: '0.00', avgTime: '0.00', testCount: 0 }
  }
  
  // 计算总时间
  const totalSec = successful.reduce((sum, r) => sum + r.total, 0)
  
  // 去除最大值和最小值后计算平均
  const times = successful.map(r => r.total).sort((a, b) => a - b)
  let trimmedTimes = times
  
  if (times.length > 2) {
    trimmedTimes = times.slice(1, -1) // 去掉第一个（最小）和最后一个（最大）
  }
  
  const avgSec = trimmedTimes.length > 0 
    ? trimmedTimes.reduce((sum, t) => sum + t, 0) / trimmedTimes.length 
    : 0

  // 计算平均相似度（去除极值）
  const similarities = successful
    .map(r => {
      const sim = r.similarity
      if (!sim) return null
      const num = typeof sim === 'string' ? parseFloat(sim) : sim
      return isNaN(num) ? null : num
    })
    .filter(s => s !== null)
  
  let avgSimStr = '0.00'
  if (similarities.length > 0) {
    const sortedSims = similarities.sort((a, b) => a - b)
    let trimmedSims = sortedSims
    
    if (sortedSims.length > 2) {
      trimmedSims = sortedSims.slice(1, -1)
    }
    
    if (trimmedSims.length > 0) {
      const avgSim = trimmedSims.reduce((sum, s) => sum + s, 0) / trimmedSims.length
      avgSimStr = avgSim.toFixed(2)
    }
  }
  
  return {
    totalTime: totalSec.toFixed(2),
    avgTime: avgSec.toFixed(2),
    testCount: successful.length,
    avgSimilarity: avgSimStr
  }
})

const statusText = computed(() => {
  if (!testing.value) return ''
  const done = doneCount.value
  const total = files.value.length
  const current = files.value.find(f => f.testing)
  return `第 ${done + 1}/${total} 张: ${current?.name || '...'}`
})

onMounted(async () => {
  const res = await API.get('/settings/vl_model')
  if (res.success && res.data) {
    activeModel.value = res.data.active_model
    selectedModel.value = res.data.active_model
    availableModels.value = res.data.available_models || []
  // 【可选优化】根据当前系统模型，初始化开关状态
    // 如果系统正在用云端模型，开关就拨到云端
    if (res.data.active_model?.startsWith('dashscope:')) {
      useCloud.value = true
    }
  }
})

function onFilesChange(e) {
  const newFiles = Array.from(e.target.files || [])
  for (const f of newFiles) {
    files.value.push({
      file: f,
      name: f.name,
      url: URL.createObjectURL(f),
      done: false,
      failed: false,
      testing: false,
    })
  }
  previewIndex.value = 0
  results.value = []
  e.target.value = ''
}

function clearAll() {
  files.value.forEach(f => URL.revokeObjectURL(f.url))
  files.value = []
  results.value = []
  previewIndex.value = 0
}

function timingColor(sec) {
  if (sec < 7) return 'text-green-600'
  if (sec < 10) return 'text-yellow-600'
  return 'text-red-600'
}

// 根据相似度高低显示不同颜色
function similarityColor(sim) {
  if (!sim) return 'text-gray-400'
  // 如果是字符串格式（如 "85.0%"），先提取数字
  const num = typeof sim === 'string' ? parseFloat(sim) : sim
  if (num >= 70) return 'text-green-600 font-semibold'
  if (num >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

/**
 * 导出测试结果
 * @param {'csv'|'json'} format - 导出格式
 */
function exportResults(format = 'csv') {
  if (results.value.length === 0) {
    alert('没有可导出的测试结果')
    return
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  const filename = `vision_test_${selectedModel.value}_${timestamp}`

  if (format === 'csv') {
    exportAsCSV(results.value, filename)
  } else if (format === 'json') {
    exportAsJSON(results.value, stats.value, filename)
  }
}

/**
 * 导出为 CSV 格式
 */
function exportAsCSV(results, filename) {
  // CSV 表头
  const headers = [
    '序号',
    '文件名',
    '总耗时(s)',
    '预处理耗时(s)',
    '推理耗时(s)',
    '空间类型',
    '墙面材料',
    '地面材料',
    '顶面材料',
    '相似度',
    '测试结果'
  ]

  // 转换结果为 CSV 行
  const rows = results.map((r, i) => [
    i + 1,
    `"${r.filename}"`,  // 用引号包裹，防止逗号问题
    r.total,
    r.timings?.preprocess || 0,
    r.timings?.inference || 0,
    `"${r.space || '-'}"`,
    `"${r.wall || '-'}"`,
    `"${r.floor || '-'}"`,
    `"${r.ceiling || '-'}"`,
    `"${r.similarity || '-'}"`,
    r.success ? '成功' : '失败'
  ])

  // 组合 CSV 内容
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n')

  // 添加 BOM 以支持 Excel 正确显示中文
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  downloadFile(blob, `${filename}.csv`)
}

/**
 * 导出为 JSON 格式
 */
function exportAsJSON(results, statsData, filename) {
  const exportData = {
    exportTime: new Date().toISOString(),
    model: selectedModel.value,
    statistics: statsData,
    results: results.map(r => ({
      filename: r.filename,
      total: r.total,
      timings: r.timings,
      space: r.space,
      wall: r.wall,
      floor: r.floor,
      ceiling: r.ceiling,
      similarity: r.similarity,
      success: r.success,
      rawData: r.rawData
    }))
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  downloadFile(blob, `${filename}.json`)
}

/**
 * 下载文件
 */
function downloadFile(blob, filename) {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

async function startBatchTest() {
  if (files.value.length === 0) return
  testing.value = true
  results.value = []
  doneCount.value = 0

  for (const f of files.value) {
    f.done = false
    f.failed = false
    f.testing = true
    f.showRaw = false
    f.expanded = false

    const fd = new FormData()
    fd.append('image_file', f.file)
    fd.append('model', selectedModel.value)
    fd.append('crop_enabled', cropEnabled.value)  // 裁剪开关
    const res = await API.post('/vision_test', fd)

    const entry = {
      filename: f.name,
      fileUrl: f.url,
      success: false,
      total: 0,
      timings: { preprocess: 0, inference: 0 },
      space: '-',
      wall: '-',
      floor: '-',
      ceiling: '-',
      rawData: null,
      expanded: false,
      showRaw: false,
    }

    if (res.success && res.data) {
      const d = res.data
      entry.success = d.raw_result?.success !== false
      entry.total = d.timings?.total || 0
      entry.timings = d.timings || { preprocess: 0, inference: 0 }
      entry.rawData = d.raw_result
      const sr = d.raw_result?.structured
      if (sr) {
        entry.space = sr.space_type || '-'
        entry.wall = sr.wall_material || '-'
        entry.floor = sr.floor_material || '-'
        entry.ceiling = sr.ceiling_material || '-'
      }
      entry.success = !!sr
      entry.similarity = d.similarity ? (d.similarity.overall_similarity * 100).toFixed(1) + '%' : null

    } else {
      entry.rawData = { error: res.message || '请求失败' }
    }

    results.value.push(entry)
    f.done = entry.success
    f.failed = !entry.success
    f.testing = false
    doneCount.value++
  }

  testing.value = false
}
</script>
