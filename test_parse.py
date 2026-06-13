#!/usr/bin/env python3
"""启动服务并测试解析"""
import subprocess
import time
import requests
import os

# 1. 检查 Ollama LLaVA
print("[1] 检查 Ollama LLaVA...")
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    has_llava = any("llava" in m["name"].lower() for m in r.json().get("models", []))
    print(f"   LLaVA: {'✅ 就绪' if has_llava else '❌ 未找到'}")
except:
    print("   ❌ Ollama 未启动")
    has_llava = False

# 2. 启动后端服务
print("\n[2] 启动后端服务...")
proc = subprocess.Popen(
    ["/home/sd317/.hermes/hermes-agent/venv/bin/python", "/home/sd317/cad/backend/main.py"],
    cwd="/home/sd317/cad/backend",
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(5)
print("   服务已启动")

# 3. 测试健康检查
print("\n[3] 健康检查...")
try:
    r = requests.get("http://localhost:8100/api/health", timeout=5)
    print(f"   ✅ {r.json()}")
except Exception as e:
    print(f"   ❌ {e}")

# 4. 测试配置端点
print("\n[4] 配置信息...")
try:
    r = requests.get("http://localhost:8100/api/config", timeout=5)
    print(f"   {r.json()}")
except Exception as e:
    print(f"   ❌ {e}")

# 5. 测试解析 DWG
print("\n[5] 测试解析 DWG 图纸...")
try:
    with open("/home/sd317/cad/backend/file/附件/施工图文件/12345678.dwg", "rb") as f:
        r = requests.post("http://localhost:8100/api/analyze", files={"cad_file": ("12345678.dwg", f)}, timeout=120)
    data = r.json()
    cad = data.get("cad_result", {})
    spaces = cad.get("spaces", [])
    print(f"   解析方法: {cad.get('parse_method', '?')}")
    print(f"   识别房间数: {len(spaces)}")
    if spaces:
        for s in spaces[:5]:
            print(f"     - {s.get('name', 'N/A')}: {s.get('area_sqm', '?')}㎡")
    if cad.get('error'):
        print(f"   ⚠️ 警告: {cad['error']}")
except Exception as e:
    print(f"   ❌ DWG 解析失败: {e}")

# 6. 测试解析效果图文
print("\n[6] 测试解析效果图文...")
try:
    with open("/home/sd317/cad/backend/file/附件/效果图/22911849bb37bd5d42451e6346ab5afd.jpg", "rb") as f:
        r = requests.post("http://localhost:8100/api/analyze", files={"image_file": ("效果图1.jpg", f)}, timeout=180)
    data = r.json()
    img = data.get("image_result", {})
    print(f"   成功: {img.get('success', '?')}")
    if img.get('error'):
        print(f"   错误: {img['error'][:200]}")
    if img.get('overall_style'):
        print(f"   风格: {img['overall_style']}")
except Exception as e:
    print(f"   ❌ 效果图文解析失败: {e}")

# 7. 清理
print("\n[7] 清理...")
proc.terminate()
proc.wait(timeout=10)
print("   ✅ 完成!")
