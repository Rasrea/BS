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

# Ground Truth（原始凭证）
GROUND_TRUTH = [
    {
        "name": "效果图-客厅现代简约",
        "answer": {"space_type": "客厅", "wall_material": "乳胶漆", "floor_material": "瓷砖", "ceiling_material": "石膏板吊顶"},
    },
    {
        "name": "效果图-客厅轻奢风",
        "answer": {"space_type": "客厅", "wall_material": "墙布", "floor_material": "瓷砖", "ceiling_material": "石膏板吊顶"},
    },
    {
        "name": "效果图-现代空间",
        "answer": {"space_type": "客厅", "wall_material": "乳胶漆", "floor_material": "瓷砖", "ceiling_material": "石膏板吊顶"},
    },
]

# 同义词映射（用于判定准确率，与标准材料库一致）
SYNONYM_GROUPS = [
    # 地面材质
    {"实木地板", "实木复合地板", "强化复合地板", "木地板", "地板", "SPC石塑地板", "PVC地板"},
    {"地砖", "通体砖", "瓷砖", "仿古砖"},
    {"大理石", "石材", "天然石"},
    {"水磨石", "磨石"},
    # 墙面材质
    {"乳胶漆", "墙面漆", "涂料"},
    {"墙布", "墙纸", "壁纸", "墙布/壁纸"},
    {"木饰面", "实木墙板", "护墙板", "木作", "集成墙板"},
    {"艺术漆", "肌理漆"},
    {"硅藻泥", "硅藻土"},
    {"岩板", "薄板"},
    {"软包", "硬包"},
    {"微水泥", "水泥漆", "艺术水泥"},
    {"玻璃", "镜面"},
    {"石膏板", "石膏线条"},
    {"竹木纤维板", "木塑板"},
    # 顶面材质
    {"石膏板吊顶", "石膏板", "石膏吊顶", "吊顶"},
    {"铝扣板", "集成吊顶", "铝扣板吊顶"},
    {"蜂窝大板", "大板吊顶"},
    {"实木吊顶", "木格栅"},
    {"乳胶漆顶面", "乳胶漆吊顶"},
    {"艺术漆顶面", "艺术涂料顶面"},
    {"玻璃顶", "玻璃天窗"},
    # 空间
    {"主卧", "主卧室"},
    {"次卧", "次卧室", "客卧"},
    {"客厅", "起居室", "大堂"},
    {"餐厅", "饭厅", "用餐区"},
    {"厨房", "厨房区"},
]

def is_synonym(a, b):
    """判断两个材质名称是否为同义词"""
    if not a or not b:
        return False
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return True
    for group in SYNONYM_GROUPS:
        lower_group = {x.lower() for x in group}
        if a in lower_group and b in lower_group:
            return True
    return False

# 门禁阈值
GATE_FILL_RATE = 90      # 字段填充率阈值 (%)
GATE_ACCURACY = 80       # 字段准确率阈值 (%)
GATE_TIME_LIMIT = 10     # 单图耗时阈值 (秒)
GATE_SPACE_DEVIATION = 1 # 空间偏差阈值 (最多允许几张空间识别错误)


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


def score_against_ground_truth(entries):
    """将模型结果与 Ground Truth 对比，返回准确率、空间偏差等指标"""
    total_fields = len(entries) * 4
    correct_fields = 0
    wrong_spaces = 0
    details = []
    
    for i, entry in enumerate(entries):
        gt = GROUND_TRUTH[i]
        f = entry["fields"]
        correct = 0
        
        # 逐个字段对比（含同义词判定）
        for field, gt_val in gt["answer"].items():
            model_val = f.get(field, "")
            if model_val and model_val != "(空)" and model_val != "未知":
                if model_val == gt_val or is_synonym(model_val, gt_val):
                    correct += 1
                    correct_fields += 1
        
        # 空间偏差单独统计
        model_space = f.get("space_type", "")
        gt_space = gt["answer"]["space_type"]
        space_ok = (model_space == gt_space) or is_synonym(model_space, gt_space)
        if model_space and model_space != "(空)" and not space_ok:
            wrong_spaces += 1
        
        details.append({"image": entry["image"], "correct": correct, "total": 4})
    
    accuracy = correct_fields / total_fields * 100 if total_fields else 0
    return accuracy, correct_fields, total_fields, wrong_spaces, details


