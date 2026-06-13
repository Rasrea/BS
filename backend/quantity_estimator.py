"""
工程量/报价计算模块

基于融合校验后的数据，计算各工序的工程量并对接计价库生成报价。

核心功能：
1. 墙面工程：抹灰、腻子、乳胶漆（按净面积）
2. 地面工程：地砖/地板铺设（按面积）
3. 吊顶工程：石膏板吊顶（按面积）
4. 门窗工程：木门/塑钢门/铝合金窗（按洞口面积）
5. 水电工程：开关插座/灯具预留（按点位）
6. 对接计价库：支持自定义单价/品牌/规格
"""

import json
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

# == 工种枚举 ==
class WorkCategory(str, Enum):
    WALL = "wall"              # 墙面工程
    FLOOR = "floor"            # 地面工程
    CEILING = "ceiling"        # 吊顶工程
    DOOR = "door"              # 门窗工程
    WINDOW = "window"          # 窗户工程
    PLUMBING = "plumbing"      # 给排水工程
    ELECTRIC = "electric"      # 电气工程
    CLEANUP = "cleanup"        # 垃圾清运


class SurfaceMaterial(str, Enum):
    PAINT = "paint"            # 乳胶漆
    WALLPAPER = "wallpaper"    # 墙纸/墙布
    TILE = "tile"              # 瓷砖
    WOOD_PANEL = "wood_panel"  # 木饰面
    STONE = "stone"            # 石材


class FloorMaterial(str, Enum):
    LARGE_FORMAT_TILE = "large_tile"        # 大块瓷砖
    WOOD_FLOOR = "wood_floor"      # 木地板
    LAMINATE = "laminate"          # 复合地板
    MARBLE = "marble"              # 大理石
    ENGINEERED_WOOD = "wood"       # 实木复合地板


# == 默认计价库（可替换为外部 API/数据库） ==
DEFAULT_QUOTE_DB = {
    # 墙面工程（元/平方米）
    "wall": {
        "wall_surface_treatment": {
            "name": "墙面基层处理",
            "unit": "㎡",
            "price_per_unit": 15.0,
            "sub_items": [
                {"name": "腻子批嵌", "unit": "㎡", "price_per_unit": 12.0},
                {"name": "乳胶漆（底漆+面漆）", "unit": "㎡", "price_per_unit": 25.0},
                {"name": "基层打磨", "unit": "㎡", "price_per_unit": 8.0},
            ],
        },
        "wallpaper_install": {
            "name": "墙纸/墙布铺设",
            "unit": "㎡",
            "price_per_unit": 45.0,
        },
        "tile_install": {
            "name": "瓷砖铺贴",
            "unit": "㎡",
            "price_per_unit": 65.0,
        },
    },
    # 地面工程（元/平方米）
    "floor": {
        "large_tile": {
            "name": "大块瓷砖铺贴",
            "unit": "㎡",
            "price_per_unit": 65.0,
        },
        "wood_floor": {
            "name": "木地板铺设",
            "unit": "㎡",
            "price_per_unit": 120.0,
        },
        "laminate": {
            "name": "复合地板铺设",
            "unit": "㎡",
            "price_per_unit": 80.0,
        },
        "marble": {
            "name": "大理石铺贴",
            "unit": "㎡",
            "price_per_unit": 350.0,
        },
    },
    # 吊顶工程（元/平方米）
    "ceiling": {
        "gypsum_board": {
            "name": "石膏板吊顶",
            "unit": "㎡",
            "price_per_unit": 120.0,
        },
        "mineral_plate": {
            "name": "矿棉板吊顶",
            "unit": "㎡",
            "price_per_unit": 90.0,
        },
    },
    # 门窗工程（元/樘 或 元/平方米）
    "door": {
        "wood_door": {
            "name": "木门",
            "unit": "樘",
            "price_per_unit": 1200.0,
        },
        "aluminum_door": {
            "name": "塑钢门",
            "unit": "樘",
            "price_per_unit": 800.0,
        },
        "sliding_door": {
            "name": "推拉门",
            "unit": "㎡",
            "price_per_unit": 600.0,
        },
        "glass_door": {
            "name": "玻璃门",
            "unit": "㎡",
            "price_per_unit": 800.0,
        },
    },
    # 窗户工程（元/平方米）
    "window": {
        "aluminum_window": {
            "name": "铝合金窗",
            "unit": "㎡",
            "price_per_unit": 450.0,
        },
        "sliding_window": {
            "name": "推拉窗",
            "unit": "㎡",
            "price_per_unit": 380.0,
        },
        "fixed_glass": {
            "name": "固定玻璃",
            "unit": "㎡",
            "price_per_unit": 350.0,
        },
        "broken_bridge_aluminum": {
            "name": "断桥铝窗",
            "unit": "㎡",
            "price_per_unit": 650.0,
        },
    },
    # 水电工程
    "plumbing": {
        "water_supply": {
            "name": "给排水改造",
            "unit": "点位",
            "price_per_unit": 200.0,
        },
        "sewage": {
            "name": "污水管改造",
            "unit": "点位",
            "price_per_unit": 150.0,
        },
    },
    "electric": {
        "switch_socket": {
            "name": "开关插座安装",
            "unit": "点位",
            "price_per_unit": 60.0,
        },
        "light_fixture": {
            "name": "灯具安装预留",
            "unit": "点位",
            "price_per_unit": 50.0,
        },
        "circuit_upgrade": {
            "name": "电路改造",
            "unit": "米",
            "price_per_unit": 35.0,
        },
    },
    # 垃圾清运
    "cleanup": {
        "waste_removal": {
            "name": "垃圾清运",
            "unit": "车",
            "price_per_unit": 300.0,
        },
    },
}


