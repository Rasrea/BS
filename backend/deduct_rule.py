"""
洞口扣减规则模块

内置扣减规则（基于 ezdxf 矢量数据）：
- 木门：扣 85%
- 铝合金窗：扣 70%
- 推拉门：扣 50%
- 平移窗：扣 65%
- 固定玻璃：扣 90%
- 壁龛：+ 5% 增量
- 立柱：+ 3% 增量

所有扣减基于墙体总面积 * 洞口占比计算。
"""

from typing import Optional
from enum import Enum


class DoorType(str, Enum):
    WOOD = "wood"          # 木门
    ALUMINUM = "aluminum"  # 铝合金窗
    SLIDING = "sliding"    # 推拉门
    FOLDING = "folding"    # 折叠门
    Bifold = "bifold"      # 折叠门
    SWING = "swing"        # 旋转门/平开门


class WindowType(str, Enum):
    PLAIN_WINDOW = "plain_window"       # 普通窗/铝合金窗
    SLIDING_WINDOW = "sliding_window"   # 平移窗
    FIXED_GLASS = "fixed_glass"        # 固定玻璃


class SpecialItem(str, Enum):
    NICH = "niche"           # 壁龛，增量 +5%
    COLUMN = "column"        # 立柱，增量 +3%
    BAY_WINDOW = "bay_window"  # 飘窗，增量 +8%


# == 扣减率配置 ==
DOOR_DEDUCTION_RATE = {
    DoorType.WOOD: 0.85,
    DoorType.ALUMINUM: 0.80,  # 铝合金门
    DoorType.SLIDING: 0.50,
    DoorType.FOLDING: 0.60,
    DoorType.Bifold: 0.30,
    DoorType.SWING: 0.75,  # 旋转门
}

WINDOW_DEDUCTION_RATE = {
    WindowType.PLAIN_WINDOW: 0.70,      # 铝合金窗
    WindowType.SLIDING_WINDOW: 0.65,    # 平移窗
    WindowType.FIXED_GLASS: 0.90,       # 固定玻璃
}


def get_deduction_rate(item_type: str, subtype: Optional[str] = None) -> float:
    """
    根据类型获取扣减率
    
    Args:
        item_type: "door", "window", "niche", "column", "bay_window"
        subtype: 具体类型
    Returns:
        扣减率 (0~1)，1 表示全扣，0 表示不扣
    """
    if item_type == "door":
        subtype = subtype or "wood"
        return DOOR_DEDUCTION_RATE.get(DoorType(subtype), 0.85)
    elif item_type == "window":
        subtype = subtype or "aluminum"
        return WINDOW_DEDUCTION_RATE.get(WindowType(subtype), 0.70)
    elif item_type == "niche":
        return 0.05     # 增量系数
    elif item_type == "column":
        return 0.03     # 增量系数
    elif item_type == "bay_window":
        return 0.08     # 飘窗增量
    else:
        return 0.85     # 默认扣减 85%


def apply_deductions(
    wall_areas: list,
    openings: list,
    unit_price: float
) -> dict:
    """
    应用洞口扣减规则
    
    Args:
        wall_areas: 墙体面积列表 [{"area_sqm": float, "room_name": str, "walls": [...]}]
        openings: 洞口列表 [{"room_name": str, "width_mm": float, "height_mm": float, "item_type": str, "subtype": str}]
        unit_price: 单价 (元/平方米)
    Returns:
        {
            "total_wall_area_sqm": total wall area,
            "total_opening_area_sqm": total opening area,
            "deducted_opening_area_sqm": total after deduction
            "net_wall_area_sqm": net wall area after deduction
            "cost": total cost,
            "details": { room_name: { ... } }
            "warnings": []
        }
    """
    total_wall_area = sum(w.get("area_sqm", 0) for w in wall_areas)
    room_details = {}
    total_deducted = 0
    
    for opening in openings:
        room = opening.get("room_name", "unknown")
        w_mm = opening.get("width_mm", 0)
        h_mm = opening.get("height_mm", 0)
        item_type = opening.get("item_type", "door")
        subtype = opening.get("subtype")
        
        # 计算洞口面积（平方米）
        area_sqm = (w_mm * h_mm) / 1_000_000
        
        # 获取扣减率
        rate = get_deduction_rate(item_type, subtype)
        
        # 扣减后的面积
        deducted = area_sqm * rate
        total_deducted += deducted
        
        if room not in room_details:
            room_details[room] = {
                "total_wall_area_sqm": 0,
                "total_opening_area_sqm": 0,
                "deducted_opening_area_sqm": 0,
                "walls": [],
                "openings": [],
            }
        
        room_details[room]["total_opening_area_sqm"] += area_sqm
        room_details[room]["deducted_opening_area_sqm"] += deducted
        room_details[room]["openings"].append({
            "type": item_type,
            "subtype": subtype,
            "width_mm": w_mm,
            "height_mm": h_mm,
            "area_sqm": round(area_sqm, 3),
            "rate": rate,
            "deducted_sqm": round(deducted, 3),
        })
    
    # 为未分配洞口的房间设置墙体面积
    for wall in wall_areas:
        room = wall.get("room_name", "unknown")
        if room not in room_details:
            room_details[room] = {
                "total_wall_area_sqm": 0,
                "total_opening_area_sqm": 0,
                "deducted_opening_area_sqm": 0,
                "walls": [],
                "openings": [],
            }
        room_details[room]["total_wall_area_sqm"] = wall.get("area_sqm", 0)
        room_details[room]["walls"].append({
            "area_sqm": wall.get("area_sqm", 0),
            "length_m": wall.get("length_m", 0),
        })
    
    # 计算净墙面面积
    total_net_area = total_wall_area - total_deducted
    if total_net_area < 0:
        total_net_area = 0
        warnings = ["警告：洞口面积超过墙体总面积，请检查数据"]
    else:
        warnings = []
    
    cost = total_net_area * unit_price
    
    return {
        "total_wall_area_sqm": round(total_wall_area, 2),
        "total_opening_area_sqm": round(sum(o.get("width_mm", 0) * o.get("height_mm", 0) / 1_000_000 for o in openings), 2),
        "deducted_opening_area_sqm": round(total_deducted, 2),
        "net_wall_area_sqm": round(total_net_area, 2),
        "cost": round(cost, 2),
        "unit_price": unit_price,
        "details": room_details,
        "warnings": warnings,
    }
