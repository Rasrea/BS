<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
    <!-- Header -->
    <header class="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <div>
              <h1 class="text-lg font-bold text-gray-900">家装智能报价系统</h1>
              <p class="text-[10px] text-gray-500">CAD解析 · AI识别 · 数据融合 · 自动报价</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              :class="statusClass">
              <span class="w-1.5 h-1.5 rounded-full" :class="statusDotClass"></span>
              {{ statusText }}
            </span>
            <span class="text-xs text-gray-400">v2.1</span>
          </div>
        </div>
      </div>
    </header>

    <!-- Tabs -->
    <div class="border-b border-gray-200 bg-white/60">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex overflow-x-auto">
          <button v-for="tab in tabs" :key="tab.key"
                  @click="activeTab = tab.key"
                  class="px-5 py-3 text-sm font-medium whitespace-nowrap transition-colors relative"
                  :class="activeTab === tab.key
                    ? 'text-primary-700'
                    : 'text-gray-500 hover:text-gray-700'">
            {{ tab.label }}
            <span v-if="activeTab === tab.key"
                  class="absolute bottom-0 left-3 right-3 h-0.5 bg-primary-600 rounded-full"></span>
          </button>
        </div>
      </div>
    </div>

    <!-- Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <!-- Tab 1: 首页 - 上传与解析 -->
      <div v-show="activeTab === 'home'">
        <!-- 项目名称 -->
        <div class="card mb-4">
          <label class="text-xs text-gray-500 block mb-1">项目名称</label>
          <input v-model="projectName" placeholder="装修工程"
                 class="w-full max-w-xs border border-gray-300 rounded-lg px-3 py-2 text-sm" />
        </div>

        <!-- 上传选择 -->
        <div class="flex items-center gap-2 mb-3">
          <button @click="uploadMode='single'" class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
            :class="uploadMode==='single' ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'">
            单张上传
          </button>
          <button @click="uploadMode='multi'" class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
            :class="uploadMode==='multi' ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'">
            多张队列
          </button>
        </div>

        <!-- 双上传区 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <CadUploader @file-change="onCadFileChange" />
          <ImageUploader v-if="uploadMode==='single'" @file-change="onImageFileChange" />
          <ImageQueue v-else @results-update="onQueueResults" />
        </div>

        <!-- 操作按钮区 -->
        <div class="card mb-4">
          <div class="flex items-center gap-4 flex-wrap">
            <button class="btn-primary" :disabled="!(cadFile || imageFile) || loading"
                    @click="startAnalysis">
              <svg v-if="loading" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {{ loading
                ? (analysisType === 'cad' ? '🔄 CAD解析中...' : '🔄 AI识别中...')
                : '🚀 开始分析' }}
            </button>
            <button v-if="cadFile || imageFile" class="btn-secondary text-sm" @click="clearFiles">清空重选</button>
            <span v-if="loading" class="text-xs text-primary-600 animate-pulse">
              ⏱ 单任务执行中，请勿重复操作...
            </span>

            <!-- 状态提示 -->
            <div v-if="sysStatus" class="flex items-center gap-3 ml-auto">
              <span class="text-xs text-gray-400">系统: {{ sysStatus.task_state }}</span>
            </div>
          </div>
        </div>

        <!-- 结果展示 -->
        <CadResultCard :data="cadResult" />
        <ImageResultCard :data="imageResult" />

        <!-- 操作指引 -->
        <div v-if="!cadResult && !imageResult" class="card text-center text-gray-400 py-8">
          <p class="text-4xl mb-3">🏗️</p>
          <p class="text-sm">上传 CAD 图纸或效果图，系统将自动解析并识别</p>
          <p class="text-xs mt-2">📌 提示：CAD 和效果图须分两次上传（禁止混合）</p>
        </div>
      </div>

      <!-- Tab 2: 融合报价 -->
      <div v-show="activeTab === 'merge'">
        <MergePanel @quote-exists="onNewQuote" />
      </div>

      <!-- Tab 3: 分层明细 -->
      <div v-show="activeTab === 'breakdown'">
        <SurfaceBreakdown />
      </div>

      <!-- Tab 3: 历史记录 -->
      <div v-show="activeTab === 'history'">
        <HistoryPanel ref="historyRef" />
      </div>

      <!-- Tab 4: 定价配置 -->
      <div v-show="activeTab === 'settings'">
        <PricingPanel />
      </div>

      <!-- Tab 5: 施工工序 -->
      <div v-show="activeTab === 'processes'">
        <ProcessPanel />
        <div class="mt-6">
          <ProcessSpaceMap />
        </div>
      </div>

      <!-- Tab 6: 操作日志 -->
      <div v-show="activeTab === 'logs'">
        <LogViewer />
      </div>
    </main>

    <!-- Footer -->
    <footer class="mt-8 py-4 border-t border-gray-200">
      <div class="max-w-7xl mx-auto px-4 text-center text-xs text-gray-400">
        家装智能自动报价系统 · Demo v2.1 · 后端状态: {{ sysStatusText }}
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import API from './services/api.js'
import CadUploader from './components/CadUploader.vue'
import ImageUploader from './components/ImageUploader.vue'
import ImageQueue from './components/ImageQueue.vue'
import CadResultCard from './components/CadResultCard.vue'
import ImageResultCard from './components/ImageResultCard.vue'
import MergePanel from './components/MergePanel.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import PricingPanel from './components/PricingPanel.vue'
import LogViewer from './components/LogViewer.vue'
import ProcessPanel from './components/ProcessPanel.vue'
import ProcessSpaceMap from './components/ProcessSpaceMap.vue'
import SurfaceBreakdown from './components/SurfaceBreakdown.vue'

