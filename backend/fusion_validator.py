"""
融合校验模块

核心功能：
1. ezdxf 矢量数据 + VL 识别数据融合
2. 空间/房间名称/面积/尺寸的交叉验证
3. 矛盾数据标记（需人工复核）
4. 置信度计算

策略：
- 标准 DWG 矢量数据优先（置信度 0.9+）
- VL 数据仅用于补缺（非标图例、扫描件等）
- 两者冲突时以矢量数据为准，VL 数据标注为"待复核"
"""

import json
import re
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

# == 类型标准化映射 ==
ROOM_TYPE_ALIASES = {
    "客厅": ["客厅", "客餐厅", "起居室", "living room", "living"],
    "餐厅": ["餐厅", "dining room", "dining"],
    "主卧": ["主卧", "主卧室", "主人房", "master bedroom", "master"],
    "次卧": ["次卧", "次卧室", "客房", "bedroom", "guest bedroom"],
    "儿童房": ["儿童房", "kid's room", "children's room"],
    "书房": ["书房", "study room", "study"],
    "厨房": ["厨房", "kitchen"],
    "卫生间": ["卫生间", "厕所", "浴室", "主卫", "次卫", "公卫", "bathroom", "wc"],
    "阳台": ["阳台", "balcony"],
    "玄关": ["玄关", "entrance", "foyer"],
    "走廊": ["走廊", "过道", "hallway", "corridor"],
    "储藏室": ["储藏室", "storage", "closet"],
    "衣帽间": ["衣帽间", "walk-in closet"],
    "老人房": ["老人房", "elderly room"],
    "阳台": ["阳台", "balcony"],
    "楼梯": ["楼梯", "stairs", "staircase"],
    "楼梯间": ["楼梯间", "stairwell"],
    "电梯间": ["电梯间", "elevator shaft"],
    "车库": ["车库", "garage"],
    "露台": ["露台", "terrace"],
    "庭院": ["庭院", "yard", "courtyard"],
    "花园": ["花园", "garden"],
    "设备间": ["设备间", "equipment room"],
    "配电室": ["配电室", "power room", "electrical room"],
    "锅炉房": ["锅炉房", "boiler room"],
}


def normalize_room_name(name: str) -> Optional[str]:
    """标准化房间名称"""
    if not name or name in ("未命名空间", "unknown", ""):
        return None
    
    name_lower = name.lower().strip()
    for std_name, aliases in ROOM_TYPE_ALIASES.items():
        for alias in aliases:
            if alias in name_lower or alias in name:
                return std_name
    return name


def is_same_room(name_a: str, name_b: str) -> bool:
    """判断两个房间名称是否指代同一房间"""
    std_a = normalize_room_name(name_a)
    std_b = normalize_room_name(name_b)
    return std_a is not None and std_a == std_b


def extract_dimensions_from_text(text: str) -> List[int]:
    """从文本中提取尺寸数字（毫米）"""
    # 匹配常见尺寸格式：3600, 3.6m, 12" x 8", 1200*300, 1200-300
    patterns = [
        r'\b(\d{3,5})\b',  # 基本数字
        r'(\d+)x(\d+)',    # 宽x高
        r'(\d+)\*?(\d+)',  # 宽*高
        r'(\d+)\s*[x*~]\s*(\d+)',  # 宽 x 高
    ]
    
    dimensions = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                for m in match:
                    val = int(m)
                    if 100 <= val <= 60000:  # 合理尺寸范围 10cm - 60m
                        dimensions.append(val)
            else:
                val = int(match)
                if 100 <= val <= 60000:
                    dimensions.append(val)
    
    return list(set(dimensions))  # 去重


def calculate_area_confidence(
    dxf_area: float,
    vl_area: float,
    dxf_confidence: float,
    vl_confidence: float,
) -> dict:
    """
    计算面积置信度
    
    规则：
    - 两者一致（±10%）→ 高置信 0.95+
    - 轻微差异（10-30%）→ 中等置信 0.7-0.85，标记待复核
    - 差异过大（>30%）→ 低置信 0.3-0.6，必须人工确认
    """
    if dxf_area == 0 or vl_area == 0:
        return {
            "area_confidence": min(dxf_confidence, vl_confidence) * 0.5,
            "status": "partial_data",
            "note": "数据不完整，需补充",
        }
    
    diff_ratio = abs(dxf_area - vl_area) / max(dxf_area, vl_area, 0.01)
    
    if diff_ratio <= 0.1:  # 10% 以内
        confidence = max(dxf_confidence, vl_confidence) * (1 - diff_ratio)
        status = "一致"
        note = "数据吻合，可直接使用"
    elif diff_ratio <= 0.3:  # 10-30%
        confidence = 0.75 - diff_ratio * 1.5
        status = "差异-待复核"
        note = f"差异 {diff_ratio*100:.1f}%，建议核实"
    else:
        confidence = max(0.3, 0.6 - diff_ratio * 0.5)
        status = "冲突-需人工确认"
        note = f"差异 {diff_ratio*100:.1f}%，需人工确认"
    
    return {
        "area_confidence": round(confidence, 2),
        "diff_ratio": round(diff_ratio, 4),
        "diff_percentage": round(diff_ratio * 100, 1),
        "status": status,
        "note": note,
    }


