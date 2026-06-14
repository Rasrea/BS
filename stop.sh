#!/bin/bash
# BuildSight 停止脚本
# 停止后端服务 (端口8100)

PORT=8100
if lsof -i :$PORT -sTCP:LISTEN &>/dev/null 2>&1; then
    PIDS=$(lsof -ti :$PORT 2>/dev/null)
    echo "⏹️  正在停止 BuildSight 服务 (PID: $PIDS)..."
    kill -9 $PIDS 2>/dev/null
    sleep 1
    echo "✅ 服务已停止"
else
    echo "ℹ️  端口 $PORT 没有运行中的服务"
fi