@dataclass
class WorkItem:
    """工序项"""
    category: str
    name: str
    quantity: float    # 工程量
    unit: str
    price_per_unit: float
    total: float       # 小计
    room_name: str = ""
    notes: str = ""
    
    def to_dict(self):
        return {
            "category": self.category,
            "name": self.name,
            "quantity": round(self.quantity, 2),
            "unit": self.unit,
            "price_per_unit": self.price_per_unit,
            "total": round(self.total, 2),
            "room_name": self.room_name,
            "notes": self.notes,
        }


@dataclass
class QuoteRoom:
    """房间报价"""
    room_name: str
    work_items: List[WorkItem] = field(default_factory=list)
    
    def to_dict(self):
        items = [item.to_dict() for item in self.work_items]
        total = sum(item.total for item in self.work_items)
        return {
            "room_name": self.room_name,
            "work_items": items,
            "room_total": round(total, 2),
        }


@dataclass
class QuoteResult:
    """报价结果"""
    project_name: str
    rooms: List[QuoteRoom] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    generated_at: str = ""
    
    def calculate_summary(self):
        """计算汇总"""
        room_totals = {}
        category_totals = {}
        grand_total = 0
        
        for room in self.rooms:
            room_total = 0
            for item in room.work_items:
                room_total += item.total
                cat = item.category
                category_totals[cat] = category_totals.get(cat, 0) + item.total
            room_totals[room.room_name] = room_total
            grand_total += room_total
        
        # 分类统计
        category_names = {
            "wall": "墙面工程",
            "floor": "地面工程",
            "ceiling": "吊顶工程",
            "door": "门窗工程",
            "window": "窗户工程",
            "plumbing": "给排水工程",
            "electric": "电气工程",
            "cleanup": "垃圾清运",
        }
        
        category_summary = {}
        for cat, total in category_totals.items():
            category_summary[category_names.get(cat, cat)] = {
                "quantity": 0,
                "unit": "",
                "total": round(total, 2),
                "percentage": round(total / grand_total * 100, 1) if grand_total > 0 else 0,
            }
        
        self.summary = {
            "project_name": self.project_name,
            "total_area_sqm": 0,
            "room_count": len(self.rooms),
            "category_summary": category_summary,
            "grand_total": round(grand_total, 2),
            "room_totals": room_totals,
            "generated_at": self.generated_at or datetime.now().isoformat(),
        }
    
    def to_dict(self):
        self.calculate_summary()
        return {
            "project_name": self.project_name,
            "summary": self.summary,
            "rooms": [room.to_dict() for room in self.rooms],
        }


