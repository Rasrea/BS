<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
    <!-- ⏳ 启动加载遮罩 -->
    <div v-if="appLoading" class="fixed inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center z-[999]"
         style="position:fixed;top:0;left:0;right:0;bottom:0;">
      <div class="text-center max-w-sm">
        <svg class="animate-spin w-12 h-12 mx-auto text-primary-500 mb-4" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        <p class="text-sm font-medium text-gray-700" v-if="!appLoadingError">正在连接后端服务...</p>
        <p class="text-sm font-medium text-red-600" v-else>{{ appLoadingError }}</p>
        <p class="text-xs text-gray-400 mt-2" v-if="!appLoadingError">请确保后端服务已启动（端口 8100）</p>
        <button v-if="appLoadingError" class="btn-primary text-sm mt-4" @click="retryConnect">🔄 重试连接</button>
      </div>
    </div>
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
              <p class="text-[10px] text-gray-500">图纸分析 · 分层明细 · 融合报价 · 施工工序</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              :class="statusClass">
              <span class="w-1.5 h-1.5 rounded-full" :class="statusDotClass"></span>
              {{ statusText }}
            </span>
            <span class="text-xs text-gray-400">V1.0.4</span>
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
        <!-- 流水步骤条 -->
        <div class="card mb-4">
          <div class="flex items-center justify-between">
            <div v-for="(step, i) in flowSteps" :key="i"
                 class="flex items-center gap-2"
                 :class="i < flowSteps.length - 1 ? 'flex-1' : ''">
              <div class="flex items-center gap-2">
                <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                     :class="step.done ? 'bg-green-500 text-white' : step.active ? 'bg-primary-600 text-white ring-2 ring-primary-300' : 'bg-gray-200 text-gray-500'">
                  {{ step.done ? '✓' : step.num }}
                </div>
                <span class="text-xs font-medium" :class="step.done ? 'text-green-600' : step.active ? 'text-primary-700' : 'text-gray-400'">
                  {{ step.label }}
                </span>
              </div>
              <div v-if="i < flowSteps.length - 1" class="flex-1 h-px mx-2"
                   :class="flowSteps[i+1].done ? 'bg-green-400' : 'bg-gray-300'"></div>
            </div>
          </div>
        </div>
        <!-- 项目名称 -->
        <div class="card mb-4">
          <label class="text-xs text-gray-500 block mb-1">项目名称</label>
          <input v-model="projectName" placeholder="装修工程"
                 class="w-full max-w-xs border border-gray-300 rounded-lg px-3 py-2 text-sm" />
        </div>

        <!-- 视觉模型选择 -->
        <div class="card mb-4">
          <div class="flex items-center gap-4 flex-wrap">
            <span class="text-xs text-gray-500">🧠 视觉模型:</span>
            <span class="text-xs font-semibold text-primary-700 bg-primary-50 px-2 py-1 rounded">{{ activeModel }}</span>
            <select v-model="selectedModel" class="border border-gray-300 rounded-lg px-2 py-1 text-xs bg-white">
              <option v-for="m in availableModels" :key="m.key" :value="m.key" :disabled="!m.installed">
                {{ m.label }}{{ !m.installed ? ' (未安装)' : '' }}
              </option>
            </select>
            <button class="text-xs px-2 py-1 rounded font-medium"
              :class="selectedModel && selectedModel !== activeModel ? 'bg-primary-600 text-white hover:bg-primary-700' : 'bg-gray-100 text-gray-400 cursor-not-allowed'"
              :disabled="!selectedModel || selectedModel === activeModel || vlSaving"
              @click="switchModel">
              {{ vlSaving ? '切换中...' : '切换' }}
            </button>
            <span v-if="vlMsg" class="text-xs" :class="vlMsgType === 'error' ? 'text-red-500' : 'text-green-600'">{{ vlMsg }}</span>
          </div>
        </div>

        <!-- 上传模式选择 -->
        <div class="flex items-center gap-2 mb-3">
          <button @click="uploadMode='single'" class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
            :class="uploadMode==='single' ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'">
            单张上传
          </button>
          <button @click="uploadMode='multi'" class="text-xs px-3 py-1.5 rounded-lg font-medium transition-colors"
            :class="uploadMode==='multi' ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'">
            多张队列
          </button>
          <span v-if="uploadMode==='single'" class="text-xs text-gray-300 mx-1">|</span>
          <button v-if="uploadMode==='single'"
                  @click="singleFormat = singleFormat === 'image' ? 'pdf' : 'image'"
                  class="text-xs px-2 py-1 rounded font-medium transition-colors"
                  :class="singleFormat==='image' ? 'bg-blue-50 text-blue-600' : 'bg-amber-50 text-amber-600'">
            {{ singleFormat === 'image' ? '🖼️ 图片' : '📄 PDF' }}
          </button>
        </div>

        <!-- 双上传区 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <CadUploader @file-change="onCadFileChange" @preview="onCadPreview" />
            <!-- CAD预览 -->
            <div v-if="cadPreviewUrl && uploadMode==='single'" class="mt-2 p-2 bg-gray-50 rounded border border-gray-200">
              <p class="text-xs text-gray-500 mb-1">📐 CAD文件: {{ cadFile?.name }}</p>
              <div v-if="cadSpaces.length > 0" class="grid grid-cols-3 gap-1 max-h-32 overflow-y-auto">
                <div v-for="s in cadSpaces.slice(0, 15)" :key="s.name"
                     class="text-[10px] bg-white rounded px-1.5 py-1 border border-gray-100">
                  <span class="font-medium text-gray-700">{{ s.name }}</span>
                  <span class="text-gray-400 ml-1">{{ s.area_sqm?.toFixed(1) }}㎡</span>
                </div>
                <div v-if="cadSpaces.length > 15" class="text-[10px] text-primary-600 rounded px-1.5 py-1 bg-primary-50">
                  +{{ cadSpaces.length - 15 }} 个空间
                </div>
              </div>
            </div>
          </div>
          <div>
            <!-- 单张上传模式：图片 / PDF 二选一 -->
            <ImageUploader v-if="uploadMode==='single' && singleFormat==='image'" @file-change="onImageFileChange" />
            <div v-else-if="uploadMode==='single' && singleFormat==='pdf'" class="card">
              <label class="block text-sm font-medium text-gray-700 mb-2">📄 上传PDF施工图</label>
              <input type="file" accept=".pdf" @change="onPdfFileChange"
                     class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100" />
              <p v-if="pdfFile" class="text-xs text-green-600 mt-2 flex items-center gap-2">
                ✅ {{ pdfFile.name }}
                <button class="text-indigo-500 hover:text-indigo-700 font-medium" @click="previewPdf">🔍 预览</button>
              </p>
              <button v-if="pdfFile && !pdfLoading" class="btn-primary text-xs mt-3" @click="startPdfAnalysis">
                🚀 识别PDF
              </button>
              <p v-if="pdfLoading" class="text-xs text-primary-600 mt-2 animate-pulse">⏱ PDF解析中...</p>
            </div>
            <!-- 多张队列模式（同时支持CAD和效果图） -->
            <ImageQueue v-else-if="uploadMode==='multi'" @results-update="onQueueResults" />
            <!-- 图片预览 -->
            <div v-if="imagePreviewUrl && uploadMode==='single' && singleFormat==='image'" class="mt-2 p-2 bg-gray-50 rounded border border-gray-200">
              <p class="text-xs text-gray-500 mb-1">🖼️ 效果图预览:</p>
              <img :src="imagePreviewUrl" class="w-full h-32 object-cover rounded border border-gray-200" />
            </div>
          </div>
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
              {{ loading ? '⏳ 执行中...' : '🚀 开始分析' }}
            </button>
            <button v-if="cadFile || imageFile" class="btn-secondary text-sm" @click="clearFiles">清空重选</button>

            <!-- 状态提示 -->
            <div v-if="sysStatus" class="flex items-center gap-3 ml-auto">
              <span class="text-xs text-gray-400">系统: {{ sysStatus.task_state }}</span>
            </div>
          </div>

          <!-- 详细进度 -->
          <div v-if="loading && progressSteps.length > 0" class="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
            <div v-for="(step, i) in progressSteps" :key="i" class="flex items-start gap-2 py-1">
              <!-- 状态图标 -->
              <span v-if="step.status === 'done'" class="text-green-500 text-xs mt-0.5">✓</span>
              <span v-else-if="step.status === 'active'" class="text-primary-500 text-xs mt-0.5">
                <svg class="animate-spin w-3 h-3" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
              </span>
              <span v-else class="text-gray-300 text-xs mt-0.5">○</span>
              <!-- 步骤文字 -->
              <span class="text-xs" :class="{
                'text-green-700 font-medium': step.status === 'done',
                'text-primary-700 font-medium': step.status === 'active',
                'text-gray-400': step.status === 'pending',
              }">{{ step.text }}</span>
              <!-- 耗时 -->
              <span v-if="step.duration" class="text-[10px] text-gray-400 ml-auto">{{ step.duration }}</span>
            </div>
          </div>
        </div>

        <!-- 结果展示 -->
        <CadResultCard :data="cadResult" />
        <ImageResultCard :data="imageResult" />

        <!-- 操作指引 -->
        <div v-if="!cadResult && !imageResult && !pdfResult" class="card text-center text-gray-400 py-8">
          <p class="text-4xl mb-3">📐</p>
          <p class="text-sm">上传 CAD 图纸或效果图，系统自动完成图纸分析</p>
          <p class="text-xs mt-2">💡 流程：图纸分析 → 分层明细 → 融合报价 → 施工工序</p>
        </div>
        <!-- PDF结果 -->
        <div v-if="pdfResult" class="card mt-4">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">📄 PDF识别结果</h3>
          <div class="text-xs text-gray-600">
            <p>文件: {{ pdfResult.data?.filename }}</p>
            <p>页数: {{ pdfResult.data?.total_pages }}页</p>
            <div v-for="r in pdfResult.data?.results" :key="r.page" class="mt-2 p-2 bg-gray-50 rounded">
              <p class="font-medium">第{{ r.page }}页</p>
              <p>空间: {{ r.recognized_space || '未识别' }}</p>
              <p>墙面: {{ r.wall_material || '-' }} | 地面: {{ r.floor_material || '-' }} | 顶面: {{ r.ceiling_material || '-' }}</p>
            </div>
          </div>
          <button class="btn-primary text-xs mt-3" @click="pdfResult=null; activeTab='merge'">前往融合报价 →</button>
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

      <!-- Tab: 双源核对 -->
      <div v-show="activeTab === 'comparison'">
        <ComparisonPanel />
      </div>

      <!-- Tab: 标准报价 -->
      <div v-show="activeTab === 'reports'">
        <StandardReport />
      </div>

      <!-- Tab 7: 识别测试 -->
      <div v-show="activeTab === 'vision_test'">
        <VisionTestPanel />
      </div>
    </main>

    <!-- 全屏 CAD 预览 -->
    <Teleport to="body">
      <div v-if="showCadPreview" class="cad-preview-overlay">
        <CadViewer ref="cadViewerRef" :file="cadPreviewFile" @close="closeCadPreview" />
      </div>
    </Teleport>

    <!-- Footer -->
    <footer class="mt-8 py-4 border-t border-gray-200">
      <div class="max-w-7xl mx-auto px-4 text-center text-xs text-gray-400">
        家装智能自动报价系统 · Demo v2.1 · 后端状态: {{ sysStatusText }}
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, provide } from 'vue'
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
import VisionTestPanel from './components/VisionTestPanel.vue'
import ComparisonPanel from './components/ComparisonPanel.vue'
import StandardReport from './components/StandardReport.vue'
import CadViewer from './components/CadViewer.vue'

