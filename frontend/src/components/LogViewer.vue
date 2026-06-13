<template>
  <div>
    <h3 class="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
      <span>📝</span> 操作日志
    </h3>

    <div v-if="loading" class="text-center text-gray-400 py-8">加载中...</div>

    <div v-else-if="!logs.length" class="text-center text-gray-400 py-8 card">
      <p>暂无操作日志</p>
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200">
            <th class="text-left py-2 px-3 font-medium text-gray-600">时间</th>
            <th class="text-left py-2 px-3 font-medium text-gray-600">类型</th>
            <th class="text-left py-2 px-3 font-medium text-gray-600">Trace ID</th>
            <th class="text-right py-2 px-3 font-medium text-gray-600">耗时 (s)</th>
            <th class="text-center py-2 px-3 font-medium text-gray-600">状态</th>
            <th class="text-left py-2 px-3 font-medium text-gray-600">错误信息</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id"
              class="border-b border-gray-100 hover:bg-gray-50">
            <td class="py-2 px-3 text-xs text-gray-500 whitespace-nowrap">{{ log.start_time || log.create_time || log.operate_time || '-' }}</td>
            <td class="py-2 px-3 text-gray-700 font-medium">{{ log.task_type || log.operation_action }}</td>
            <td class="py-2 px-3 text-xs text-gray-400 font-mono">{{ log.trace_id || '-' }}</td>
            <td class="py-2 px-3 text-right text-gray-700">{{ log.duration ? Number(log.duration).toFixed(1) : '-' }}</td>
            <td class="py-2 px-3 text-center">
              <span class="px-2 py-0.5 text-xs rounded-full"
                :class="statusClass(log.run_status || log.status)">
                {{ log.run_status || log.status || 'unknown' }}
              </span>
            </td>
            <td class="py-2 px-3 text-xs text-red-500 max-w-xs truncate">{{ log.error_info || '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import API from '../services/api.js'

const loading = ref(false)
const logs = ref([])

function statusClass(s) {
  if (!s || s === 'success') return 'bg-green-100 text-green-700'
  if (s === 'running') return 'bg-blue-100 text-blue-700'
  if (s === 'timeout') return 'bg-yellow-100 text-yellow-700'
  return 'bg-red-100 text-red-700'
}

async function load() {
  loading.value = true
  const res = await API.getLogs(1, 100)
  if (res.success && res.data?.logs) {
    logs.value = res.data.logs
  } else if (res.success && Array.isArray(res.data)) {
    logs.value = res.data
  }
  loading.value = false
}

onMounted(load)
</script>
