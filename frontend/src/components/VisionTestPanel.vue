<template>
  <div>
    <!-- 模型管理面板 -->
    <div class="card mb-4">
      <div class="flex items-center justify-between cursor-pointer" @click="showModelManager = !showModelManager">
        <h3 class="text-sm font-semibold text-gray-700">🧩 模型管理</h3>
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-gray-400" v-if="customModels.length > 0">{{ customModels.length }} 个自定义</span>
          <svg class="w-4 h-4 text-gray-400 transition-transform" :class="{'rotate-180': showModelManager}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </div>
      </div>

      <div v-if="showModelManager" class="mt-3">
        <div class="flex justify-end mb-2 gap-2">
          <button
            @click.stop="showRecycleBin = !showRecycleBin; loadRecycleBin()"
            class="text-xs px-3 py-1.5 bg-gray-100 text-gray-500 rounded-lg hover:bg-gray-200 font-medium relative"
          >
            🗑️ 回收站
            <span v-if="recycleModels.length > 0" class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] rounded-full flex items-center justify-center">{{ recycleModels.length }}</span>
          </button>
          <button
            @click.stop="startAddModel"
            class="text-xs px-3 py-1.5 bg-primary-50 text-primary-600 rounded-lg hover:bg-primary-100 font-medium"
          >
            + 添加模型
          </button>
        </div>

        <!-- 自定义模型列表 -->
      <div v-if="customModels.length > 0">
          <div class="text-[10px] text-gray-400 mb-1.5">已添加 {{ customModels.length }} 个自定义模型</div>
          <div class="space-y-1.5">
            <div v-for="cm in customModels" :key="cm.id"
                 class="flex items-center justify-between p-2 bg-white border border-gray-100 rounded-lg hover:border-gray-200">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0"
                    :class="cm.model_type === 'cloud' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'">
                {{ cm.model_type === 'cloud' ? '☁️ 云端' : '💻 本地' }}
              </span>
              <span class="text-xs font-medium text-gray-700 truncate">{{ cm.label }}</span>
              <span class="text-[10px] text-gray-400 truncate">{{ cm.model_key }}</span>
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              <button @click.stop="startEditModel(cm)"
                      class="text-[10px] px-2 py-0.5 bg-primary-50 text-primary-600 rounded hover:bg-primary-100">
                编辑
              </button>
              <button @click.stop="toggleModelEnabled(cm)"
                      :disabled="togglingId === cm.id"
                      class="text-[10px] px-2 py-0.5 rounded disabled:opacity-50"
                      :class="cm.is_enabled ? 'bg-green-50 text-green-600 hover:bg-green-100' : 'bg-gray-100 text-gray-400 hover:bg-gray-200'">
                {{ togglingId === cm.id ? '...' : (cm.is_enabled ? '✓ 已启用' : '✗ 已禁用') }}
              </button>
              <button @click.stop="deleteCustomModel(cm)"
                      :disabled="togglingId === cm.id"
                      class="text-[10px] px-2 py-0.5 bg-red-50 text-red-500 rounded hover:bg-red-100 disabled:opacity-50">
                删除
              </button>
            </div>
            </div>
          </div>
        </div>
        <div v-else class="text-[10px] text-gray-400 text-center py-2">
          暂无自定义模型，点击「+ 添加模型」开始添加
        </div>
      </div>
    </div>

    <!-- 新增/编辑模型弹窗 -->
    <div v-if="editingModel" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-5">
        <h4 class="text-sm font-semibold text-gray-700 mb-3">
          {{ editingModel.id ? '编辑模型：' + editingModel.label : '添加自定义模型' }}
        </h4>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div v-if="!editingModel.id">
            <label class="text-[10px] text-gray-500 block mb-0.5">模型ID *</label>
            <input v-model="editingModel.model_key" placeholder="如: dashscope:my-model 或 my-local-model"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-xs" />
          </div>
          <div>
            <label class="text-[10px] text-gray-500 block mb-0.5">模型名称 *</label>
            <input v-model="editingModel.label" placeholder="显示名称"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-xs" />
          </div>
          <div v-if="editingModel.model_type === 'cloud'">
            <label class="text-[10px] text-gray-500 block mb-0.5">API Base URL</label>
            <input v-model="editingModel.api_base_url" placeholder="https://api.example.com/v1"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-xs" />
          </div>
          <div v-if="editingModel.model_type === 'cloud'">
            <label class="text-[10px] text-gray-500 block mb-0.5">API Token</label>
            <input v-model="editingModel.api_token" type="password" placeholder="sk-xxxxx"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-xs" />
          </div>
          <div v-if="editingModel.model_type === 'cloud'">
            <label class="text-[10px] text-gray-500 block mb-0.5">API 格式</label>
            <select v-model="editingModel.api_format" class="w-full border border-gray-300 rounded px-2 py-1.5 text-xs bg-white">
              <option value="openai">OpenAI 兼容</option>
              <option value="dashscope">DashScope</option>
              <option value="qwen_vl_legacy">Qwen VL (旧版)</option>
            </select>
          </div>
          <div class="md:col-span-2">
            <label class="text-[10px] text-gray-500 block mb-0.5">描述</label>
            <input v-model="editingModel.description" placeholder="可选描述信息"
                   class="w-full border border-gray-300 rounded px-2 py-1.5 text-xs" />
          </div>
        </div>
        <div class="flex items-center justify-end gap-2 mt-4">
          <button @click="editingModel = null" class="text-xs px-3 py-1.5 text-gray-500 hover:text-gray-700">取消</button>
          <button @click="editingModel.id ? saveEditModel() : addCustomModel()" :disabled="savingModel"
                  class="text-xs px-4 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium disabled:opacity-50">
            {{ savingModel ? '保存中...' : (editingModel.id ? '保存' : '添加') }}
          </button>
        </div>
        <span v-if="editModelMsg" class="text-[10px] mt-1 block" :class="editModelMsgType === 'error' ? 'text-red-500' : 'text-green-600'">{{ editModelMsg }}</span>
      </div>
    </div>

    <!-- 回收站弹窗 -->
    <div v-if="showRecycleBin" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-5 max-h-[70vh] flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-semibold text-gray-700">🗑️ 回收站</h4>
          <button @click="showRecycleBin = false" class="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div v-if="recycleModels.length === 0" class="text-center py-8 text-gray-400">
          <p class="text-2xl mb-2">🗑️</p>
          <p class="text-xs">回收站为空</p>
        </div>
        <div v-else class="flex-1 overflow-y-auto space-y-2">
          <div v-for="rm in recycleModels" :key="rm.id"
               class="flex items-center justify-between p-2.5 bg-gray-50 border border-gray-100 rounded-lg">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0"
                      :class="rm.model_type === 'cloud' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'">
                  {{ rm.model_type === 'cloud' ? '☁️' : '💻' }}
                </span>
                <span class="text-xs font-medium text-gray-600 truncate">{{ rm.label }}</span>
              </div>
              <p class="text-[10px] text-gray-400 mt-0.5">删除于 {{ rm.update_time }}</p>
            </div>
            <div class="flex items-center gap-1.5 shrink-0 ml-2">
              <button @click="restoreModel(rm)" :disabled="recycleActionId === rm.id"
                      class="text-[10px] px-2 py-0.5 bg-green-50 text-green-600 rounded hover:bg-green-100 disabled:opacity-50">
                恢复
              </button>
              <button @click="permanentDelete(rm)" :disabled="recycleActionId === rm.id"
                      class="text-[10px] px-2 py-0.5 bg-red-50 text-red-500 rounded hover:bg-red-100 disabled:opacity-50">
                彻底删除
              </button>
            </div>
          </div>
        </div>
        <div class="mt-3 pt-3 border-t border-gray-100">
          <p class="text-[10px] text-gray-400 text-center">软删除的模型保留 30 天，届时将自动清理</p>
        </div>
      </div>
    </div>

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

        <!-- 图像识别和cad图纸检测切换开关 -->
        <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-200">
          <span class="text-xs text-gray-500 whitespace-nowrap">🔄 测试模式:</span>
          <button
            @click="testMode = 'image'"
            class="px-3 py-1 rounded-full text-xs font-medium transition-colors"
            :class="testMode === 'image' ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'"
          >
            🖼️ 效果图识别
          </button>
          <button
            @click="testMode = 'cad'"
            class="px-3 py-1 rounded-full text-xs font-medium transition-colors"
            :class="testMode === 'cad' ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'"
          >
            📐 CAD 解析
          </button>
        </div>
      </div>

      <!-- 上传区域 -->
      <div class="mb-4">
        <template v-if="testMode === 'image'">
          <label class="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 text-sm font-medium">
            📁 选择图片（可多选）
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="onFilesChange" class="hidden" />
          </label>
          <span class="text-xs text-gray-400 ml-3">支持多选，按顺序逐个测试</span>
        </template>
        
        <template v-else>
          <label class="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 text-sm font-medium">
            📐 选择CAD文件（.dxf/.dwg/.pdf）
            <input type="file" accept=".dxf,.dwg,.pdf" multiple @change="onCadFilesChange" class="hidden" />
          </label>
          <span class="text-xs text-gray-400 ml-3">支持 DXF、DWG、PDF 格式</span>
        </template>
      </div>

      <!-- CAD 文件列表（选择后立即显示预览按钮） -->
      <div v-if="testMode === 'cad' && cadFiles.length > 0" class="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-medium text-blue-700">已选 {{ cadFiles.length }} 个CAD文件</span>
          <button class="text-xs text-red-500 hover:text-red-700" @click="clearCadFiles">清空全部</button>
        </div>
        <div class="space-y-1.5">
          <div v-for="(f, i) in cadFiles" :key="i"
               class="flex items-center justify-between p-2 bg-white rounded border border-blue-100">
            <div class="flex items-center gap-2 min-w-0">
              <svg class="w-4 h-4 text-blue-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span class="text-xs font-medium text-gray-700 truncate">{{ f.name }}</span>
              <span class="text-[10px] text-gray-400">{{ f.file ? (f.file.size / 1024).toFixed(1) + ' KB' : '' }}</span>
              <span v-if="isDxfFile(f.name)" class="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded">可预览</span>
              <span v-if="f.groundTruth" class="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-600 rounded">✓ 已关联真实值</span>
              <span v-if="f.hasAnnotation"
                    class="text-[10px] px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded">
                ✏️ 已标注
              </span>
            </div>
            <div class="flex items-center gap-2">
              <label v-if="!f.groundTruth" class="cursor-pointer text-[10px] px-2 py-1 bg-green-100 text-green-600 rounded hover:bg-green-200 transition-colors">
                📋 上传真实值
                <input type="file" accept=".json" @change="(e) => onGroundTruthFileChange(e, i)" class="hidden" />
              </label>
              <button v-else class="text-[10px] px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors" @click="removeGroundTruth(i)">
                ✕ 移除真实值
              </button>
              <button 
                v-if="isDxfFile(f.name)"
                class="text-[10px] px-2 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200 transition-colors"
                @click="annotateCadFile(f)"
              >
                ✏️ 人工标注
              </button>
              <span v-else class="text-[10px] text-gray-400">仅支持DXF预览</span>
            </div>
          </div>
        </div>
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
        <button 
          v-if="testMode === 'image'"
          class="btn-primary" 
          :disabled="files.length === 0 || testing" 
          @click="startBatchTest"
        >
          <svg v-if="testing" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ testing ? `测试中 ${doneCount}/${files.length}...` : '🚀 批量测试效果图' }}
        </button>
        
        <button 
          v-else
          class="btn-primary" 
          :disabled="cadFiles.length === 0 || testingCad" 
          @click="startCadBatchTest"
        >
          <svg v-if="testingCad" class="animate-spin w-4 h-4 inline mr-1" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {{ testingCad ? '解析中...' : '🚀 批量测试CAD解析' }}
        </button>
      </div>

      <!-- 进度条 -->
      <div v-if="testing && files.length > 1" class="mb-4">
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div class="bg-primary-500 h-2 rounded-full transition-all duration-300" :style="{width: (doneCount/files.length*100)+'%'}"></div>
        </div>
        <div class="text-[10px] text-gray-400 mt-1 text-right">{{ doneCount }}/{{ files.length }} 完成</div>
      </div>
    </div>

    <!-- 图像汇总结果 -->
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
          📥 导出 JSON汇总结果
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

    <!-- CAD 测试结果 -->
    <div v-if="testMode === 'cad' && cadResults.length > 0" class="space-y-3">
      <div class="card">
        <h4 class="text-xs font-semibold text-gray-600 mb-2">📊 CAD 解析结果</h4>
        <div class="space-y-2">
          <div v-for="(r, i) in cadResults" :key="i" class="border rounded p-2" :class="r.success ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'">
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs font-medium">{{ i + 1 }}. {{ r.filename }}</span>
              <span class="text-[10px]" :class="r.success ? 'text-green-600' : 'text-red-600'">
                {{ r.success ? '✓ 成功' : '✗ 失败' }}
              </span>
            </div>
            
            <div v-if="r.success && r.data" class="text-xs space-y-2">
              <!-- 整体 MSE 汇总 -->
              <div v-if="r.success && r.data?.evaluation?.cad_evaluations?.overall_mse" 
                   class="grid grid-cols-2 gap-2 mb-2">
                <div class="p-1.5 bg-blue-50 rounded flex items-center justify-center gap-1 px-3" 
                     v-if="r.data.evaluation.cad_evaluations.overall_mse.area_sqm != null">
                  <span class="text-[12px] text-gray-500">面积 MSE：</span>
                  <span class="text-xs font-bold text-blue-700">
                    {{ r.data.evaluation.cad_evaluations.overall_mse.area_sqm.toFixed(2) }}
                  </span>
                </div>
                <div class="p-1.5 bg-purple-50 rounded flex items-center justify-center gap-1 px-3"
                     v-if="r.data.evaluation.cad_evaluations.overall_mse.perimeter_m != null">
                  <span class="text-[12px] text-gray-500">周长 MSE：</span>
                  <span class="text-xs font-bold text-purple-700">
                    {{ r.data.evaluation.cad_evaluations.overall_mse.perimeter_m.toFixed(2) }}
                  </span>
                </div>

              </div>

              <!-- 空间详情表格 -->
              <div v-if="r.success && r.data && r.data.spaces && r.data.spaces.length > 0" class="mt-2">
                <div class="overflow-x-auto">
                  <table class="w-full text-[12px]">
                    <thead>
                      <tr class="bg-white/50">
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-gray-600">空间名称</th>
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-gray-600">面积 (m²)</th>
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-blue-600">真实值 (m²)</th>
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-teal-500">绝对误差 (m²)</th>
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-gray-600">周长 (m)</th>
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-blue-600">真实值 (m)</th>
                        <th class="text-center py-1.5 px-2 text-[12px] font-medium text-teal-500">绝对误差 (m)</th>
                      </tr>
                    </thead>

                    <tbody>
                      <tr v-for="(space, idx) in r.data.spaces" :key="idx" class="border-t border-gray-200 bg-white/30">
                        <td class="py-1 px-2 text-center font-medium">{{ space.name || space.space_name || '-' }}</td>
                        <td class="py-1 px-2 text-center text-gray-700">{{ space.area_sqm ?? space.area ?? '-' }}</td>
                        <td class="py-1 px-2 text-center">
                          <span class="text-blue-600 font-medium">
                            {{ getEvaluatedField(r, idx, 'true_area') }}
                          </span>
                        </td>
                        <td class="py-1 px-2 text-center">
                          <span :class="getEvaluatedColor(r, idx, 'abs_error_area')">
                            {{ getEvaluatedField(r, idx, 'abs_error_area') }}
                          </span>
                        </td>
                        <td class="py-1 px-2 text-center text-gray-700">{{ space.perimeter_m ?? '-' }}</td>
                        <td class="py-1 px-2 text-center">
                          <span class="text-blue-600 font-medium">
                            {{ getEvaluatedField(r, idx, 'true_perimeter') }}
                          </span>
                        </td>
                        <td class="py-1 px-2 text-center">
                          <span :class="getEvaluatedColor(r, idx, 'abs_error_perimeter')">
                            {{ getEvaluatedField(r, idx, 'abs_error_perimeter') }}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              
              <!-- 原始数据折叠 -->
              <button class="text-[10px] text-primary-600 hover:text-primary-800" @click="r.showRaw = !r.showRaw">
                {{ r.showRaw ? '收起原始数据' : '展开原始数据' }}
              </button>
              <pre v-if="r.showRaw" class="text-[10px] bg-gray-900 text-green-300 p-2 rounded overflow-x-auto max-h-32 overflow-y-auto">{{ JSON.stringify(r.data, null, 2) }}</pre>
            </div>
            
            <div v-else class="text-xs text-red-500">
              {{ r.error || '无数据' }}
            </div>
          </div>
        </div>
      </div>
    </div>


    <!-- 空状态 -->
    <div v-if="files.length === 0 && cadFiles.length === 0 && results.length === 0 && cadResults.length === 0" class="card text-center text-gray-400 py-8">
      <p class="text-4xl mb-3">{{ testMode === 'image' ? '🧪' : '📐' }}</p>
      <p class="text-sm">{{ testMode === 'image' ? '选择一张或多张效果图，测试视觉模型识别效果' : '选择CAD文件，测试解析和报价功能' }}</p>
      <p class="text-xs mt-2">不写数据库、不走融合流程、纯诊断用途</p>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import API from '../services/api.js'
