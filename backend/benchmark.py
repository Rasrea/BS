"""
三模型 Benchmark 对比评测：llava:7b vs qwen2.5:7b vs qwen2.5vl:latest
对比结构化识别的准确率、字段匹配率、填写率、未知率、响应时间等指标
"""
import os
import sys
import json
import time
import statistics
from datetime import datetime

# 确保 backend 在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_recognizer import recognize_image

# ============================================================
# 1. Benchmark Dataset - 5张测试图片
# ============================================================
# expected 值为人工粗略判断，主要看模型间相对差异
benchmark_dataset = [
    {
        "name": "效果图-客厅现代简约",
        "image_path": "/home/sd317/cad/backend/uploads/效果图/5dbed8b4d235b58b57a0d128a4182831.jpg",
        "expected": {
            "space_type": "客厅",
            "wall_material": "乳胶漆",
            "floor_material": "木地板",
            "ceiling_material": "石膏板吊顶",
            "decor_style": "现代简约",
            "remark": "",
        }
    },
    {
        "name": "效果图-卧室温馨",
        "image_path": "/home/sd317/cad/backend/uploads/效果图/22911849bb37bd5d42451e6346ab5afd.jpg",
        "expected": {
            "space_type": "卧室",
            "wall_material": "墙布",
            "floor_material": "木地板",
            "ceiling_material": "石膏板吊顶",
            "decor_style": "现代简约",
            "remark": "",
        }
    },
    {
        "name": "效果图-餐厅轻奢",
        "image_path": "/home/sd317/cad/backend/uploads/效果图/493d3247f2aa51b51b778debd70b9e74.jpg",
        "expected": {
            "space_type": "餐厅",
            "wall_material": "乳胶漆",
            "floor_material": "瓷砖",
            "ceiling_material": "石膏板吊顶",
            "decor_style": "轻奢",
            "remark": "",
        }
    },
    {
        "name": "室内-客厅休闲",
        "image_path": "/home/sd317/cad/backend/uploads/bba16d4e-1d5_image.jpg",
        "expected": {
            "space_type": "客厅",
            "wall_material": "乳胶漆",
            "floor_material": "木地板",
            "ceiling_material": "石膏板吊顶",
            "decor_style": "现代简约",
            "remark": "",
        }
    },
    {
        "name": "室内-现代空间",
        "image_path": "/home/sd317/cad/backend/uploads/c9dbb3e399ba_img.jpg",
        "expected": {
            "space_type": "客厅",
            "wall_material": "乳胶漆",
            "floor_material": "瓷砖",
            "ceiling_material": "石膏板吊顶",
            "decor_style": "现代简约",
            "remark": "",
        }
    },
]

# 重点关注的材质字段
MATERIAL_FIELDS = ["wall_material", "floor_material", "ceiling_material"]
ALL_FIELDS = ["space_type", "wall_material", "floor_material", "ceiling_material", "decor_style", "remark"]


def field_match(actual: str, expected: str) -> bool:
    """判断字段是否匹配（宽松匹配：只要实际值包含期望值或部分关键词匹配）"""
    a = actual.strip().lower() if actual else ""
    e = expected.strip().lower() if expected else ""
    if not e or e == "未知":
        return True  # expected 为空或未知，不扣分
    # 精确匹配
    if a == e:
        return True
    # 包含关系
    if e in a or a in e:
        return True
    # 关键词匹配
    keywords = {
        "木地板": ["木地板", "地板", "木材", "木"],
        "瓷砖": ["瓷砖", "地砖", "砖", "大理石"],
        "乳胶漆": ["乳胶漆", "涂料", "漆", "墙面漆"],
        "墙布": ["墙布", "壁纸", "墙纸", "布艺"],
        "石膏板吊顶": ["石膏板", "吊顶", "石膏"],
        "现代简约": ["现代简约", "现代", "简约", "简约现代"],
        "轻奢": ["轻奢", "轻奢风", "现代轻奢"],
    }
    for key, syns in keywords.items():
        if e in syns and any(s in a for s in syns):
            return True
    return False


