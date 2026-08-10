"""
识别结果实体类：统一封装 CAD 识别结果与效果图识别结果，
供后端各接口（读取、导出、融合报价等）复用。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import uuid

# ─────────────────── 全局 CAD 注册表（只保存最新一次识别结果）──────────────────
_latest_cad_spaces: Optional[List['CadSpace']] = None


def get_latest_cad_spaces() -> Optional[List['CadSpace']]:
    """获取最新的 CadSpace 列表"""
    return _latest_cad_spaces

def set_latest_cad_spaces(spaces: List['CadSpace']) -> None:
    """设置最新的 CadSpace 列表（覆盖旧数据）"""
    global _latest_cad_spaces
    _latest_cad_spaces = spaces


def clear_latest_cad_spaces() -> None:
    """清空最新数据"""
    global _latest_cad_spaces
    _latest_cad_spaces = None

# ─────────────────── ImageResult 注册表（按 drawing_id 分组）──────────────────
_latest_image_registry: Dict[str, List['ImageResult']] = {}


def get_latest_image_results(drawing_id: str = "default") -> List['ImageResult']:
    """获取指定批次（drawing_id）的 ImageResult 列表"""
    return _latest_image_registry.get(drawing_id, [])


def set_latest_image_result(drawing_id: str, results: List['ImageResult']) -> None:
    """设置指定批次的 ImageResult 列表"""
    _latest_image_registry[drawing_id] = results


def append_image_result(drawing_id: str, result: 'ImageResult') -> None:
    """向指定批次追加一个 ImageResult"""
    if drawing_id not in _latest_image_registry:
        _latest_image_registry[drawing_id] = []
    _latest_image_registry[drawing_id].append(result)

@dataclass
class CadSpace:
    """
    CAD 识别结果 — 简化版，只保留核心字段
    类似 Spring Boot 的 @Entity / @Bean
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    space_name: str = ""      # 空间名称（客厅、主卧等）
    area_sqm: float = 0.0     # 面积（平方米）
    perimeter_m: float = 0.0  # 周长（米）
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "space_name": self.space_name,
            "area_sqm": self.area_sqm,
            "perimeter_m": self.perimeter_m,
        }


def dict_to_cadspace(data: dict) -> CadSpace:
    """
    将 parser 返回的 dict 转换为 CadSpace 实例
    类似 Spring Boot 的 @Bean 构造函数
    """
    return CadSpace(
        id=data.get("id", uuid.uuid4().hex[:8]),
        space_name=data.get("name", data.get("space_name", "")),
        area_sqm=float(data.get("area_sqm", data.get("area", 0))),
        perimeter_m=float(data.get("perimeter_m", 0)),
    )


@dataclass
class ImageResult:
    """效果图识别结果"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    filename: str = ""
    space_name: str = ""
    wall_material: str = ""
    floor_material: str = ""
    ceiling_material: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "space_name": self.space_name,
            "wall_material": self.wall_material,
            "floor_material": self.floor_material,
            "ceiling_material": self.ceiling_material,
            "confidence": self.confidence,
        }