const tabs = [
  { key: 'home', label: '🏠 首页' },
  { key: 'merge', label: '🔄 融合报价' },
  { key: 'breakdown', label: '📐 分层明细' },
  { key: 'history', label: '📋 历史记录' },
  { key: 'settings', label: '⚙️ 定价配置' },
  { key: 'processes', label: '🔧 施工工序' },
  { key: 'logs', label: '📝 操作日志' },
]

const activeTab = ref('home')
const uploadMode = ref('single')
const projectName = ref('装修工程')
const cadFile = ref(null)
const imageFile = ref(null)
const loading = ref(false)
const analysisType = ref('')
const cadResult = ref(null)
const imageResult = ref(null)
const sysStatus = ref(null)
const historyRef = ref(null)

onMounted(async () => {
  sysStatus.value = (await API.getStatus()).data || null
})

const statusClass = computed(() => {
  if (!sysStatus.value) return 'bg-gray-100 text-gray-600'
  return sysStatus.value.task_state === 'idle' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
})
const statusDotClass = computed(() => {
  if (!sysStatus.value) return 'bg-gray-400'
  return sysStatus.value.task_state === 'idle' ? 'bg-green-500' : 'bg-yellow-500'
})
const statusText = computed(() => {
  if (!sysStatus.value) return '检查中...'
  return sysStatus.value.task_state === 'idle' ? '空闲' : sysStatus.value.task_state
})
const sysStatusText = computed(() => {
  if (!sysStatus.value) return '未知'
  const t = sysStatus.value
  return `${t.task_state} | LLaVA: ${t.llava_available ? '✓' : '✗'} | DB: ${t.db_connected ? '✓' : '✗'}`
})

function onCadFileChange(f) { cadFile.value = f }
function onImageFileChange(f) { imageFile.value = f }
function onQueueResults(results) {
  // 队列完成后自动切到融合报价tab查看结果
  if (results.length > 0) {
    activeTab.value = 'merge'
  }
}

function clearFiles() {
  cadFile.value = null
  imageFile.value = null
  cadResult.value = null
  imageResult.value = null
}

async function startAnalysis() {
  loading.value = true

  if (cadFile.value) {
    // CAD解析
    analysisType.value = 'cad'
    cadResult.value = null
    cadResult.value = await API.analyzeCad(cadFile.value, projectName.value)
    // 成功后刷新状态
    sysStatus.value = (await API.getStatus()).data || sysStatus.value
  } else if (imageFile.value) {
    // 效果图识别
    analysisType.value = 'ai'
    imageResult.value = null
    imageResult.value = await API.analyzeImage(imageFile.value)
    sysStatus.value = (await API.getStatus()).data || sysStatus.value
  }

  loading.value = false
}

function onNewQuote(quoteId) {
  // 生成报价后自动切到历史页
  activeTab.value = 'history'
}
</script>
