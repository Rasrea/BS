"""
交叉校验模块
将 CAD 解析结果与效果图识别结果进行对照校验
"""
from typing import Optional


def cross_validate(cad_result: dict, image_result: dict) -> dict:
    """
    交叉校验 CAD 和效果图的识别结果

    返回:
    {
        "warnings": [...],
        "confidence": float,
        "suggestions": [...],
        "matched_spaces": [...],
        "unmatched": {...}
    }
    """
    warnings = []
    suggestions = []
    matched = []
    cad_spaces = cad_result.get("spaces", [])
    img_spaces = image_result.get("spaces", [])

    # 类型映射
    type_alias = {
        "客厅": ["客厅", "客餐厅", "起居室", "living room", "living"],
        "主卧": ["主卧", "主人房", "master bedroom", "主卧室"],
        "次卧": ["次卧", "卧室", "客房", "bedroom"],
        "厨房": ["厨房", "kitchen"],
        "卫生间": ["卫生间", "厕所", "浴室", "主卫", "次卫", "公卫", "bathroom"],
        "餐厅": ["餐厅", "dining room", "dining"],
        "阳台": ["阳台", "balcony"],
        "书房": ["书房", "study room", "study"],
    }

    def normalize_type(name: str) -> Optional[str]:
        name_lower = name.lower()
        for std, aliases in type_alias.items():
            for alias in aliases:
                if alias in name or alias in name_lower:
                    return std
        return None

    # 对比空间数量和类型
    cad_types = set()
    for s in cad_spaces:
        nt = normalize_type(s.get("name", ""))
        if nt:
            cad_types.add(nt)

    img_types = set()
    for s in img_spaces:
        nt = normalize_type(s.get("type", ""))
        if nt:
            img_types.add(nt)

    # 匹配空间
    for cs in cad_spaces:
        cad_name = cs.get("name", "")
        cad_type = normalize_type(cad_name)

        best_match = None
        for ims in img_spaces:
            img_type = normalize_type(ims.get("type", ""))
            if cad_type and img_type and cad_type == img_type:
                best_match = ims
                break

        if best_match:
            matched.append({
                "cad_name": cad_name,
                "img_type": best_match.get("type", ""),
                "cad_area": cs.get("area_sqm"),
                "img_area_range": best_match.get("area_estimate"),
                "match_type": "精确匹配" if cad_type else "模糊匹配",
            })
        else:
            matched.append({
                "cad_name": cad_name,
                "img_type": None,
                "cad_area": cs.get("area_sqm"),
                "img_area_range": None,
                "match_type": "仅在CAD中出现",
            })

    # 仅在效果图中出现的空间
    only_in_img = []
    seen_img_types = {m.get("img_type") for m in matched if m.get("img_type")}
    for ims in img_spaces:
        it = normalize_type(ims.get("type", ""))
        if it and it not in seen_img_types:
            only_in_img.append(ims)
            seen_img_types.add(it)

    # 生成警告
    if len(cad_spaces) != len(img_spaces):
        warnings.append(
            f"C A D 识别到 {len(cad_spaces)} 个空间，"
            f"效果图识别到 {len(img_spaces)} 个空间，数量不一致"
        )

    if only_in_img:
        names = [s.get("type", "未知") for s in only_in_img]
        warnings.append(f"效果图中出现了 CAD 未标注的空间: {', '.join(names)}")

    # 面积校验
    for m in matched:
        cad_area = m.get("cad_area")
        img_range = m.get("img_area_range")
        if cad_area and img_range:
            min_a = img_range.get("min_sqm", 0)
            max_a = img_range.get("max_sqm", 999)
            if cad_area < min_a * 0.7 or cad_area > max_a * 1.3:
                warnings.append(
                    f"{m['cad_name']} 面积差异较大: "
                    f"CAD={cad_area}㎡, 效果图估算={min_a}-{max_a}㎡"
                )

    # 生成建议
    if warnings:
        suggestions.append("建议设计师重点核对以上差异点")
    if len(only_in_img) > 0:
        suggestions.append("效果图中出现额外空间，请确认 CAD 图纸完整性")
    if len(cad_spaces) == 0:
        suggestions.append("未能从 CAD 中提取空间信息，建议检查 CAD 文件格式")
    if len(img_spaces) == 0:
        suggestions.append("未能从效果图中识别空间，请检查图片质量或 API 配置")

    # 总体置信度
    confidence = 0.9
    if warnings:
        confidence -= 0.1 * len(warnings)
    confidence = max(0.3, min(1.0, confidence))

    return {
        "warnings": warnings,
        "confidence": round(confidence, 2),
        "suggestions": suggestions if suggestions else ["识别结果基本一致，可以直接使用"],
        "matched_spaces": matched,
        "only_in_image": only_in_img,
        "summary": {
            "cad_spaces_count": len(cad_spaces),
            "img_spaces_count": len(img_spaces),
            "matched_count": sum(1 for m in matched if m.get("img_type")),
        }
    }