const tabs = [
  { key: 'home', label: '📐 图纸分析' },
  { key: 'breakdown', label: '📋 分层明细' },
  { key: 'merge', label: '💰 融合报价' },
  { key: 'processes', label: '🔧 施工工序' },
  { key: 'reports', label: '📊 标准报价' },
  { key: 'history', label: '📋 历史记录' },
  { key: 'comparison', label: '📋 双源核对' },
  { key: 'settings', label: '⚙️ 定价配置' },
  { key: 'logs', label: '📝 操作日志' },
  { key: 'vision_test', label: '🔬 识别测试' },
]

const activeTab = ref('home')
const uploadMode = ref('single')
const singleFormat = ref('image')
const projectName = ref('装修工程')
const cadFile = ref(null)
const imageFile = ref(null)
const loading = ref(false)
const analysisType = ref('')
const cadResult = ref(null)
const imageResult = ref(null)
const sysStatus = ref(null)
const historyRef = ref(null)
const progressSteps = ref([])

// 🌟 刷新键：分析完成后+1，子组件watch此值自动重新加载数据
const refreshKey = ref(0)
provide('refreshKey', refreshKey)

// 进度辅助函数
function addStep(text) {
  progressSteps.value.push({ text, status: 'pending', duration: '' })
}
function setStepActive(text) {
  const s = progressSteps.value.find(s => s.text === text)
  if (s) s.status = 'active'
}
function setStepDone(text, duration = '') {
  const s = progressSteps.value.find(s => s.text === text)
  if (s) { s.status = 'done'; s.duration = duration }
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }

// 文件预览
const cadPreviewUrl = ref('')
const imagePreviewUrl = ref('')
const cadSpaces = ref([])

// CAD 图纸预览（全屏）
const showCadPreview = ref(false)
const cadPreviewFile = ref(null)
const cadViewerRef = ref(null)

// ⏳ 启动加载
const appLoading = ref(true)
const appLoadingError = ref('')
async function retryConnect() {
  appLoadingError.value = ''
  appLoading.value = true
  try {
    sysStatus.value = (await API.getStatus()).data || null
    await loadVlModels()
  } catch (e) {
    appLoadingError.value = '❌ 后端连接失败: ' + (e.message || '网络异常，请确认后端已启动')
  } finally {
    setTimeout(() => { appLoading.value = false }, 400)
  }
}

// 流水步骤
const cadDone = ref(false)
const imgDone = ref(false)
const analysisDone = ref(false)
const flowSteps = computed(() => [
  { num: '1', label: '上传CAD', done: cadDone.value, active: !cadDone.value && !imgDone.value },
  { num: '2', label: '上传效果图', done: imgDone.value, active: cadDone.value && !imgDone.value },
  { num: '3', label: '开始分析', done: analysisDone.value, active: (cadDone.value || imgDone.value) && !analysisDone.value },
  { num: '4', label: '查看结果', done: false, active: analysisDone.value },
])