const emit = defineEmits(['cad-preview', 'cad-annotate'])  // cad标注按钮

const files = ref([])
const testing = ref(false)
const results = ref([])
const previewIndex = ref(0)
const selectedModel = ref('qwen2.5:7b')
const activeModel = ref('')
const availableModels = ref([])
const doneCount = ref(0)

// 图像识别和cad检测
const testMode = ref('image') // 'image' | 'cad'
const cadFiles = ref([]) // CAD 文件列表
const cadResults = ref([]) // CAD 测试结果
const testingCad = ref(false) // CAD 测试中状态

// ========== 新增：模型管理 ==========
const showModelManager = ref(false)
const togglingId = ref(null)
const savingModel = ref(false)
const editModelMsg = ref('')
const editModelMsgType = ref('success')
const customModels = ref([])
const editingModel = ref(null)

const showRecycleBin = ref(false)
const recycleModels = ref([])
const recycleActionId = ref(null)

async function loadCustomModels() {
  const res = await API.get('/settings/vl_model/custom')
  if (res.success && res.data) {
    customModels.value = res.data.models || []
  }
}

// ====================== 图像识别 ======================

function startAddModel() {
  editingModel.value = {
    id: null,
    model_key: '',
    label: '',
    model_type: 'cloud',
    api_base_url: '',
    api_token: '',
    api_format: 'openai',
    description: '',
  }
  editModelMsg.value = ''
}

