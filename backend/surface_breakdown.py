"""
空间分层工程量计算引擎

从已有的 CAD 空间数据（area, length, width, height）计算每个空间的
墙面、地面、顶面独立工程量，存入 detail_json 字段。

设计原则：
- 只读已有数据，不修改任何汇总/报价逻辑
- 墙面面积 = 近似周长 × 层高（扣除门窗洞口估算值）
- 地面面积 = 空间多边形面积（直接使用已有 area）
- 顶面面积 = 地面面积（标准层）
- 计算系数从 system_settings 读取，支持后期调参
"""

import json
import math
from typing import Optional


def compute_surface_breakdown(
    area: float,
    length: float,
    width: float,
    height: float = 2.8,
    settings: Optional[dict] = None,
    space_name: str = "",
) -> dict:
    """
    计算单个空间的分层工程量。

    参数：
        area:     地面面积（㎡，来自 CAD 多边形）
        length:   边界框长度（m）
        width:    边界框宽度（m）
        height:   层高（m，默认 2.8）
        settings: 系统配置字典（带扣减系数等）
        space_name: 空间名称（用于特殊空间判断，如阳台/卫生间）

    返回：
        {
            "surfaces": {
                "floor":   {"area": ..., "unit": "㎡", "description": ...},
                "wall":    {"area": ..., "net_area": ..., "unit": "㎡", ...},
                "ceiling": {"area": ..., "unit": "㎡", ...}
            },
            "perimeter_m": ...,
            "height_m": ...,
            "deduct_ratio": ...,
            "note": "..."
        }
    """
    if not settings:
        settings = {}

    # ---- 地面 ----
    floor_area = max(area, 0.0)

    # ---- 顶面（标准层取地面面积）----
    ceiling_area = floor_area

    # ---- 墙面 ----
    # 近似周长：用边界框的 2*(长+宽)；不规则空间会低估，
    # 使用 >1 的周长系数补偿（默认 1.0 = 矩形近似）
    perimeter_factor = float(settings.get("perimeter_factor", "1.15"))
    perimeter_approx = 2.0 * (length + width) * perimeter_factor

    # 粗算墙面毛面积 = 周长 × 层高
    wall_gross = perimeter_approx * height

    # 洞口扣减（门窗）
    # 按空间类型调整扣减比例
    deduct_ratio = float(settings.get("deduct_door_window", "0.15"))
    name_lower = space_name.lower()

    # 卫生间/厨房窗户较小，扣减比例降低
    if any(kw in name_lower for kw in ["卫生间", "厕所", "厨房", "浴室"]):
        deduct_ratio = float(settings.get("deduct_wc_kitchen", "0.12"))
    # 阳台三面墙体，扣减较多（门窗占比大）
    elif "阳台" in name_lower:
        deduct_ratio = float(settings.get("deduct_balcony", "0.20"))

    wall_net = wall_gross * (1.0 - deduct_ratio)

    # ---- 构造返回值 ----
    breakdown = {
        "surfaces": {
            "floor": {
                "area": round(floor_area, 2),
                "unit": "㎡",
                "description": "地面面积",
                "source": "CAD多边形面积",
            },
            "wall": {
                "area": round(wall_gross, 2),
                "net_area": round(wall_net, 2),
                "unit": "㎡",
                "description": "墙面面积",
                "source": "近似周长×层高（已扣减门窗洞口）",
                "deduct_ratio": deduct_ratio,
                "deduct_description": f"扣减 {(deduct_ratio * 100):.0f}% 门窗洞口",
            },
            "ceiling": {
                "area": round(ceiling_area, 2),
                "unit": "㎡",
                "description": "顶面面积",
                "source": "同地面面积（标准层）",
            },
        },
        "perimeter_m": round(perimeter_approx, 2),
        "height_m": height,
        "deduct_ratio": deduct_ratio,
        "note": "墙面面积为近似值，精确值需基于CAD墙体中线计算",
    }

    return breakdown


def batch_compute(all_spaces: list, settings: Optional[dict] = None) -> list:
    """
    批量计算所有空间的分层工程量。

    all_spaces: 每个元素为 dict，必须包含:
        - space_name, area, length, width, height
    可选: id (用于关联回写)

    返回：增量更新的空间列表，每个元素增加 surface_breakdown 字段
    """
    results = []
    for space in all_spaces:
        name = space.get("space_name", space.get("name", ""))
        area = space.get("area", 0) or 0
        raw_l = space.get("length", space.get("dimensions", {}).get("width_m", 0)) or 0
        raw_w = space.get("width", space.get("dimensions", {}).get("height_m", 0)) or 0
        length = max(raw_l, raw_w)
        width = min(raw_l, raw_w)
        height = space.get("height", 2.8) or 2.8

        breakdown = compute_surface_breakdown(
            area=area,
            length=length,
            width=width,
            height=height,
            settings=settings,
            space_name=name,
        )

        entry = dict(space)
        entry["surface_breakdown"] = breakdown
        results.append(entry)

    return results