def run_benchmark(model_name: str) -> dict:
    """
    对 benchmark_dataset 中所有图片逐一调用结构化识别
    返回统计结果
    """
    results = []
    for idx, item in enumerate(benchmark_dataset):
        name = item["name"]
        img_path = item["image_path"]
        expected = item["expected"]

        print(f"  [{model_name}] 识别: {name} ...")
        start_time = time.time()

        try:
            result = recognize_image(img_path, model=model_name)
        except Exception as e:
            result = {
                "success": False,
                "structured": {},
                "raw_response": "",
                "model_used": model_name,
                "error": str(e),
            }

        elapsed = time.time() - start_time
        structured = result.get("structured", {})
        success = result.get("success", False)
        error = result.get("error", "")

        # 计算字段匹配数（所有字段）
        matched_fields = 0
        total_fields = 0
        field_details = {}
        for key, exp_val in expected.items():
            if key not in structured:
                continue
            act_val = structured.get(key, "")
            total_fields += 1
            is_match = field_match(act_val, exp_val)
            if is_match:
                matched_fields += 1
            field_details[key] = {
                "expected": exp_val,
                "actual": act_val,
                "match": is_match,
            }

        # 材质字段匹配数
        material_matched = 0
        material_total = 0
        for key in MATERIAL_FIELDS:
            if key in structured and key in expected:
                material_total += 1
                if field_match(structured.get(key, ""), expected[key]):
                    material_matched += 1

        # 字段填写率：非空字段数 / 总字段数
        total_slots = len(structured) if structured else len(ALL_FIELDS)
        filled_fields = sum(1 for v in structured.values() if v and v != "未知")
        fill_rate = filled_fields / total_slots if total_slots > 0 else 0

        # "未知"字段比例
        unknown_fields = sum(1 for v in structured.values() if v == "未知" or not v)
        unknown_rate = unknown_fields / total_slots if total_slots > 0 else 0

        # 匹配准确率
        accuracy = matched_fields / total_fields if total_fields > 0 else 0

        entry = {
            "name": name,
            "image_path": img_path,
            "success": success,
            "elapsed": round(elapsed, 2),
            "error": error,
            "structured": structured,
            "matched_fields": matched_fields,
            "total_fields": total_fields,
            "material_matched": material_matched,
            "material_total": material_total,
            "accuracy": round(accuracy, 4),
            "fill_rate": round(fill_rate, 4),
            "unknown_rate": round(unknown_rate, 4),
            "field_details": field_details,
        }
        results.append(entry)

        status = "✓" if success else "✗"
        print(f"    {status} 耗时={elapsed:.1f}s 匹配={matched_fields}/{total_fields} 填写率={fill_rate:.0%} 未知率={unknown_rate:.0%}")

    # 统计汇总
    success_count = sum(1 for r in results if r["success"])
    accuracies = [r["accuracy"] for r in results]
    fill_rates = [r["fill_rate"] for r in results]
    unknown_rates = [r["unknown_rate"] for r in results]
    times = [r["elapsed"] for r in results]

    # 剔除首张冷启动时间
    times_warm = times[1:] if len(times) > 1 else times

    # 材质字段统计
    material_matched_total = sum(r["material_matched"] for r in results)
    material_total_total = sum(r["material_total"] for r in results)

    summary = {
        "model": model_name,
        "total_images": len(results),
        "success_count": success_count,
        "success_rate": round(success_count / len(results), 4) if results else 0,
        "avg_accuracy": round(statistics.mean(accuracies), 4) if accuracies else 0,
        "avg_fill_rate": round(statistics.mean(fill_rates), 4) if fill_rates else 0,
        "avg_unknown_rate": round(statistics.mean(unknown_rates), 4) if unknown_rates else 0,
        "avg_time": round(statistics.mean(times), 2) if times else 0,
        "avg_time_warm": round(statistics.mean(times_warm), 2) if times_warm else 0,
        "min_time": round(min(times), 2) if times else 0,
        "max_time": round(max(times), 2) if times else 0,
        "std_time": round(statistics.stdev(times), 2) if len(times) > 1 else 0,
        "material_accuracy": round(material_matched_total / material_total_total, 4) if material_total_total > 0 else 0,
        "material_matched": material_matched_total,
        "material_total": material_total_total,
        "results": results,
    }
    return summary


