#!/bin/bash
# ==============================================
# BuildSight v0.8.3 — 家装智能报价系统 一键启动
# ==============================================
# 用法: bash start.sh
# 依赖: Python 3.10+, Ollama
# ==============================================

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PORT=8100

echo "╔══════════════════════════════════════╗"
echo "║   BuildSight  v0.8.3                ║"
echo "║   家装智能自动报价系统              ║"
echo "╠══════════════════════════════════════╣"
echo "║  CAD解析 · AI识别 · 融合报价 · 导出 ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. 检查 Python ──
echo "[1/4] 检查 Python..."
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "  ❌ 未找到 Python，请安装 Python 3.10+"
    exit 1
fi
echo "  ✅ $($PYTHON --version)"

# ── 2. 安装依赖 ──
echo "[2/4] 安装后端依赖..."
cd "$BACKEND_DIR"
if [ -f requirements.txt ]; then
    $PYTHON -m pip install -q -r requirements.txt 2>/dev/null
else
    $PYTHON -m pip install -q fastapi uvicorn[standard] python-multipart aiofiles openpyxl pandas httpx 2>/dev/null
fi
echo "  ✅ 依赖安装完成"

# ── 3. 检查 Ollama 模型 ──
echo "[3/4] 检查 Ollama 模型..."
if command -v ollama &>/dev/null; then
    # 检查Ollama服务是否运行
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "  ⚠️  Ollama 服务未运行，正在启动..."
        ollama serve &
        sleep 3
    fi
    echo "  ✅ Ollama 服务运行中"

    NEEDED=("qwen2.5:7b" "llava:7b")
    for model in "${NEEDED[@]}"; do
        if ollama list 2>/dev/null | grep -q "$model"; then
            echo "  ✅ 模型 $model 已安装"
        else
            echo "  ⏳ 正在拉取模型 $model（首次需要下载，约5-10分钟）..."
            ollama pull "$model"
            echo "  ✅ 模型 $model 安装完成"
        fi
    done
else
    echo "  ⚠️  未检测到 Ollama"
    echo "     请先安装: https://ollama.com"
    echo "     安装后执行: ollama pull qwen2.5:7b"
fi

# ── 4. 启动服务 ──
echo ""
echo "[4/4] 启动后端服务..."
echo ""
echo "  📍 地址: http://localhost:$PORT/"
echo "  📂 目录: $BACKEND_DIR"
echo ""
echo "  🔬 测试视觉模型: 打开后点「识别测试」tab"
echo "  🏠 开始使用: 上传CAD或效果图 → 开始分析"
echo ""
echo "════════════════════════════════════════"
echo ""

$PYTHON main.py