def print_summary(results):
    """打印汇总报告"""
    print(f"\n{'='*60}")
    print(f"  📊 BuildSight 模型基准评测报告")
    print(f"  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📷 测试集: {len(TEST_IMAGES)} 张图片")
    print(f"{'='*60}")
    
    table_header = f"{'模型':<18} {'填充率':<8} {'准确率':<8} {'空间偏差':<8} {'平均耗时':<8} {'评分'}"
    print(f"\n  {table_header}")
    print(f"  {'─'*68}")
    
    gates_passed = True
    model_scores = {}
    
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        avg_time = statistics.mean(times) if times else 0
        
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        
        # 对照 Ground Truth 计算准确率和空间偏差
        accuracy, correct_fields, _, wrong_spaces, details = score_against_ground_truth(entries)
        
        # 综合评分（加权）
        fill_score = min(100, fill_rate)
        accuracy_score = accuracy
        space_score = max(0, 100 - (wrong_spaces / 3 * 100))
        time_score = max(0, 100 - ((avg_time - 1) / 9 * 100) if avg_time > 1 else 100)
        composite = fill_score * 0.20 + accuracy_score * 0.40 + space_score * 0.25 + time_score * 0.15
        
        star_count = max(1, min(5, int(composite / 20)))
        stars = "★" * star_count + "☆" * (5 - star_count)
        model_scores[model] = {"composite": composite, "accuracy": accuracy, "wrong_spaces": wrong_spaces, "fill_rate": fill_rate}
        
        if fill_rate < GATE_FILL_RATE or accuracy < GATE_ACCURACY or wrong_spaces > GATE_SPACE_DEVIATION:
            gates_passed = False
        
        print(f"  {model:<18} {fill_rate:<6.0f}%  {accuracy:<6.1f}%  {wrong_spaces}/3{' ':>5} {avg_time:<6.1f}s {stars}")
    
    # 综合胜出
    if model_scores:
        winner = max(model_scores, key=lambda m: model_scores[m]["composite"])
        print(f"\n  {'─'*68}")
        print(f"  🏆 综合胜出: \033[1m{winner}\033[0m  (评分 {model_scores[winner]['composite']:.1f})")
        print(f"  {'─'*68}")
    
    # 门禁结果
    print(f"\n  ╔═ 门禁检查 ═╗")
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        max_time = max(times) if times else 0
        accuracy, _, _, wrong_spaces, _ = score_against_ground_truth(entries)
        
        fill_ok = fill_rate >= GATE_FILL_RATE
        time_ok = max_time <= GATE_TIME_LIMIT
        acc_ok = accuracy >= GATE_ACCURACY
        space_ok = wrong_spaces <= GATE_SPACE_DEVIATION
        
        issues = []
        if not fill_ok: issues.append(f"填充率={fill_rate:.0f}%(<{GATE_FILL_RATE}%)")
        if not acc_ok: issues.append(f"准确率={accuracy:.0f}%(<{GATE_ACCURACY}%)")
        if not time_ok: issues.append(f"耗时={max_time:.1f}s(>{GATE_TIME_LIMIT}s)")
        if not space_ok: issues.append(f"空间偏差={wrong_spaces}/3")
        
        status = "✅" if (fill_ok and time_ok and acc_ok and space_ok) else "❌"
        extra = f"  {'⚠️ ' + '; '.join(issues) if issues else ''}"
        print(f"  ║ {status} {model:<18} 填充率={fill_rate:.0f}% 准确率={accuracy:.0f}% 耗时={max_time:.1f}s 空间偏差={wrong_spaces}/3{extra}")
    
    print(f"  ╚═{'═'*40}╝")
    
    if not gates_passed:
        print(f"\n  ⚠️  门禁未通过！请检查以上 ❌ 项")
    
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
    lines.append("| 模型 | 字段填充率 | 字段准确率 | 空间偏差 | 平均耗时 | 综合评分 |")
    lines.append("|------|-----------|-----------|---------|---------|---------|\n")
    
    for model, entries in results.items():
        total_fields = len(entries) * 4
        filled_fields = sum(e["filled"] for e in entries)
        times = [e["time_s"] for e in entries if e["time_s"] > 0]
        avg_time = statistics.mean(times) if times else 0
        fill_rate = filled_fields / total_fields * 100 if total_fields else 0
        accuracy, _, _, wrong_spaces, _ = score_against_ground_truth(entries)
        fill_score = min(100, fill_rate)
        accuracy_score = accuracy
        space_score = max(0, 100 - (wrong_spaces / 3 * 100))
        time_score = max(0, 100 - ((avg_time - 1) / 9 * 100) if avg_time > 1 else 100)
        composite = fill_score * 0.20 + accuracy_score * 0.40 + space_score * 0.25 + time_score * 0.15
        lines.append(f"| {model} | {fill_rate:.0f}% | {accuracy:.0f}% | {wrong_spaces}/3 | {avg_time:.1f}s | {composite:.1f} |\n")
    
    lines.append("\n### Ground Truth（原始凭证真值）\n")
    lines.append("| 图片 | 空间类型 | 墙面材质 | 地面材质 | 顶面材质 |")
    lines.append("|------|----------|----------|----------|----------|")
    for gt in GROUND_TRUTH:
        a = gt["answer"]
        lines.append(f"| {gt['name']} | {a['space_type']} | {a['wall_material']} | {a['floor_material']} | {a['ceiling_material']} |")
    lines.append("")
    
    lines.append("\n## 逐项详情\n")
    for model, entries in results.items():
        lines.append(f"### {model}\n")
        _, _, _, _, details = score_against_ground_truth(entries)
        lines.append("| 图片 | 空间(应→实) | 墙面(应→实) | 地面(应→实) | 顶面(应→实) | 正确数 | 耗时 |")
        lines.append("|------|-------------|-------------|-------------|-------------|:------:|------|")
        for i, e in enumerate(entries):
            fields_dict = e["fields"]
            gt = GROUND_TRUTH[i]["answer"]
            d = details[i] if i < len(details) else {"correct": 0, "total": 4}
            
            def cmp(field, gt_val, fd):
                model_val = fd.get(field, "")
                ok = model_val and model_val != "(空)" and (model_val == gt_val or is_synonym(model_val, gt_val))
                return f"{gt_val}→{model_val}" + (" ✅" if ok else " ❌")
            
            sf = cmp("space_type", gt["space_type"], fields_dict)
            wf = cmp("wall_material", gt["wall_material"], fields_dict)
            ff = cmp("floor_material", gt["floor_material"], fields_dict)
            cf = cmp("ceiling_material", gt["ceiling_material"], fields_dict)
            
            status = "✅" if d["correct"] >= 4 else "⚠️"
            lines.append(f"| {status} {e['image']} | {sf} | {wf} | {ff} | {cf} | {d['correct']}/4 | {e['time_s']}s |")
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
        accuracy, _, _, wrong_spaces, _ = score_against_ground_truth(entries)
        fill_ok = fill_rate >= GATE_FILL_RATE
        time_ok = max_time <= GATE_TIME_LIMIT
        acc_ok = accuracy >= GATE_ACCURACY
        space_ok = wrong_spaces <= GATE_SPACE_DEVIATION
        if not (fill_ok and time_ok and acc_ok and space_ok):
            all_pass = False
            issues = []
            if not fill_ok: issues.append(f"填充率={fill_rate:.0f}%(<{GATE_FILL_RATE}%)")
            if not acc_ok: issues.append(f"准确率={accuracy:.0f}%(<{GATE_ACCURACY}%)")
            if not time_ok: issues.append(f"耗时={max_time:.1f}s(>{GATE_TIME_LIMIT}s)")
            if not space_ok: issues.append(f"空间偏差={wrong_spaces}/3")
            lines.append(f"- ❌ **{model}**: {'; '.join(issues)}")
    
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