async function addCustomModel() {
  if (!editingModel.value.model_key || !editingModel.value.label) {
    editModelMsg.value = '模型ID和模型名称不能为空'
    editModelMsgType.value = 'error'
    return
  }
  savingModel.value = true
  editModelMsg.value = ''
  const fd = new FormData()
  fd.append('model_key', editingModel.value.model_key)
  fd.append('label', editingModel.value.label)
  fd.append('model_type', editingModel.value.model_type)
  fd.append('api_base_url', editingModel.value.api_base_url)
  fd.append('api_token', editingModel.value.api_token)
  fd.append('api_format', editingModel.value.api_format || 'openai')
  fd.append('description', editingModel.value.description)
  const res = await API.post('/settings/vl_model/custom', fd)
  if (res.success) {
    editModelMsg.value = `模型 ${editingModel.value.label} 添加成功`
    editModelMsgType.value = 'success'
    await loadCustomModels()
    await reloadModels()
    setTimeout(() => { editingModel.value = null }, 500)
  } else {
    editModelMsg.value = res.message || '添加失败'
    editModelMsgType.value = 'error'
  }
  savingModel.value = false
  setTimeout(() => editModelMsg.value = '', 3000)
}

async function toggleModelEnabled(cm) {
  if (togglingId.value === cm.id) return
  togglingId.value = cm.id
  const fd = new FormData()
  fd.append('is_enabled', cm.is_enabled ? 0 : 1)
  const res = await API.put(`/settings/vl_model/custom/${cm.id}`, fd)
  if (res.success) {
    cm.is_enabled = cm.is_enabled ? 0 : 1
    await loadCustomModels()
    await reloadModels()
  } else {
    alert(res.message || '操作失败')
  }
  togglingId.value = null
}