// 视觉模型
const vlSaving = ref(false)
const activeModel = ref('')
const selectedModel = ref('')
const availableModels = ref([])
const vlMsg = ref('')
const vlMsgType = ref('success')

onMounted(async () => {
  appLoading.value = true
  try {
    sysStatus.value = (await API.getStatus()).data || null
    await loadVlModels()
  } catch (e) {
    appLoadingError.value = '❌ 后端连接失败: ' + (e.message || '网络异常')
  } finally {
    setTimeout(() => { appLoading.value = false }, 400)
  }
})

async function loadVlModels() {
  const res = await API.get('/settings/vl_model')
  if (res.success && res.data) {
    activeModel.value = res.data.active_model
    selectedModel.value = res.data.active_model
    availableModels.value = res.data.available_models || []
  }
}

async function switchModel() {
  if (!selectedModel.value || selectedModel.value === activeModel.value) return
  vlSaving.value = true
  vlMsg.value = ''
  const fd = new FormData()
  fd.append('model', selectedModel.value)
  const res = await API.post('/settings/vl_model', fd)
  if (res.success) {
    activeModel.value = res.data.active_model
    vlMsg.value = `已切换至 ${res.data.active_model}`
    vlMsgType.value = 'success'
  } else {
    vlMsg.value = res.message || '切换失败'
    vlMsgType.value = 'error'
  }
  setTimeout(() => vlMsg.value = '', 3000)
  vlSaving.value = false
}

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

function onCadFileChange(f) {
  cadFile.value = f
  cadDone.value = !!f
  if (f) {
    cadPreviewUrl.value = f.name // 标记已上传
  } else {
    cadPreviewUrl.value = ''
    cadSpaces.value = []
  }
}
function onImageFileChange(f) {
  imageFile.value = f
  imgDone.value = !!f
  if (f) {
    imagePreviewUrl.value = URL.createObjectURL(f)
  } else {
    imagePreviewUrl.value = ''
  }
}
function onQueueResults(results) {
  // 队列完成后自动切到融合报价tab查看结果
  if (results.length > 0) {
    activeTab.value = 'merge'
    refreshKey.value++  // 🌟 通知子组件刷新
  }
}

