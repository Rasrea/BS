<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { AcApDocManager, AcEdOpenMode, AcApFontUtil } from "@mlightcad/cad-simple-viewer";

const props = defineProps({
  file: { type: Object, default: null }, // { name, buffer }
});
const emit = defineEmits(["close"]);

const containerRef = ref(null);
const loading = ref(false);
const loadingText = ref("加载中...");
const error = ref(null);
const hasFile = ref(false);

let docManager = null;
let initialized = false;

function initEngine() {
  if (initialized && docManager) return true;
  try {
    docManager = AcApDocManager.createInstance({
      container: containerRef.value,
      autoResize: true,
      baseUrl: "https://cdn.jsdelivr.net/gh/mlightcad/cad-data@main/",
      webworkerFileUrls: {
        mtextRender: "./workers/mtext-renderer-worker.js",
        dxfParser: "./workers/dxf-parser-worker.js",
        dwgParser: "./workers/libredwg-parser-worker.js",
      },
    });
    initialized = true;
    return true;
  } catch (err) {
    console.error("[CAD Viewer] Init failed:", err);
    error.value = "引擎初始化失败: " + err.message;
    return false;
  }
}

async function doLoad(file) {
  error.value = null;
  loading.value = true;
  loadingText.value = "加载中...";

  await nextTick();

  if (!initEngine()) {
    loading.value = false;
    return;
  }

  try {
    const ext = file.name.split(".").pop().toLowerCase();
    if (ext === "dwg") {
      loadingText.value = "解析 DWG 文件 (WASM)... 大文件可能需要较长时间";
    } else {
      loadingText.value = "解析 DXF 文件...";
    }

    const success = await docManager.openDocument(file.name, file.buffer, {
      minimumChunkSize: 1000,
      mode: AcEdOpenMode.Write,
    });

    if (!success) {
      throw new Error(
        ext === "dwg"
          ? "DWG 解析失败，文件版本可能不兼容或格式损坏"
          : "文件解析失败，格式可能不正确"
      );
    }

    await nextTick();
    try {
      docManager?.sendStringToExecute?.("zoom\nextents");
    } catch (zoomErr) {
      console.warn("[CAD Viewer] Auto-fit failed:", zoomErr);
    }

    hasFile.value = true;
  } catch (err) {
    console.error("[CAD Viewer] Load error:", err);
    error.value = err.message || "加载文件失败";
  } finally {
    loading.value = false;
  }
}

function fitView() {
  try { docManager?.sendStringToExecute?.("zoom\nextents"); } catch (e) {}
}
function zoomIn() {
  try { docManager?.sendStringToExecute?.("zoom\nscale\n2x"); } catch (e) {}
}
function zoomOut() {
  try { docManager?.sendStringToExecute?.("zoom\nscale\n.5x"); } catch (e) {}
}

async function preCacheCommonFonts() {
  const baseUrl = "https://cdn.jsdelivr.net/gh/mlightcad/cad-data@main/fonts/";
  const commonFonts = ["txt.shx", "simplex.shx", "complex.shx"];
  for (const fontName of commonFonts) {
    try {
      const url = baseUrl + fontName;
      const response = await fetch(url);
      if (response.ok) {
        const blob = await response.blob();
        const file = new File([blob], fontName);
        await AcApFontUtil.cacheFont(file);
      }
    } catch (e) {
      // silently ignore font pre-cache failures
    }
  }
}

function cleanup() {
  hasFile.value = false;
  loading.value = false;
  error.value = null;
  if (docManager) {
    try { docManager.destroy(); } catch (e) {}
    docManager = null;
    initialized = false;
  }
}

watch(
  () => props.file,
  (f) => {
    if (f) doLoad(f);
    else cleanup();
  },
  { immediate: true }
);

onMounted(async () => {
  await nextTick();
  if (containerRef.value) {
    initEngine();
    preCacheCommonFonts().catch(() => {});
  }
  if (props.file) doLoad(props.file);
});

onBeforeUnmount(() => {
  cleanup();
});

defineExpose({ fitView, zoomIn, zoomOut, cleanup });
</script>

<template>
  <div class="cad-viewer-root">
    <!-- 顶部栏 -->
    <div class="viewer-topbar">
      <div class="flex items-center gap-3">
        <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span class="text-sm font-medium text-gray-200">{{ props.file?.name || 'CAD 预览' }}</span>
      </div>
      <button @click="emit('close')" class="close-btn-top">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- 画布区 -->
    <div ref="containerRef" class="cad-canvas"></div>

    <!-- 空状态 -->
    <div v-if="!hasFile && !loading && !error" class="overlay empty-overlay">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
      </svg>
      <p>正在加载图纸预览...</p>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="overlay loading-overlay">
      <div class="spinner"></div>
      <p class="text-sm text-gray-400 mt-3">{{ loadingText }}</p>
    </div>

    <!-- 错误 -->
    <div v-if="error" class="overlay error-overlay">
      <div class="text-3xl mb-2">⚠️</div>
      <p class="text-sm text-red-400 font-medium">加载失败</p>
      <p class="text-xs text-gray-500 mt-1 max-w-sm text-center">{{ error }}</p>
      <button class="retry-btn mt-4" @click="props.file && doLoad(props.file)">重试</button>
    </div>

    <!-- 底部工具栏 -->
    <div v-if="hasFile && !loading" class="toolbar">
      <button title="适应窗口" @click="fitView">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
        </svg>
      </button>
      <button title="放大" @click="zoomIn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          <line x1="11" y1="8" x2="11" y2="14" /><line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      </button>
      <button title="缩小" @click="zoomOut">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          <line x1="8" y1="11" x2="14" y2="11" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.cad-viewer-root {
  position: relative;
  width: 100%;
  height: 100vh;
  background: #1a1d2e;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.viewer-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(15, 23, 42, 0.95);
  border-bottom: 1px solid rgba(99, 102, 241, 0.15);
  flex-shrink: 0;
  z-index: 30;
}

.close-btn-top {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
}
.close-btn-top:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.cad-canvas {
  flex: 1;
  min-height: 0;
}
.cad-canvas :deep(canvas) {
  display: block;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.empty-overlay {
  background: #1a1d2e;
  color: #64748b;
  font-size: 14px;
}
.empty-overlay svg {
  margin-bottom: 12px;
  opacity: 0.5;
}

.loading-overlay {
  background: rgba(26, 29, 46, 0.95);
}
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-overlay {
  background: rgba(26, 29, 46, 0.95);
}
.retry-btn {
  padding: 7px 22px;
  border: 1px solid rgba(239, 68, 68, 0.4);
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.retry-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}

.toolbar {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 10px;
  z-index: 25;
}
.toolbar button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
}
.toolbar button:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.3);
  color: #e2e8f0;
}
</style>