@dataclass
class MergedSpace:
    """融合后的空间数据"""
    name: str                    # 标准化后的房间名
    dxf_area: float = 0.0        # 矢量解析面积
    vl_area: float = 0.0         # VL识别面积
    dxf_dimensions: dict = field(default_factory=dict)  # 矢量尺寸
    vl_dimensions: dict = field(default_factory=dict)   # VL尺寸
    area_confidence: float = 0.0
    area_status: str = ""        # "一致"/"差异-待复核"/"冲突-需人工确认"/"partial_data"
    area_note: str = ""          # 说明
    source_areas: List[str] = field(default_factory=lambda: [])  # 来源
    needs_review: bool = False   # 是否需要人工复核
    materials: dict = field(default_factory=dict)  # 材质（来自 VL）
    furnishings: List[str] = field(default_factory=list)  # 家具（来自 VL）
    openings: List[dict] = field(default_factory=list)  # 洞口
    
    def to_dict(self):
        return {
            "name": self.name,
            "dxf_area_sqm": self.dxf_area,
            "vl_area_sqm": self.vl_area,
            "final_area_sqm": self.dxf_area if self.dxf_area > 0 else self.vl_area,
            "area_confidence": self.area_confidence,
            "area_status": self.area_status,
            "area_note": self.area_note,
            "needs_review": self.needs_review,
            "source_areas": self.source_areas,
            "materials": self.materials,
            "furnishings": self.furnishings,
            "openings": self.openings,
        }


@dataclass
class FusionResult:
    """融合校验结果"""
    spaces: List[MergedSpace] = field(default_factory=list)
    total_spaces: int = 0
    matched_spaces: int = 0
    unmatched_dxf: List[MergedSpace] = field(default_factory=list)
    unmatched_vl: List[MergedSpace] = field(default_factory=list)
    total_confidence: float = 0.0
    reviewed_count: int = 0      # 已复核数量
    pending_review: int = 0      # 待复核数量
    cost_report: dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "total_spaces": self.total_spaces,
            "matched_spaces": self.matched_spaces,
            "total_confidence": round(self.total_confidence, 2),
            "reviewed_count": self.reviewed_count,
            "pending_review": self.pending_review,
            "spaces": [s.to_dict() for s in self.spaces],
            "unmatched_dxf": [s.name for s in self.unmatched_dxf],
            "unmatched_vl": [s.name for s in self.unmatched_vl],
            "warnings": self.warnings,
            "cost_report": self.cost_report,
        }