async function deleteCustomModel(cm) {
  if (!confirm(`确定将模型「${cm.label}」移入回收站？您可以在 30 天内恢复。`)) return
  const res = await API.delete(`/settings/vl_model/custom/${cm.id}`)
  if (res.success) {
    await loadCustomModels()
    await reloadModels()
  } else {
    alert(res.message || '删除失败')
  }
}

async function loadRecycleBin() {
  const res = await API.get('/settings/vl_model/custom/recycle')
  if (res.success && res.data) {
    recycleModels.value = res.data.models || []
  }
}

async function restoreModel(rm) {
  recycleActionId.value = rm.id
  const res = await API.post(`/settings/vl_model/custom/recycle/${rm.id}/restore`)
  if (res.success) {
    await loadRecycleBin()
    await loadCustomModels()
    await reloadModels()
  } else {
    alert(res.message || '恢复失败')
  }
  recycleActionId.value = null
}

async function permanentDelete(rm) {
  if (!confirm(`此操作不可撤销，模型「${rm.label}」将被永久删除。确定要继续吗？`)) return
  recycleActionId.value = rm.id
  const res = await API.delete(`/settings/vl_model/custom/recycle/${rm.id}`)
  if (res.success) {
    await loadRecycleBin()
  } else {
    alert(res.message || '删除失败')
  }
  recycleActionId.value = null
}

