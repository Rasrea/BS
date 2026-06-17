<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-base font-semibold text-gray-800 flex items-center gap-2">
        <span>📋</span> 报价历史记录
      </h3>
      <button @click="refresh" class="btn-secondary text-sm !px-3 !py-1.5">
        🔄 刷新
      </button>
    </div>

    <div v-if="loading" class="text-center text-gray-400 py-8">加载中...</div>

    <div v-else-if="!records.length" class="text-center text-gray-400 py-8 card">
      <p class="text-3xl mb-2">📭</p>
      <p>暂无历史记录</p>
      <p class="text-xs mt-1">请在「首页」上传CAD图纸开始分析</p>
    </div>

    <!-- 列表 -->
    <div v-else class="space-y-3">
      <div v-for="q in records" :key="q.id"
           class="card !p-4 hover:shadow-md cursor-pointer transition-all"
           @click="toggleDetail(q.id)">
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-3">
              <span class="text-sm font-semibold text-gray-800">{{ q.project_name || '装修工程' }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full"
                :class="q.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'">
                {{ q.status || 'completed' }}
              </span>
              <span class="text-xs text-gray-400">{{ q.created_at || q.create_time }}</span>
            </div>
            <div class="flex items-center gap-4 mt-1 text-xs text-gray-500">
              <span>{{ q.space_count || 0 }} 个空间</span>
              <span>{{ q.total_area ? q.total_area.toFixed(1) : '-' }} ㎡</span>
              <span v-if="q.final_price" class="font-semibold text-primary-700">
                ¥{{ Number(q.final_price).toLocaleString() }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2 ml-4">
            <button v-if="q.id" @click.stop="doExport(q.id)"
                    class="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100">
              导出
            </button>
            <button @click.stop="confirmDelete(q.id)"
                    class="text-xs px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100">
              删除
            </button>
            <span class="text-gray-300 text-lg">{{ expandedId === q.id ? '▾' : '▸' }}</span>
          </div>
        </div>

        <!-- 详情展开 -->
        <transition name="fade">
          <div v-if="expandedId === q.id" class="mt-4 pt-4 border-t border-gray-100">
            <QuoteDisplay v-if="q.id" :data="{ success: true, data: q }" :title="'报价明细'" />
          </div>
        </transition>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="flex justify-center items-center gap-3 mt-6">
      <button class="btn-secondary text-sm !px-3 !py-1" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
      <span class="text-sm text-gray-500">{{ page }} / {{ totalPages }}</span>
      <button class="btn-secondary text-sm !px-3 !py-1" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
    </div>

    <!-- 自定义删除确认弹窗 -->
    <ConfirmDialog
      :visible="showDeleteDialog"
      title="确认删除"
      message="确定要删除此报价记录吗？此操作不可撤销。"
      @confirm="doDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import API from '../services/api.js'
import QuoteDisplay from './QuoteDisplay.vue'
import ConfirmDialog from './ConfirmDialog.vue'

const records = ref([])
const loading = ref(false)
const page = ref(1)
const totalPages = ref(1)
const expandedId = ref(null)

// 删除确认弹窗
const showDeleteDialog = ref(false)
const pendingDeleteId = ref(null)

async function refresh() {
  loading.value = true
  const res = await API.getHistory(page.value, 20)
  if (res.success && res.data?.quotes?.items) {
    records.value = res.data.quotes.items
    totalPages.value = Math.ceil((res.data.quotes.total || 1) / 20)
  } else {
    records.value = []
  }
  loading.value = false
}

async function changePage(p) {
  page.value = p
  await refresh()
}

function toggleDetail(id) {
  expandedId.value = expandedId.value === id ? null : id
}

async function doExport(quoteId) {
  const res = await API.downloadExcelBlob(quoteId)
  if (!res.success) {
    alert('导出失败：' + res.message)
  }
}

function confirmDelete(quoteId) {
  pendingDeleteId.value = quoteId
  showDeleteDialog.value = true
}

async function doDelete() {
  const quoteId = pendingDeleteId.value
  if (!quoteId) return
  showDeleteDialog.value = false
  const res = await API.deleteHistory(quoteId)
  if (res.success) {
    records.value = records.value.filter(r => r.id !== quoteId)
  } else {
    alert('删除失败：' + res.message)
  }
  pendingDeleteId.value = null
}

onMounted(refresh)
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
