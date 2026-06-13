#!/usr/bin/env python3
"""
BuildSight 模型视觉识别 Benchmark 基准评测脚本
================================================
用途: 标准化多模型对比评测，输出可归档的基准报告
用法:
    python3 docs/03-规范/benchmark_runner.py              # 全量三模型对比
    python3 docs/03-规范/benchmark_runner.py --model qwen2.5:7b  # 单模型快速验证
    python3 docs/03-规范/benchmark_runner.py --output report.md  # 输出到文件

门禁阈值:
    - 字段填充率 < 90% → 告警
    - 单图耗时 > 10s   → 性能告警
    - 测试集缺失       → 中止
"""
import os
import sys
import json
import time
import argparse
import statistics
from datetime import datetime

# 确保 backend 在路径中
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
sys.path.insert(0, os.path.join(PROJECT_DIR, "backend"))

try:
    from image_recognizer import recognize_image
except ImportError as e:
    print(f"❌ 无法导入 image_recognizer: {e}")
    print(f"   请确认在项目根目录下运行，或 PYTHONPATH 包含 backend/")
    sys.exit(1)

# ═══════════════════════════════════════════════
# 配置区
# ═══════════════════════════════════════════════

# 测试图片路径（不允许修改）
TEST_IMAGES = [
    {
        "name": "效果图-客厅现代简约",
        "path": os.path.join(PROJECT_DIR, "backend/file/附件/效果图/22911849bb37bd5d42451e6346ab5afd.jpg"),
    },
    {
        "name": "效果图-客厅轻奢风",
        "path": os.path.join(PROJECT_DIR, "backend/file/附件/效果图/5dbed8b4d235b58b57a0d128a4182831.jpg"),
    },
    {
        "name": "效果图-现代空间",
        "path": os.path.join(PROJECT_DIR, "backend/file/附件/效果图/493d3247f2aa51b51b778debd70b9e74.jpg"),
    },
]

# 待测模型列表
DEFAULT_MODELS = ["llava:7b", "qwen2.5:7b", "qwen2.5vl:latest"]

# 门禁阈值
GATE_FILL_RATE = 90   # 字段填充率阈值 (%)
GATE_TIME_LIMIT = 10  # 单图耗时阈值 (秒)


def check_prerequisites(models):
    """检查前置条件：测试集存在、模型可用"""
    warnings = []
    
    # 检查测试集
    for img in TEST_IMAGES:
        if not os.path.isfile(img["path"]):
            warnings.append(f"❌ 测试图片缺失: {img['name']} ({img['path']})")
    
    # 检查模型
    import subprocess
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        available = r.stdout.lower()
        for m in models:
            if m not in available:
                warnings.append(f"⚠️ 模型未安装: {m}（将被跳过）")
    except Exception as e:
        warnings.append(f"⚠️ 无法检查 Ollama 状态: {e}")
    
    return warnings


def run_benchmark(models):
    """执行基准测试，返回结果字典"""
    results = {}
    
    for model in models:
        print(f"\n  ┌─ {'─'*40}")
        print(f"  │ 🔍 测试模型: {model}")
        print(f"  └─ {'─'*40}")
        
        model_results = []
        for img in TEST_IMAGES:
            if not os.path.isfile(img["path"]):
                model_results.append({
                    "image": img["name"],
                    "error": "图片文件不存在",
                    "time_s": 0,
                    "fields": {},
                    "filled": 0,
                })
                continue
            
            start = time.time()
            try:
                result = recognize_image(img["path"], model)
            except Exception as e:
                result = {"error": str(e)}
            elapsed = time.time() - start
            
            structured = result.get("structured", 
                          result.get("spaces", [{}])[0] if result.get("spaces") else {})
            if isinstance(structured, dict):
                space = structured.get("space_type", structured.get("type", structured.get("space", "")))
                wall = structured.get("wall_material", "")
                floor = structured.get("floor_material", "")
                ceiling = structured.get("ceiling_material", "")
            else:
                space = wall = floor = ceiling = ""
            
            fields = {
                "space_type": space or "(空)",
                "wall_material": wall or "(空)",
                "floor_material": floor or "(空)",
                "ceiling_material": ceiling or "(空)",
            }
            filled = sum(1 for v in fields.values() if v != "(空)" and v != "未知")
            
            entry = {
                "image": img["name"],
                "time_s": round(elapsed, 1),
                "fields": fields,
                "filled": filled,
                "error": result.get("error"),
            }
            model_results.append(entry)
            
            status = "✅" if filled >= 3 else "⚠️"
            print(f"    {status} {img['name']:<20} ({elapsed:.1f}s) "
                  f"空间={fields['space_type']:<8} 墙={fields['wall_material']:<8} "
                  f"地={fields['floor_material']:<8} 顶={fields['ceiling_material']}")
            if result.get("error"):
                print(f"       ⚠ 错误: {result['error']}")
        
        results[model] = model_results
    
    return results