function startEditModel(cm) {
  editingModel.value = { ...cm }
  editModelMsg.value = ''
}

async function saveEditModel() {
  if (!editingModel.value.label) {
    editModelMsg.value = '显示名称不能为空'
    editModelMsgType.value = 'error'
    return
  }
  savingModel.value = true
  editModelMsg.value = ''
  const fd = new FormData()
  fd.append('label', editingModel.value.label)
  fd.append('description', editingModel.value.description)
  if (editingModel.value.model_type === 'cloud') {
    fd.append('api_base_url', editingModel.value.api_base_url || '')
    fd.append('api_token', editingModel.value.api_token || '')
    fd.append('api_format', editingModel.value.api_format || 'openai')
  }
  const res = await API.put(`/settings/vl_model/custom/${editingModel.value.id}`, fd)
  if (res.success) {
    editModelMsg.value = '保存成功'
    editModelMsgType.value = 'success'
    await loadCustomModels()
    await reloadModels()
    setTimeout(() => { editingModel.value = null }, 500)
  } else {
    editModelMsg.value = res.message || '保存失败'
    editModelMsgType.value = 'error'
  }
  savingModel.value = false
  setTimeout(() => editModelMsg.value = '', 3000)
}

async function reloadModels() {
  const res = await API.get('/settings/vl_model')
  if (res.success && res.data) {
    activeModel.value = res.data.active_model
    availableModels.value = res.data.available_models || []
  }
}