def merge_dxf_and_vl(
    dxf_result: dict,
    vl_result: dict,
    cost_report: Optional[dict] = None,
) -> FusionResult:
    """
    融合 DXF 矢量数据与 VL 识别数据
    
    Args:
        dxf_result: DXF 解析结果 { "spaces": [...], "total_area_sqm": ..., ... }
        vl_result: VL 识别结果 { "spaces": [...], "overall_style": ..., ... }
        cost_report: VL 成本报告
    
    Returns:
        FusionResult
    """
    result = FusionResult()
    result.cost_report = cost_report or {}
    
    dxf_spaces = dxf_result.get("spaces", [])
    vl_spaces = vl_result.get("spaces", []) if vl_result.get("success") else []
    
    # 提取 VL 识别的材质和风格信息
    vl_style = vl_result.get("overall_style", "未知") if vl_result.get("success") else "未知"
    vl_raw = vl_result if vl_result and not vl_result.get("success") else None
    
    # === 1. 空间名称匹配 ===
    dxf_map = {}  # name -> space data
    vl_map = {}   # name -> space data
    
    for space in dxf_spaces:
        name = space.get("name", "") or space.get("type", "")
        std_name = normalize_room_name(name) or name
        dxf_map[std_name] = {
            "data": space,
            "original_name": name,
            "normalized": std_name,
        }
    
    for space in vl_spaces:
        name = space.get("name", "") or space.get("type", "")
        std_name = normalize_room_name(name) or name
        vl_map[std_name] = {
            "data": space,
            "original_name": name,
            "normalized": std_name,
        }
    
    # === 2. 匹配并融合 ===
    all_names = set(list(dxf_map.keys()) + list(vl_map.keys()))
    matched_names = set()
    
    for name in all_names:
        in_dxf = name in dxf_map
        in_vl = name in vl_map
        
        # 构造融合空间
        merged = MergedSpace(name=name)
        
        if in_dxf and in_vl:
            # DXF 有 + VL 有 → 融合
            merged.source_areas = ["dxf", "vl"]
            merged.dxf_area = dxf_map[name]["data"].get("area_sqm", 0) or 0
            vl_data = vl_map[name]["data"]
            merged.vl_area = vl_data.get("area_sqm", 0) or vl_data.get("area_estimate", {}).get("max_sqm", 0) or 0
            
            # 尺寸融合
            merged.dxf_dimensions = dxf_map[name]["data"].get("dimensions", {})
            merged.vl_dimensions = vl_data.get("dimensions", {})
            
            # 置信度计算
            area_info = calculate_area_confidence(
                merged.dxf_area, merged.vl_area,
                dxf_map[name]["data"].get("confidence", 0.9),
                vl_data.get("confidence", 0.8),
            )
            merged.area_confidence = area_info["area_confidence"]
            merged.area_status = area_info["status"]
            merged.area_note = area_info["note"]
            
            # 材质/家具/设施（来自 VL）
            merged.materials = vl_data.get("materials", {})
            merged.furnishings = vl_data.get("furnishings", vl_data.get("furniture", []))
            
            if area_info["status"] != "一致":
                merged.needs_review = True
                result.warnings.append(f"房间 '{name}' 面积数据冲突：DXF={merged.dxf_area}㎡ vs VL={merged.vl_area}㎡")
            
            result.matched_spaces += 1
            
        elif in_dxf:
            # 仅 DXF 有 → 矢量数据
            merged.source_areas = ["dxf"]
            merged.dxf_area = dxf_map[name]["data"].get("area_sqm", 0) or 0
            merged.vl_area = 0
            merged.area_confidence = dxf_map[name]["data"].get("confidence", 0.9)
            merged.area_status = "仅DXF有"
            merged.area_note = "仅通过矢量解析获得数据"
            merged.dxf_dimensions = dxf_map[name]["data"].get("dimensions", {})
            
            # 如果面积太小或太大，标记可疑
            if merged.dxf_area < 1 or merged.dxf_area > 500:
                merged.needs_review = True
                result.warnings.append(f"房间 '{name}' 面积异常：{merged.dxf_area}㎡")
            
            # 仅 DXF 的房间需要 VL 补充（但当前未识别到，标记为"可能缺失"）
            result.unmatched_vl.append(merged)
            
        elif in_vl:
            # 仅 VL 有 → 补充数据
            merged.source_areas = ["vl"]
            vl_data = vl_map[name]["data"]
            merged.vl_area = vl_data.get("area_sqm", 0) or vl_data.get("area_estimate", {}).get("max_sqm", 0) or 0
            merged.dxf_area = 0
            merged.area_confidence = vl_data.get("confidence", 0.7) * 0.6  # 仅 VL 降低置信度
            merged.area_status = "仅VL有"
            merged.area_note = "仅在 VL 识别中获得，置信度降低"
            merged.vl_dimensions = vl_data.get("dimensions", {})
            merged.materials = vl_data.get("materials", {})
            merged.furnishings = vl_data.get("furnishings", vl_data.get("furniture", []))
            merged.needs_review = True
            
            result.unmatched_dxf.append(merged)
            result.warnings.append(f"效果图中发现 CAD 未标注的空间：'{name}'")
        
        else:
            # 不应该到达这里
            continue
        
        result.spaces.append(merged)
    
    result.total_spaces = len(result.spaces)
    result.pending_review = sum(1 for s in result.spaces if s.needs_review)
    result.reviewed_count = result.total_spaces - result.pending_review
    
    # === 3. 总体置信度 ===
    if result.spaces:
        confidences = [s.area_confidence for s in result.spaces if s.area_confidence > 0]
        result.total_confidence = sum(confidences) / len(confidences) if confidences else 0.5
    else:
        result.total_confidence = 0.0
    
    # === 4. 补充总体信息 ===
    if dxf_result.get("total_area_sqm"):
        result.dxf_total_area = dxf_result.get("total_area_sqm", 0)
    if dxf_result.get("layout"):
        result.dxf_layout = dxf_result["layout"]
    
    result.overall_style = vl_style
    
    return result


def generate_review_list(fusion_result: FusionResult) -> dict:
    """
    生成人工复核清单
    
    Returns:
        {
            "review_items": [...],  # 待复核项目
            "confirmed_items": [...]  ✅ 已确认项目
            "stats": {"total": N, "pending": N, "confirmed": N}
        }
    """
    review_items = []
    confirmed_items = []
    
    for space in fusion_result.spaces:
        item = {
            "name": space.name,
            "source": space.source_areas,
        }
        
        if space.needs_review:
            review_items.append({
                "name": space.name,
                **item,
                "dxf_area_sqm": space.dxf_area,
                "vl_area_sqm": space.vl_area,
                "area_status": space.area_status,
                "need_action": True,
                "suggestion": space.area_note,
            })
        else:
            confirmed_items.append({
                "name": space.name,
                **item,
                "area_sqm": space.final_area_sqm,
                "confidence": space.area_confidence,
            })
    
    return {
        "review_items": review_items,
        "confirmed_items": confirmed_items,
        "stats": {
            "total": fusion_result.total_spaces,
            "pending": len(review_items),
            "confirmed": len(confirmed_items),
        },
    }
