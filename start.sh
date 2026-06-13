#!/bin/bash
# BuildSight 一键启动脚本
# 用法: bash start.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
PORT=8100

echo "================================"
echo " BuildSight 智能报价系统 启动"
echo "================================"

# 1. 检查 Python
echo "[1/4] 检查 Python..."
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 Python，请先安装 Python 3.10+"
    exit 1
fi
echo "   Python: $($PYTHON --version)"

# 2. 安装依赖
echo "[2/4] 安装后端依赖..."
cd "$BACKEND_DIR"
$PYTHON -m pip install -q fastapi uvicorn[standard] python-multipart aiofiles openpyxl pandas httpx 2>/dev/null
echo "   ✅ 依赖安装完成"

# 3. 检查 Ollama
echo "[3/4] 检查 Ollama 模型..."
if command -v ollama &>/dev/null; then
    NEEDED=("qwen2.5:7b" "llava:7b")
    for model in "${NEEDED[@]}"; do
        if ollama list 2>/dev/null | grep -q "$model"; then
            echo "   ✅ $model 已安装"
        else
            echo "   ⏳ 正在拉取 $model ..."
            ollama pull "$model"
            echo "   ✅ $model 安装完成"
        fi
    done
else
    echo "   ⚠️ 未检测到 Ollama，请先安装: https://ollama.com"
    echo "   安装后执行: ollama pull qwen2.5:7b && ollama pull llava:7b"
fi

# 4. 启动服务
echo "[4/4] 启动后端服务..."
echo "   端口: $PORT"
echo "   访问: http://localhost:$PORT/"
echo "================================"
$PYTHON main.py