async function clearFiles() {
  // 后端同步删除临时文件
  try {
    await API.post('/upload/clear', {})
  } catch (e) { /* 静默处理 */ }
  cadFile.value = null
  imageFile.value = null
  cadResult.value = null
  imageResult.value = null
  cadPreviewUrl.value = ''
  imagePreviewUrl.value = ''
  cadSpaces.value = []
  cadDone.value = false
  imgDone.value = false
  analysisDone.value = false
  progressSteps.value = []
}

// CAD 图纸预览
function onCadPreview(fileData) {
  cadPreviewFile.value = fileData
  showCadPreview.value = true
}
function closeCadPreview() {
  // 先显式销毁引擎，再隐藏 overlay
  try { cadViewerRef.value?.cleanup?.() } catch (e) {}
  showCadPreview.value = false
  cadPreviewFile.value = null
}

async function startAnalysis() {
  loading.value = true
  progressSteps.value = []

  if (cadFile.value) {
    analysisType.value = 'cad'
    cadResult.value = null

    addStep('📤 上传CAD文件...')
    addStep('🔍 解析CAD图纸...')
    addStep('📐 计算面积和工程量...')
    setStepActive('📤 上传CAD文件...')
    await sleep(100)

    const t0 = Date.now()
    cadResult.value = await API.analyzeCad(cadFile.value, projectName.value)
    const dur = ((Date.now() - t0) / 1000).toFixed(1) + 's'
    setStepDone('📤 上传CAD文件...', dur)

    if (cadResult.value?.success) {
      setStepDone('🔍 解析CAD图纸...')
      setStepDone('📐 计算面积和工程量...')
    } else {
      setStepDone('🔍 解析CAD图纸...', '失败')
      setStepDone('📐 计算面积和工程量...', '失败')
    }

    // 解析成功后填充CAD空间预览
    if (cadResult.value?.data?.spaces) {
      cadSpaces.value = cadResult.value.data.spaces
    }
  }

  if (imageFile.value) {
    analysisType.value = 'ai'
    imageResult.value = null

    addStep('📤 上传效果图...')
    addStep('🖼️ 预处理图片（压缩/裁剪）...')
    addStep('🧠 调用视觉模型识别...')
    addStep('📋 解析识别结果...')
    setStepActive('📤 上传效果图...')
    await sleep(100)

    const t0 = Date.now()
    imageResult.value = await API.analyzeImage(imageFile.value)
    const dur = ((Date.now() - t0) / 1000).toFixed(1) + 's'

    setStepDone('📤 上传效果图...', dur)
    setStepDone('🖼️ 预处理图片（压缩/裁剪）...')
    setStepDone('🧠 调用视觉模型识别...')

    if (imageResult.value?.success) {
      setStepDone('📋 解析识别结果...')
    } else {
      setStepDone('📋 解析识别结果...', '失败')
    }
  }

  // 更新系统状态
  sysStatus.value = (await API.getStatus()).data || sysStatus.value

  loading.value = false
  analysisDone.value = true
  refreshKey.value++  // 🌟 通知子组件刷新数据
}

function onNewQuote(quoteId) {
  // 生成报价后自动切到历史页并刷新
  refreshKey.value++
  activeTab.value = 'history'
}

// ======== PDF识别 ========
const pdfFile = ref(null)
const pdfLoading = ref(false)
const pdfResult = ref(null)

function onPdfFileChange(e) {
  pdfFile.value = e.target.files[0] || null
}

function previewPdf() {
  if (!pdfFile.value) return
  const url = URL.createObjectURL(pdfFile.value)
  window.open(url, '_blank')
}

async function startPdfAnalysis() {
  if (!pdfFile.value) return
  pdfLoading.value = true
  const fd = new FormData()
  fd.append('pdf_file', pdfFile.value)
  const res = await API.post('/analyze_pdf', fd)
  pdfResult.value = res
  pdfLoading.value = false
  if (res.success) {
    pdfFile.value = null  // 清空
    refreshKey.value++  // 🌟 通知子组件刷新
    activeTab.value = 'merge'  // 切到融合报价
  }
}
</script>

<style>
.cad-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  animation: cad-fade-in 0.2s ease-out;
}
@keyframes cad-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