def compare_models():
    """对比三个模型：llava:7b, qwen2.5:7b, qwen2.5vl:latest"""
    print("=" * 80)
    print(" 🔬 三模型 Benchmark 对比评测")
    print(f"    时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    测试集: {len(benchmark_dataset)} 张图片")
    print("=" * 80)
    print()

    models = ["llava:7b", "qwen2.5:7b", "qwen2.5vl:latest"]
    summaries = {}

    for model in models:
        print(f"\n{'─' * 80}")
        print(f" 运行模型: {model}")
        print(f"{'─' * 80}")
        summaries[model] = run_benchmark(model)
        print()

    # 打印对比表格
    print("\n" + "=" * 80)
    print(" 📊 三模型对比结果汇总")
    print("=" * 80)

    header = f"{'指标':<28} {'llava:7b':<18} {'qwen2.5:7b':<18} {'qwen2.5vl':<18}"
    print(header)
    print("-" * 80)

    rows = [
        ("识别成功率", "success_rate", "{:.0%}"),
        ("平均字段匹配率", "avg_accuracy", "{:.1%}"),
        ("材质字段匹配率", "material_accuracy", "{:.1%}"),
        ("平均字段填写率", "avg_fill_rate", "{:.1%}"),
        ("'未知'字段比例", "avg_unknown_rate", "{:.1%}"),
        ("平均响应时间(含首张)", "avg_time", "{:.1f}s"),
        ("平均响应时间(剔除首张)", "avg_time_warm", "{:.1f}s"),
        ("最短响应时间", "min_time", "{:.1f}s"),
        ("最长响应时间", "max_time", "{:.1f}s"),
        ("响应时间标准差", "std_time", "{:.2f}"),
    ]

    for label, key, fmt in rows:
        v1 = summaries["llava:7b"].get(key, 0)
        v2 = summaries["qwen2.5:7b"].get(key, 0)
        v3 = summaries["qwen2.5vl:latest"].get(key, 0)
        print(f"  {label:<26} {fmt.format(v1):<18} {fmt.format(v2):<18} {fmt.format(v3):<18}")

    # 按图片逐项对比
    print("\n" + "─" * 80)
    print(" 📄 逐项对比详情")
    print("─" * 80)

    for i, item in enumerate(benchmark_dataset):
        name = item["name"]
        r1 = summaries["llava:7b"]["results"][i]
        r2 = summaries["qwen2.5:7b"]["results"][i]
        r3 = summaries["qwen2.5vl:latest"]["results"][i]

        print(f"\n  [{i+1}] {name}")
        print(f"       {'':<18} {'llava:7b':<18} {'qwen2.5:7b':<18} {'qwen2.5vl':<18}")
        print(f"  {'成功':<18} {str(r1['success']):<18} {str(r2['success']):<18} {str(r3['success']):<18}")
        print(f"  {'耗时(s)':<18} {r1['elapsed']:<18} {r2['elapsed']:<18} {r3['elapsed']:<18}")
        print(f"  {'匹配率':<18} {r1['matched_fields']}/{r1['total_fields']:<16} {r2['matched_fields']}/{r2['total_fields']:<16} {r3['matched_fields']}/{r3['total_fields']:<16}")
        print(f"  {'填写率':<18} {r1['fill_rate']:.0%}{'':<14} {r2['fill_rate']:.0%}{'':<14} {r3['fill_rate']:.0%}")
        print(f"  {'未知率':<18} {r1['unknown_rate']:.0%}{'':<14} {r2['unknown_rate']:.0%}{'':<14} {r3['unknown_rate']:.0%}")
        if r1.get("error") or r2.get("error") or r3.get("error"):
            print(f"  {'错误':<18} {r1.get('error',''):<18} {r2.get('error',''):<18} {r3.get('error',''):<18}")

    # 存储原始结果
    return summaries