// ========== 环境切换 ==========
const useCloud = ref(false)

// 计算属性：根据开关状态过滤模型列表
const filteredModels = computed(() => {
  return availableModels.value.filter(m => {
    return useCloud.value ? m.is_cloud : !m.is_cloud
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
    // 根据当前选中模型的 is_cloud 字段判断环境，兼容自定义云端模型
    const currentModel = availableModels.value.find(m => m.key === res.data.active_model)
    if (currentModel) {
      useCloud.value = !!currentModel.is_cloud
    }
  }
  await loadCustomModels()
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

// 导出测试结果
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


// 导出为 CSV 格式
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


// 导出为 JSON 格式
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

// 下载文件
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

// ====================== CAD 识别 ======================

// CAD 文件处理函数
function onCadFilesChange(e) {
  const newFiles = Array.from(e.target.files || [])
  cadFiles.value = newFiles.map(f => ({
    file: f,
    name: f.name,
    url: null,
    done: false,
    failed: false,
    testing: false,
    groundTruth: null,
    groundTruthData: null,
    hasAnnotation: false,
  }))
  cadResults.value = []
  e.target.value = ''
}

// 清空 CAD 文件列表
function clearCadFiles() {
  cadFiles.value = []
  cadResults.value = []
}

// 判断是否为 DXF 文件
function isDxfFile(filename) {
  return filename.toLowerCase().endsWith('.dxf')
}

// 人工标注 CAD 图纸
function annotateCadFile(cadFileObj) {
  if (!cadFileObj || !cadFileObj.file) return
  emit('cad-annotate', {
    file: cadFileObj.file,
    filename: cadFileObj.name,
    callback: () => {
      cadFileObj.hasAnnotation = true
    }
  })
}


// 真实值 JSON 处理（单个 CAD 文件关联）
function onGroundTruthFileChange(e, cadIndex) {
  const file = e.target.files?.[0]
  if (!file) return
  
  const reader = new FileReader()
  reader.onload = (evt) => {
    try {
      const jsonData = JSON.parse(evt.target.result)
      cadFiles.value[cadIndex].groundTruth = file.name
      cadFiles.value[cadIndex].groundTruthData = jsonData
    } catch (err) {
      alert(`解析 JSON 文件 "${file.name}" 失败: ${err.message}`)
      return
    }
    e.target.value = ''
  }
  reader.readAsText(file)
}

function removeGroundTruth(cadIndex) {
  cadFiles.value[cadIndex].groundTruth = null
  cadFiles.value[cadIndex].groundTruthData = null
}

// 通过列名获取后端测试数据
function getEvaluatedField(result, spaceIdx, field) {
  const evaluation = result.data?.evaluation
  if (!evaluation) return '-'
  
  // 通过空间名称匹配，而非索引
  const space = result.data.spaces?.[spaceIdx]
  const spaceName = space?.name || space?.space_name
  const room = evaluation.cad_evaluations?.rooms?.find(r => r.name === spaceName)

  if (field === 'true_area') {
    const raw = evaluation.raw_data?.find(r => r.name === spaceName)
    return raw?.true_area != null ? raw.true_area.toFixed(2) : '-'
  }

  if (field === 'abs_error_area') {
    return room?.abs_error_area != null ? room.abs_error_area.toFixed(2) : '-'
  }

  if (field === 'true_perimeter') {
    const raw = evaluation.raw_data?.find(r => r.name === spaceName)
    return raw?.true_perimeter != null ? raw.true_perimeter.toFixed(2) : '-'
  }

  if (field === 'abs_error_perimeter') {
    return room?.abs_error_perimeter != null ? room.abs_error_perimeter.toFixed(2) : '-'
  }

}

// 根据误差结果分配颜色
function getEvaluatedColor(result, spaceIdx, label) {
  const val = getEvaluatedField(result, spaceIdx, label)
  const num = parseFloat(val)
  if (isNaN(num)) return 'text-gray-400'
  if (num > 10) return 'text-red-600'
  if (num > 5) return 'text-yellow-600'
  return 'text-green-600'
}

async function startCadBatchTest() {
  if (cadFiles.value.length === 0) return
  testingCad.value = true
  cadResults.value = []

  const newResults = []
  
  for (const f of cadFiles.value) {
    f.testing = true
    f.showRaw = false
    
    const fd = new FormData()
    fd.append('cad_file', f.file)
    fd.append('project_name', 'CAD 测试工程')
    
    try {
      const res = await API.post('/analyze_full', fd, { timeout: 120000 })
      
      const apiSuccess = res?.success === true
      const apiData = apiSuccess ? res?.data : null
      const apiError = res?.message || (res?.code ? `错误码: ${res.code}` : null)
      
      let evaluatedData = apiData
      
      // 在 startCadBatchTest 中，构建评估用的数据时，补全 area_sqm 字段
      if (apiSuccess && f.groundTruthData && f.groundTruthData.spaces !== undefined) {
        // 规范化 spaces 数据：确保包含 area_sqm 和 perimeter_m
        const normalizedSpaces = (apiData.spaces || []).map(s => ({
          ...s,
          area_sqm: s.area_sqm ?? s.area ?? 0,
          perimeter_m: s.perimeter_m ?? s.perimeter ?? null,
        }))
        const evalPayload = { ...apiData, spaces: normalizedSpaces }
        const evalRes = await API.evaluateCadResult(evalPayload, f.groundTruthData)
        if (evalRes.success && evalRes.data) {
          evaluatedData = { ...apiData, evaluation: evalRes.data }
        }
      }
      
      const resultEntry = {
        filename: f.name,
        success: apiSuccess,
        data: evaluatedData,
        error: apiError,
        timestamp: new Date().toLocaleString(),
        showRaw: false
      }
      
      newResults.push(resultEntry)
      
      f.done = apiSuccess
      f.failed = !apiSuccess
    } catch (err) {
      console.error('CAD test error:', err)
      newResults.push({
        filename: f.name,
        success: false,
        data: null,
        error: err.message || '请求失败',
        timestamp: new Date().toLocaleString(),
        showRaw: false
      })
      f.failed = true
    }
    
    f.testing = false
  }
  
  cadResults.value = newResults  
  testingCad.value = false
}

</script>