def print_summary(results):
    """打印汇总报告"""
    print(f"\n{'='*60}")
    print(f"  📊 BuildSight 模型基准评测报告")
    print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📷 测试集: {len(TEST_IMAGES)} 张图片")
    print(f"{'='*60}")
    
    table_header = f"{'模型':<20} {'填充率':<10} {'平均耗时':<10} {'总耗时':<10} {'偏差':<10} {'评分'}"
    print(f"\n  {table_header}")
    print(f"  {'─'*60}")
    
    gates_passed = True
    all_filled = {}
    
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        avg_time = statistics.mean(times) if times else 0
        total_time = sum(times)
        
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        all_filled[model] = filled_fields
        
        # 检查空间偏差
        wrong_spaces = sum(1 for e in entries if e["fields"]["space_type"] == "(空)")
        stars = "★" * max(1, int(fill_rate / 20))
        
        if fill_rate < GATE_FILL_RATE:
            gates_passed = False
        
        print(f"  {model:<20} {fill_rate:<8.0f}% {avg_time:<8.1f}s {total_time:<8.1f}s "
              f"{wrong_spaces:<8} {stars}")
    
    # 胜出
    winner = max(all_filled, key=all_filled.get) if all_filled else "无"
    print(f"\n  {'─'*60}")
    print(f"  🏆 综合胜出: \033[1m{winner}\033[0m")
    print(f"  {'─'*60}")
    
    # 门禁结果
    print(f"\n  ╔═ 门禁检查 ═╗")
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        max_time = max(times) if times else 0
        
        fill_ok = fill_rate >= GATE_FILL_RATE
        time_ok = max_time <= GATE_TIME_LIMIT
        
        status = "✅" if (fill_ok and time_ok) else "❌"
        print(f"  ║ {status} {model:<20} 填充率={fill_rate:.0f}%{' ' if fill_ok else '(FAIL)'}  耗时={max_time:.1f}s{' ' if time_ok else '(SLOW)'}")
    
    print(f"  ╚═{'═'*20}╝")
    
    if not gates_passed:
        print(f"\n  ⚠️  门禁未通过！填充率低于 {GATE_FILL_RATE}% 阈值")
    
    return gates_passed


def save_report(results, output_path=None):
    """保存报告为 Markdown 文件"""
    if output_path is None:
        report_dir = os.path.join(SCRIPT_DIR, "benchmark_reports")
        os.makedirs(report_dir, exist_ok=True)
        output_path = os.path.join(report_dir, f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    lines = []
    lines.append(f"# BuildSight 模型基准评测报告\n")
    lines.append(f"**评测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**测试图片**: {len(TEST_IMAGES)} 张\n")
    lines.append(f"**Ollama 地址**: localhost:11434\n")
    lines.append(f"**对比模型**: {' vs '.join(results.keys())}\n")
    lines.append("---\n")
    
    # 汇总表
    lines.append("## 总体指标对比\n")
    lines.append("| 模型 | 字段填充率 | 平均耗时 | 总耗时 | 空间偏差 |")
    lines.append("|------|-----------|---------|--------|---------|")
    
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        avg_time = statistics.mean(times) if times else 0
        total_time = sum(times)
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        wrong = sum(1 for e in entries if e["fields"]["space_type"] == "(空)")
        lines.append(f"| {model} | {fill_rate:.0f}% | {avg_time:.1f}s | {total_time:.1f}s | {wrong}/3 |")
    
    lines.append("\n## 逐项详情\n")
    for model, entries in results.items():
        lines.append(f"### {model}\n")
        lines.append("| 图片 | 空间 | 墙面 | 地面 | 顶面 | 填充 | 耗时 |")
        lines.append("|------|------|------|------|------|------|------|")
        for e in entries:
            f = e["fields"]
            filled_str = f"{e['filled']}/4"
            status = "✅" if e["filled"] >= 3 else "❌"
            lines.append(f"| {status} {e['image']} | {f['space_type']} | {f['wall_material']} | "
                        f"{f['floor_material']} | {f['ceiling_material']} | {filled_str} | {e['time_s']}s |")
        lines.append("")
    
    # 门禁
    lines.append("## 门禁检查\n")
    all_pass = True
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        max_time = max(times) if times else 0
        fill_ok = fill_rate >= GATE_FILL_RATE
        time_ok = max_time <= GATE_TIME_LIMIT
        if not (fill_ok and time_ok):
            all_pass = False
            lines.append(f"- ❌ **{model}**: 填充率={fill_rate:.0f}%{' (低于阈值)' if not fill_ok else ''}"
                        f"{', 耗时=' + str(max_time) + 's (超时)' if not time_ok else ''}")
    
    if all_pass:
        lines.append("- ✅ **全部通过**\n")
    lines.append(f"\n---\n*报告由 benchmark_runner.py 自动生成*")
    
    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  📝 报告已保存: {output_path}")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="BuildSight 模型视觉识别基准评测")
    parser.add_argument("--model", help="指定单个模型（默认全量对比）")
    parser.add_argument("--output", help="报告输出路径")
    args = parser.parse_args()
    
    models = [args.model] if args.model else DEFAULT_MODELS
    
    print(f"\n{'='*60}")
    print(f"  BuildSight 模型基准评测")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 前置检查
    warnings = check_prerequisites(models)
    for w in warnings:
        print(f"  {w}")
    
    active_models = [m for m in models if not any(f"未安装: {m}" in w for w in warnings)]
    if not active_models:
        print("\n❌ 无可用模型，中止")
        sys.exit(1)
    
    print(f"\n  待测模型: {', '.join(active_models)}")
    print(f"  测试图片: {len(TEST_IMAGES)} 张\n")
    
    # 执行
    results = run_benchmark(active_models)
    
    # 汇总
    passed = print_summary(results)
    
    # 保存报告
    report_path = save_report(results, args.output)
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