def save_report(summaries: dict):
    """保存报告到markdown"""
    report_path = "/home/sd317/cad/docs/03-规范/模型Benchmark评测报告.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lines = []
    lines.append("# 模型 Benchmark 评测报告\n")
    lines.append(f"**评测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**测试图片数**: {len(benchmark_dataset)} 张\n")
    lines.append(f"**Ollama 地址**: localhost:11434\n")
    lines.append(f"**对比模型**: llava:7b vs qwen2.5:7b vs qwen2.5vl:latest\n")
    lines.append("---\n")

    # 测试集
    lines.append("## 1. 测试数据集\n")
    lines.append("| # | 图片名称 | 空间类型(期望) | 墙面(期望) | 地面(期望) | 吊顶(期望) | 风格(期望) |")
    lines.append("|---|---------|---------------|-----------|-----------|-----------|----------|")
    for i, item in enumerate(benchmark_dataset, 1):
        exp = item["expected"]
        lines.append(f"| {i} | {item['name']} | {exp['space_type']} | {exp['wall_material']} | {exp['floor_material']} | {exp['ceiling_material']} | {exp['decor_style']} |")
    lines.append("")

    # 总体对比
    lines.append("## 2. 总体指标对比\n")
    lines.append("| 指标 | llava:7b | qwen2.5:7b | qwen2.5vl:latest | 胜出模型 |")
    lines.append("|------|---------|-----------|-----------------|---------|")
    for label, key, fmt, better in [
        ("识别成功率", "success_rate", "{:.0%}", "高"),
        ("平均字段匹配率", "avg_accuracy", "{:.1%}", "高"),
        ("材质字段匹配率", "material_accuracy", "{:.1%}", "高"),
        ("平均字段填写率", "avg_fill_rate", "{:.1%}", "高"),
        ("\"未知\"字段比例", "avg_unknown_rate", "{:.1%}", "低"),
        ("平均响应时间(含首张)", "avg_time", "{:.1f}s", "低"),
        ("平均响应时间(剔除首张)", "avg_time_warm", "{:.1f}s", "低"),
        ("最短响应时间", "min_time", "{:.1f}s", "低"),
        ("最长响应时间", "max_time", "{:.1f}s", "低"),
        ("响应时间标准差", "std_time", "{:.2f}", "低"),
    ]:
        v1 = summaries["llava:7b"].get(key, 0)
        v2 = summaries["qwen2.5:7b"].get(key, 0)
        v3 = summaries["qwen2.5vl:latest"].get(key, 0)

        # 选择胜出模型
        vals = {"llava:7b": v1, "qwen2.5:7b": v2, "qwen2.5vl:latest": v3}
        if better == "高":
            winner = max(vals, key=vals.get)
        else:
            winner = min(vals, key=vals.get)

        lines.append(f"| {label} | {fmt.format(v1)} | {fmt.format(v2)} | {fmt.format(v3)} | {winner} |")
    lines.append("")

    # 逐项对比
    lines.append("## 3. 逐项对比详情\n")
    for i, item in enumerate(benchmark_dataset):
        name = item["name"]
        lines.append(f"### 3.{i+1} {name}\n")
        lines.append(f"- **图片路径**: {item['image_path']}\n")

        for model_name in ["llava:7b", "qwen2.5:7b", "qwen2.5vl:latest"]:
            r = summaries[model_name]["results"][i]
            lines.append(f"#### {model_name} 识别结果\n")
            lines.append("| 字段 | 期望值 | 识别值 | 匹配 |")
            lines.append("|------|--------|--------|------|")
            for field in ALL_FIELDS:
                exp_val = item["expected"].get(field, "")
                act_val = r["structured"].get(field, "")
                is_match = "✓" if field_match(act_val, exp_val) else "✗"
                lines.append(f"| {field} | {exp_val} | {act_val} | {is_match} |")
            lines.append(f"\n- **识别成功**: {'✓' if r['success'] else '✗'}")
            lines.append(f"- **响应时间**: {r['elapsed']:.1f}s")
            lines.append(f"- **字段匹配**: {r['matched_fields']}/{r['total_fields']} ({r['accuracy']:.0%})")
            lines.append(f"- **字段填写率**: {r['fill_rate']:.0%}")
            lines.append(f"- **未知字段率**: {r['unknown_rate']:.0%}")
            if r.get("error"):
                lines.append(f"- **错误信息**: {r['error']}")
            lines.append("")

    # 结论
    lines.append("## 4. 结论与建议\n")
    s1 = summaries["llava:7b"]
    s2 = summaries["qwen2.5:7b"]
    s3 = summaries["qwen2.5vl:latest"]

    # 综合评分：准确率*0.4 + 填写率*0.2 + (1-未知率)*0.1 + (1-归一化时间)*0.3
    max_time = max(s1["avg_time"], s2["avg_time"], s3["avg_time"])
    min_time = min(s1["avg_time"], s2["avg_time"], s3["avg_time"])
    time_range = max_time - min_time if max_time != min_time else 1

    def compute_score(s):
        acc_score = s["avg_accuracy"]
        fill_score = s["avg_fill_rate"]
        unknown_score = 1 - s["avg_unknown_rate"]
        time_norm = (max_time - s["avg_time"]) / time_range  # 越快越高
        return acc_score * 0.4 + fill_score * 0.2 + unknown_score * 0.1 + time_norm * 0.3

    scores = {
        "llava:7b": round(compute_score(s1), 4),
        "qwen2.5:7b": round(compute_score(s2), 4),
        "qwen2.5vl:latest": round(compute_score(s3), 4),
    }

    best_model = max(scores, key=scores.get)

    lines.append("### 4.1 核心指标对比\n")
    lines.append(f"| 指标 | llava:7b | qwen2.5:7b | qwen2.5vl:latest |")
    lines.append(f"|------|---------|-----------|-----------------|")
    lines.append(f"| 字段匹配率 | {s1['avg_accuracy']:.1%} | {s2['avg_accuracy']:.1%} | {s3['avg_accuracy']:.1%} |")
    lines.append(f"| 材质匹配率 | {s1['material_accuracy']:.1%} | {s2['material_accuracy']:.1%} | {s3['material_accuracy']:.1%} |")
    lines.append(f"| 填写率 | {s1['avg_fill_rate']:.1%} | {s2['avg_fill_rate']:.1%} | {s3['avg_fill_rate']:.1%} |")
    lines.append(f"| 未知率 | {s1['avg_unknown_rate']:.1%} | {s2['avg_unknown_rate']:.1%} | {s3['avg_unknown_rate']:.1%} |")
    lines.append(f"| 平均耗时 | {s1['avg_time']:.1f}s | {s2['avg_time']:.1f}s | {s3['avg_time']:.1f}s |")
    lines.append(f"| 综合评分 | {scores['llava:7b']:.4f} | {scores['qwen2.5:7b']:.4f} | {scores['qwen2.5vl:latest']:.4f} |")
    lines.append("")

    lines.append(f"### 4.2 综合推荐\n")
    lines.append(f"**最优模型**: {best_model}（综合评分 {scores[best_model]:.4f}）\n")
    lines.append(f"- 识别准确率: {'llava:7b' if s1['avg_accuracy'] >= s2['avg_accuracy'] and s1['avg_accuracy'] >= s3['avg_accuracy'] else 'qwen2.5:7b' if s2['avg_accuracy'] >= s3['avg_accuracy'] else 'qwen2.5vl:latest'} 更优\n")
    lines.append(f"- 字段填写完整性: {'llava:7b' if s1['avg_fill_rate'] >= s2['avg_fill_rate'] and s1['avg_fill_rate'] >= s3['avg_fill_rate'] else 'qwen2.5:7b' if s2['avg_fill_rate'] >= s3['avg_fill_rate'] else 'qwen2.5vl:latest'} 更优\n")
    lines.append(f"- 响应速度: {'llava:7b' if s1['avg_time'] <= s2['avg_time'] and s1['avg_time'] <= s3['avg_time'] else 'qwen2.5:7b' if s2['avg_time'] <= s3['avg_time'] else 'qwen2.5vl:latest'} 更优\n")
    lines.append(f"- **综合推荐**: {best_model}\n")
    lines.append("---\n")
    lines.append(f"*报告由 benchmark.py 自动生成*\n")

    report = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存: {report_path}")
    return report_path


if __name__ == "__main__":
    print("=" * 80)
    print(" 🔬 三模型 Benchmark 评测")
    print("   llava:7b vs qwen2.5:7b vs qwen2.5vl:latest")
    print("=" * 80)

    summaries = compare_models()
    report_path = save_report(summaries)
    print(f"\n评测完成！报告见: {report_path}")