def estimate_quantities(
    fusion_result: dict,
    quote_db: Optional[dict] = None,
    project_name: str = "装修工程",
    custom_prices: Optional[Dict] = None,
) -> QuoteResult:
    """
    基于融合数据估算工程量并生成报价
    
    Args:
        fusion_result: 融合校验结果（fusion_validator.FusionResult.to_dict()）
        quote_db: 计价库（默认使用内置 DEFAULT_QUOTE_DB）
        project_name: 项目名称
        custom_prices: 自定义价格覆盖
    
    Returns:
        QuoteResult
    """
    quote_db = quote_db or DEFAULT_QUOTE_DB
    merged_spaces = fusion_result.get("spaces", [])
    
    # 获取房间面积信息
    space_areas = {}
    for s in merged_spaces:
        area_sqm = s.get("final_area_sqm", s.get("dxf_area", s.get("vl_area", 0)))
        space_areas[s.get("name", "unknown")] = area_sqm
    
    # === 1. 估算各工种工程量 ===
    rooms = []
    
    for space in merged_spaces:
        room_name = space.get("name", "unknown")
        area_sqm = space.get("final_area_sqm", space.get("dxf_area", space.get("vl_area", 0)))
        materials = space.get("materials", {})
        openings = space.get("openings", [])
        furnishings = space.get("furnishings", [])
        
        room = QuoteRoom(room_name=room_name)
        
        # === 墙面工程 ===
        wall_area_sqm = area_sqm * 2.5  # 墙面面积 ≈ 地面积 × 2.5（估算，含门窗扣减前）
        
        # 根据材质选择单价
        floor_mat = materials.get("floor", "large_tile")
        wall_mat = materials.get("wall", "paint")
        
        # 抹灰/腻子/乳胶漆
        if quote_db.get("wall", {}).get("wall_surface_treatment"):
            base_price = quote_db["wall"]["wall_surface_treatment"]["price_per_unit"]
            room.work_items.append(WorkItem(
                category="wall",
                name="墙面基层处理（抹灰+腻子+乳胶漆）",
                quantity=wall_area_sqm,
                unit="㎡",
                price_per_unit=base_price,
                total=wall_area_sqm * base_price,
                room_name=room_name,
            ))
        
        # 墙面材质
        if wall_mat == "wallpaper":
            if quote_db["wall"].get("wallpaper_install"):
                room.work_items.append(WorkItem(
                    category="wall",
                    name="墙纸/墙布铺设",
                    quantity=wall_area_sqm,
                    unit="㎡",
                    price_per_unit=quote_db["wall"]["wallpaper_install"]["price_per_unit"],
                    total=wall_area_sqm * quote_db["wall"]["wallpaper_install"]["price_per_unit"],
                    room_name=room_name,
                ))
        
        # === 地面工程 ===
        if quote_db.get("floor", {}).get("large_tile"):
            # 考虑 3% 损耗
            floor_qty = area_sqm * 1.03
            price = quote_db["floor"]["large_tile"]["price_per_unit"]
            room.work_items.append(WorkItem(
                category="floor",
                name="地面铺贴（含损耗）",
                quantity=floor_qty,
                unit="㎡",
                price_per_unit=price,
                total=floor_qty * price,
                room_name=room_name,
            ))
        
        # === 吊顶工程 ===
        ceiling_area = area_sqm * 0.8  # 假设吊顶面积 = 地面面积 × 0.8
        if quote_db.get("ceiling", {}).get("gypsum_board"):
            price = quote_db["ceiling"]["gypsum_board"]["price_per_unit"]
            room.work_items.append(WorkItem(
                category="ceiling",
                name="石膏板吊顶",
                quantity=ceiling_area,
                unit="㎡",
                price_per_unit=price,
                total=ceiling_area * price,
                room_name=room_name,
            ))
        
        # === 门窗工程 ===
        for opening in openings:
            op_type = opening.get("type", "door")
            op_subtype = opening.get("subtype", "")
            
            if op_type == "door":
                sub = op_subtype or "wood"
                key_map = {"wood": "wood_door", "aluminum": "aluminum_door", "sliding": "sliding_door", "glass": "glass_door"}
                key = key_map.get(sub, "wood_door")
                if quote_db["door"].get(key):
                    door_price = quote_db["door"][key]
                    if door_price["unit"] == "樘":
                        # 按樘计
                        room.work_items.append(WorkItem(
                            category="door",
                            name=f"{door_price['name']}（{room_name}）",
                            quantity=1,
                            unit="樘",
                            price_per_unit=door_price["price_per_unit"],
                            total=door_price["price_per_unit"],
                            room_name=room_name,
                        ))
                    else:
                        # 按㎡计
                        w_mm = opening.get("width_mm", 900)
                        h_mm = opening.get("height_mm", 2100)
                        area = (w_mm * h_mm) / 1_000_000
                        room.work_items.append(WorkItem(
                            category="door",
                            name=f"{door_price['name']}（{room_name}、{w_mm//1000}×{h_mm//1000}）",
                            quantity=area,
                            unit="㎡",
                            price_per_unit=door_price["price_per_unit"],
                            total=area * door_price["price_per_unit"],
                            room_name=room_name,
                        ))
            elif op_type == "window":
                sub = op_subtype or "aluminum"
                key_map = {"aluminum": "aluminum_window", "sliding": "sliding_window", "fixed": "fixed_glass", "broken": "broken_bridge_aluminum"}
                key = key_map.get(sub, "aluminum_window")
                if quote_db["window"].get(key):
                    win_price = quote_db["window"][key]
                    w_mm = opening.get("width_mm", 1500)
                    h_mm = opening.get("height_mm", 1500)
                    area = (w_mm * h_mm) / 1_000_000
                    room.work_items.append(WorkItem(
                        category="window",
                        name=f"{win_price['name']}（{room_name}、{w_mm//1000}×{h_mm//1000}）",
                        quantity=area,
                        unit="㎡",
                        price_per_unit=win_price["price_per_unit"],
                        total=area * win_price["price_per_unit"],
                        room_name=room_name,
                    ))
        
        # === 水电工程 ===
        # 开关插座：按房间面积估算点位
        switch_count = max(2, int(area_sqm / 10))  # 每10㎡ 1个点位
        room.work_items.append(WorkItem(
            category="electric",
            name="开关插座安装",
            quantity=switch_count,
            unit="点位",
            price_per_unit=60.0,
            total=switch_count * 60.0,
            room_name=room_name,
        ))
        
        # 灯具
        light_count = max(1, int(area_sqm / 15))  # 每15㎡ 1个灯
        room.work_items.append(WorkItem(
            category="electric",
            name="灯具安装预留",
            quantity=light_count,
            unit="点位",
            price_per_unit=50.0,
            total=light_count * 50.0,
            room_name=room_name,
        ))
        
        # 给排水（卫生间/厨房）
        if "卫" in room_name or "厕" in room_name or "浴" in room_name:
            room.work_items.append(WorkItem(
                category="plumbing",
                name="给排水改造",
                quantity=3,
                unit="点位",
                price_per_unit=200.0,
                total=600.0,
                room_name=room_name,
            ))
        elif "厨" in room_name:
            room.work_items.append(WorkItem(
                category="plumbing",
                name="给排水改造",
                quantity=2,
                unit="点位",
                price_per_unit=200.0,
                total=400.0,
                room_name=room_name,
            ))
        
        rooms.append(room)
    
    # === 2. 全屋统一工程 ===
    total_area = sum(space_areas.values())
    project = QuoteResult(project_name=project_name)
    project.rooms = rooms
    
    # 垃圾清运（按总面积估算车数，每30㎡ 1车）
    waste_trucks = max(1, int(total_area / 30) + 1)
    project.rooms.append(QuoteRoom(room_name="全屋"))
    project.rooms[-1].work_items.append(WorkItem(
        category="cleanup",
        name="垃圾清运",
        quantity=waste_trucks,
        unit="车",
        price_per_unit=300.0,
        total=waste_trucks * 300.0,
        room_name="全屋",
    ))
    
    # 总项目汇总
    project.calculate_summary()
    
    return project


def export_quote_to_json(quote_result: QuoteResult) -> str:
    """导出报价为 JSON 文件"""
    return json.dumps(quote_result.to_dict(), ensure_ascii=False, indent=2)
