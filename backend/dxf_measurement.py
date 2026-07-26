"""DXF 人工标注测量支持。

该模块只负责为前端提供轻量矢量底图，并对用户提交的模型空间坐标进行
服务端几何校验和测量。它不依赖 cad_parser.py 的自动房间识别逻辑。
"""

from __future__ import annotations

import gzip
import json
import logging
import math
import threading
from pathlib import Path
from typing import Literal, Optional

import ezdxf
from ezdxf.disassemble import make_primitive, recursive_decompose
from ezdxf.colors import aci2rgb
from pydantic import BaseModel, Field
from shapely.geometry import Polygon
from shapely.validation import explain_validity


MAX_RENDER_ENTITIES = 50_000
MAX_RENDER_POINTS = 1_000_000
MAX_SCAN_ENTITIES = 100_000
MAX_SCAN_POINTS = 1_000_000
_DXF_READ_LOCK = threading.Lock()
_DUPLICATE_HANDLE_PREFIX = "Found non-unique entity handle"


UNIT_DEFINITIONS = {
    0: ("unitless", None),
    1: ("in", 25.4),
    2: ("ft", 304.8),
    3: ("mi", 1_609_344.0),
    4: ("mm", 1.0),
    5: ("cm", 10.0),
    6: ("m", 1000.0),
    7: ("km", 1_000_000.0),
    8: ("microin", 0.0000254),
    9: ("mil", 0.0254),
    10: ("yd", 914.4),
}

UNIT_OVERRIDE_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}


class RoomMeasurementInput(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    name: str = Field(default="未命名空间", max_length=100)
    shape_type: Literal["rectangle", "polygon"] = "polygon"
    vertices: list[list[float]] = Field(min_length=3, max_length=500)


class DxfScaleCalibrationInput(BaseModel):
    start: list[float] = Field(min_length=2, max_length=2)
    end: list[float] = Field(min_length=2, max_length=2)
    real_length_mm: float = Field(gt=0, le=1_000_000_000)


class DxfMeasurementRequest(BaseModel):
    drawing_id: str = Field(min_length=1, max_length=64)
    source_format: Literal["dxf", "pdf"] = "dxf"
    unit_override: Optional[Literal["mm", "cm", "m", "in", "ft"]] = None
    calibration: Optional[DxfScaleCalibrationInput] = None
    rooms: list[RoomMeasurementInput] = Field(min_length=1, max_length=500)


class _DuplicateHandleFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage().startswith(_DUPLICATE_HANDLE_PREFIX):
            self.count += 1
            return False
        return True


def _read_dxf_with_diagnostics(file_path: str | Path):
    """读取 DXF，并将重复 handle 日志收敛为可返回给调用方的计数。"""
    duplicate_filter = _DuplicateHandleFilter()
    ezdxf_logger = logging.getLogger("ezdxf")
    with _DXF_READ_LOCK:
        ezdxf_logger.addFilter(duplicate_filter)
        try:
            doc = ezdxf.readfile(file_path)
        finally:
            ezdxf_logger.removeFilter(duplicate_filter)
    return doc, duplicate_filter.count


def prepare_dxf_for_measurement(file_path: str) -> dict:
    """扫描 DXF、检测独立图纸区域，并返回默认区域的轻量矢量底图。"""
    path = Path(file_path)
    warnings = []
    try:
        doc, duplicate_handle_count = _read_dxf_with_diagnostics(path)
    except Exception as exc:
        return {"error": f"DXF 文件读取失败: {exc}"}

    if duplicate_handle_count:
        warnings.append(
            f"DXF 存在 {duplicate_handle_count} 个重复实体句柄，已继续读取；建议重新导出或修复原文件"
        )

    unit_code = int(doc.header.get("$INSUNITS", 0) or 0)
    unit_name, mm_per_unit = UNIT_DEFINITIONS.get(unit_code, (f"code_{unit_code}", None))
    if mm_per_unit is None:
        warnings.append("DXF 未声明有效单位，计算前必须选择图纸单位")

    entities = []
    texts = []
    point_count = 0
    scan_truncated = False
    min_x = min_y = math.inf
    max_x = max_y = -math.inf

    def include_point(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    try:
        flattening_distance = max(1.0 / mm_per_unit, 1e-6) if mm_per_unit else 1.0
        decomposed = recursive_decompose(doc.modelspace())
        for entity in decomposed:
            if len(entities) >= MAX_SCAN_ENTITIES or point_count >= MAX_SCAN_POINTS:
                scan_truncated = True
                break

            entity_type = entity.dxftype()
            layer = str(entity.dxf.get("layer", "0"))

            if entity_type in {"TEXT", "MTEXT"}:
                insert = entity.dxf.get("insert")
                if insert is None:
                    continue
                content = entity.plain_text() if entity_type == "MTEXT" else str(entity.dxf.get("text", ""))
                content = " ".join(content.split())[:100]
                if not content:
                    continue
                x, y = float(insert.x), float(insert.y)
                height_attribute = "char_height" if entity_type == "MTEXT" else "height"
                text_height = float(entity.dxf.get(height_attribute, 0) or 0)
                include_point(x, y)
                texts.append({
                    "text": content,
                    "position": [x, y],
                    "height": text_height,
                    "layer": layer,
                    "color": _resolve_entity_color(doc, entity, layer),
                })
                continue

            if entity_type not in {
                "LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE",
                "ELLIPSE", "SPLINE", "SOLID", "TRACE", "3DFACE",
            }:
                continue

            try:
                primitive = make_primitive(entity, max_flattening_distance=flattening_distance)
                points = [[float(vertex.x), float(vertex.y)] for vertex in primitive.vertices()]
            except Exception:
                continue

            if len(points) < 2:
                continue
            is_closed = entity_type == "CIRCLE" or (
                entity_type in {"LWPOLYLINE", "POLYLINE"}
                and bool(getattr(entity, "is_closed", False))
            )
            if is_closed:
                if points[0] != points[-1]:
                    points.append(points[0])

            remaining = MAX_SCAN_POINTS - point_count
            if len(points) > remaining:
                points = points[:remaining]
                scan_truncated = True
            for x, y in points:
                include_point(x, y)
            point_count += len(points)
            entities.append({
                "type": "polyline",
                "source_type": entity_type,
                "points": points,
                "layer": layer,
                "color": _resolve_entity_color(doc, entity, layer),
                "bounds": _points_bounds(points),
            })

            if scan_truncated:
                break
    except Exception as exc:
        return {"error": f"DXF 图元展开失败: {exc}"}

    if not entities or not math.isfinite(min_x):
        return {"error": "DXF 中没有可显示的二维矢量图元"}

    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    padding = max(width, height) * 0.02
    bounds = {
        "min_x": min_x - padding,
        "min_y": min_y - padding,
        "max_x": max_x + padding,
        "max_y": max_y + padding,
    }
    if scan_truncated:
        warnings.append("图元超过安全扫描上限，区域检测和预览可能不完整")

    views = [{
        "id": "all",
        "name": "全部图纸",
        "source": "full_modelspace",
        "bounds": bounds,
        "entity_count": len(entities),
    }]
    active_view_id = "all"
    cache = {
        "unit": unit_name,
        "unit_code": unit_code,
        "mm_per_unit": mm_per_unit,
        "unit_confirmed": mm_per_unit is not None,
        "entities": entities,
        "texts": texts,
        "views": views,
        "drawing_bounds": bounds,
        "statistics": {
            "scan_entities": len(entities),
            "scan_points": point_count,
            "texts": len(texts),
            "scan_truncated": scan_truncated,
        },
        "warnings": warnings,
    }
    with gzip.open(_cache_path(path), "wt", encoding="utf-8") as cache_file:
        json.dump(cache, cache_file, ensure_ascii=False, separators=(",", ":"))

    payload = _view_payload(cache, active_view_id)
    payload.update({
        "unit": unit_name,
        "unit_code": unit_code,
        "mm_per_unit": mm_per_unit,
        "unit_confirmed": mm_per_unit is not None,
        "views": views,
        "active_view_id": active_view_id,
        "drawing_bounds": bounds,
        "warnings": warnings,
    })
    return payload


def load_dxf_measurement_view(file_path: str, view_id: str) -> dict:
    """从准备阶段生成的缓存中读取指定图纸区域。"""
    cache_file_path = _cache_path(Path(file_path))
    if not cache_file_path.is_file():
        raise ValueError("图纸区域缓存不存在，请重新上传 DXF")
    with gzip.open(cache_file_path, "rt", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)
    payload = _view_payload(cache, view_id)
    payload.update({
        "unit": cache["unit"],
        "unit_code": cache["unit_code"],
        "mm_per_unit": cache["mm_per_unit"],
        "unit_confirmed": cache["unit_confirmed"],
        "views": cache["views"],
        "active_view_id": view_id,
        "drawing_bounds": cache["drawing_bounds"],
        "warnings": cache.get("warnings", []),
    })
    return payload


def _cache_path(file_path: Path) -> Path:
    return file_path.with_suffix(file_path.suffix + ".measurement.json.gz")


def _resolve_entity_color(doc, entity, layer_name: str) -> str:
    true_color = entity.dxf.get("true_color")
    color_index = int(entity.dxf.get("color", 256) or 256)
    if not true_color and color_index in {0, 256}:
        try:
            layer = doc.layers.get(layer_name)
            true_color = layer.dxf.get("true_color")
            color_index = abs(int(layer.dxf.get("color", 7) or 7))
        except Exception:
            color_index = 7
    if true_color:
        value = int(true_color)
        return f"#{(value >> 16) & 255:02x}{(value >> 8) & 255:02x}{value & 255:02x}"
    try:
        red, green, blue = aci2rgb(max(1, min(abs(color_index), 255)))
        return f"#{red:02x}{green:02x}{blue:02x}"
    except Exception:
        return "#b8c2cc"


def _points_bounds(points: list[list[float]]) -> dict:
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return {
        "min_x": min(x_values),
        "min_y": min(y_values),
        "max_x": max(x_values),
        "max_y": max(y_values),
    }


def _detect_views(entities: list[dict], drawing_bounds: dict) -> list[dict]:
    all_view = {
        "id": "all",
        "name": "全部图纸",
        "source": "full_modelspace",
        "bounds": drawing_bounds,
        "entity_count": len(entities),
    }
    if len(entities) < 50:
        return [all_view]

    frame_views = _detect_frame_views(entities, drawing_bounds)
    detected = frame_views if len(frame_views) >= 2 else _detect_cluster_views(entities, drawing_bounds)
    if len(detected) < 2:
        return [all_view]

    detected.sort(key=lambda view: (-view["bounds"]["max_y"], view["bounds"]["min_x"]))
    for index, view in enumerate(detected, start=1):
        view["id"] = f"region-{index}"
        view["name"] = f"图纸区域 {index}"
    detected.append(all_view)
    return detected


def _detect_frame_views(entities: list[dict], drawing_bounds: dict) -> list[dict]:
    drawing_area = _bounds_area(drawing_bounds)
    drawing_span = max(
        drawing_bounds["max_x"] - drawing_bounds["min_x"],
        drawing_bounds["max_y"] - drawing_bounds["min_y"],
        1.0,
    )
    candidates = []
    for entity in entities:
        points = entity["points"]
        if entity["source_type"] not in {"LWPOLYLINE", "POLYLINE"}:
            continue
        if len(points) < 4 or len(points) > 12 or points[0] != points[-1]:
            continue
        bounds = entity["bounds"]
        width = bounds["max_x"] - bounds["min_x"]
        height = bounds["max_y"] - bounds["min_y"]
        bbox_area = width * height
        if min(width, height) < drawing_span * 0.08 or bbox_area < drawing_area * 0.02:
            continue
        polygon_area = abs(_shoelace_area(points))
        if bbox_area <= 0 or polygon_area / bbox_area < 0.9:
            continue
        candidates.append(bounds)

    candidates.sort(key=_bounds_area, reverse=True)
    candidates = [bounds for bounds in candidates[:100] if _bounds_area(bounds) < drawing_area * 0.85]
    views = []
    minimum_count = max(25, int(len(entities) * 0.02))
    for bounds in candidates:
        if any(_overlap_ratio(bounds, view["bounds"]) > 0.25 for view in views):
            continue
        count = sum(1 for entity in entities if _center_inside(entity["bounds"], bounds))
        if count < minimum_count:
            continue
        views.append({
            "id": "",
            "name": "",
            "source": "detected_frame",
            "bounds": _pad_bounds(bounds, 0.01),
            "entity_count": count,
        })
    return views


def _detect_cluster_views(entities: list[dict], drawing_bounds: dict) -> list[dict]:
    span = max(
        drawing_bounds["max_x"] - drawing_bounds["min_x"],
        drawing_bounds["max_y"] - drawing_bounds["min_y"],
        1.0,
    )
    cell_size = span / 50
    cells: dict[tuple[int, int], list[int]] = {}
    for index, entity in enumerate(entities):
        bounds = entity["bounds"]
        center_x = (bounds["min_x"] + bounds["max_x"]) / 2
        center_y = (bounds["min_y"] + bounds["max_y"]) / 2
        cell = (
            math.floor((center_x - drawing_bounds["min_x"]) / cell_size),
            math.floor((center_y - drawing_bounds["min_y"]) / cell_size),
        )
        cells.setdefault(cell, []).append(index)

    remaining = set(cells)
    components = []
    while remaining:
        seed = remaining.pop()
        queue = [seed]
        component_cells = {seed}
        while queue:
            column, row = queue.pop()
            for column_offset in range(-2, 3):
                for row_offset in range(-2, 3):
                    neighbor = (column + column_offset, row + row_offset)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        component_cells.add(neighbor)
                        queue.append(neighbor)
        entity_indexes = [index for cell in component_cells for index in cells[cell]]
        components.append(entity_indexes)

    minimum_count = max(25, int(len(entities) * 0.025))
    views = []
    for component in components:
        if len(component) < minimum_count:
            continue
        component_bounds = _merge_bounds([entities[index]["bounds"] for index in component])
        if _bounds_area(component_bounds) < _bounds_area(drawing_bounds) * 0.005:
            continue
        views.append({
            "id": "",
            "name": "",
            "source": "spatial_cluster",
            "bounds": _pad_bounds(component_bounds, 0.03),
            "entity_count": len(component),
        })
    return views


def _view_payload(cache: dict, view_id: str) -> dict:
    view = next((item for item in cache["views"] if item["id"] == view_id), None)
    if view is None:
        raise ValueError("指定的图纸区域不存在")

    entities = []
    point_count = 0
    render_truncated = False
    for entity in cache["entities"]:
        if not _bounds_intersect(entity["bounds"], view["bounds"]):
            continue
        if len(entities) >= MAX_RENDER_ENTITIES or point_count + len(entity["points"]) > MAX_RENDER_POINTS:
            render_truncated = True
            break
        entities.append(entity)
        point_count += len(entity["points"])

    texts = [
        text for text in cache["texts"]
        if view["bounds"]["min_x"] <= text["position"][0] <= view["bounds"]["max_x"]
        and view["bounds"]["min_y"] <= text["position"][1] <= view["bounds"]["max_y"]
    ][:5000]
    warnings = []
    if render_truncated:
        warnings.append("当前区域图元过多，详细预览已达到渲染上限")
    return {
        "bounds": view["bounds"],
        "entities": entities,
        "texts": texts,
        "statistics": {
            **cache["statistics"],
            "render_entities": len(entities),
            "render_points": point_count,
            "render_truncated": render_truncated,
        },
        "view_warnings": warnings,
    }


def _shoelace_area(points: list[list[float]]) -> float:
    return sum(
        points[index][0] * points[index + 1][1] - points[index + 1][0] * points[index][1]
        for index in range(len(points) - 1)
    ) / 2


def _bounds_area(bounds: dict) -> float:
    return max(bounds["max_x"] - bounds["min_x"], 0) * max(bounds["max_y"] - bounds["min_y"], 0)


def _center_inside(inner: dict, outer: dict) -> bool:
    center_x = (inner["min_x"] + inner["max_x"]) / 2
    center_y = (inner["min_y"] + inner["max_y"]) / 2
    return outer["min_x"] <= center_x <= outer["max_x"] and outer["min_y"] <= center_y <= outer["max_y"]


def _bounds_intersect(left: dict, right: dict) -> bool:
    return not (
        left["max_x"] < right["min_x"] or left["min_x"] > right["max_x"]
        or left["max_y"] < right["min_y"] or left["min_y"] > right["max_y"]
    )


def _overlap_ratio(left: dict, right: dict) -> float:
    intersection_width = max(min(left["max_x"], right["max_x"]) - max(left["min_x"], right["min_x"]), 0)
    intersection_height = max(min(left["max_y"], right["max_y"]) - max(left["min_y"], right["min_y"]), 0)
    smaller_area = min(_bounds_area(left), _bounds_area(right))
    return intersection_width * intersection_height / smaller_area if smaller_area else 0


def _merge_bounds(bounds_list: list[dict]) -> dict:
    return {
        "min_x": min(bounds["min_x"] for bounds in bounds_list),
        "min_y": min(bounds["min_y"] for bounds in bounds_list),
        "max_x": max(bounds["max_x"] for bounds in bounds_list),
        "max_y": max(bounds["max_y"] for bounds in bounds_list),
    }


def _pad_bounds(bounds: dict, ratio: float) -> dict:
    padding = max(
        bounds["max_x"] - bounds["min_x"],
        bounds["max_y"] - bounds["min_y"],
        1.0,
    ) * ratio
    return {
        "min_x": bounds["min_x"] - padding,
        "min_y": bounds["min_y"] - padding,
        "max_x": bounds["max_x"] + padding,
        "max_y": bounds["max_y"] + padding,
    }


def calculate_room_measurements(request: DxfMeasurementRequest, file_path: str) -> dict:
    """校验人工标注多边形，并使用 DXF 模型坐标计算面积和周长。"""
    if not Path(file_path).is_file():
        raise ValueError("测量图纸不存在或已清理，请重新上传")

    doc, _ = _read_dxf_with_diagnostics(file_path)
    unit_code = int(doc.header.get("$INSUNITS", 0) or 0)
    detected_unit, detected_mm_per_unit = UNIT_DEFINITIONS.get(unit_code, (f"code_{unit_code}", None))
    calibration_result = None
    if request.calibration:
        start = request.calibration.start
        end = request.calibration.end
        if not all(math.isfinite(value) for value in [*start, *end, request.calibration.real_length_mm]):
            raise ValueError("校准数据必须是有效数值")
        model_length = math.hypot(end[0] - start[0], end[1] - start[1])
        if model_length <= 1e-9:
            raise ValueError("校准线段的两个端点不能重合")
        mm_per_unit = request.calibration.real_length_mm / model_length
        unit_name = "calibrated"
        unit_source = "manual_calibration"
        calibration_result = {
            "start": start,
            "end": end,
            "model_length": model_length,
            "real_length_mm": request.calibration.real_length_mm,
        }
    elif request.unit_override:
        unit_name = request.unit_override
        mm_per_unit = UNIT_OVERRIDE_TO_MM[request.unit_override]
        unit_source = "user_override"
    else:
        unit_name = detected_unit
        mm_per_unit = detected_mm_per_unit
        unit_source = "dxf_insunits"

    if mm_per_unit is None:
        raise ValueError("DXF 未声明单位，请选择图纸单位后再计算")

    results = []
    valid_polygons: list[tuple[int, Polygon]] = []
    for room in request.rooms:
        errors = []
        points = []
        for index, vertex in enumerate(room.vertices):
            if len(vertex) != 2 or not all(math.isfinite(float(value)) for value in vertex):
                errors.append(f"第 {index + 1} 个顶点不是有效二维坐标")
                continue
            points.append((float(vertex[0]), float(vertex[1])))

        polygon = Polygon(points) if len(points) >= 3 else None
        if polygon is None or polygon.is_empty:
            errors.append("无法构造房间多边形")
        elif not polygon.is_valid:
            errors.append(f"房间边界无效: {explain_validity(polygon)}")
        elif polygon.area <= 0:
            errors.append("房间面积必须大于零")

        result = {
            "client_id": room.client_id,
            "name": room.name.strip() or "未命名空间",
            "shape_type": room.shape_type,
            "vertices": [[x, y] for x, y in points],
            "valid": not errors,
            "errors": errors,
            "warnings": [],
            "measurement_source": "manual_annotation",
        }

        if not errors and polygon is not None:
            area_sqm = polygon.area * mm_per_unit * mm_per_unit / 1_000_000
            perimeter_m = polygon.length * mm_per_unit / 1000
            dimensions = _rotated_dimensions(polygon, mm_per_unit)
            result.update({
                "area_sqm": round(area_sqm, 3),
                "perimeter_m": round(perimeter_m, 3),
                "dimensions": dimensions,
            })
            valid_polygons.append((len(results), polygon))
        results.append(result)

    for left_index in range(len(valid_polygons)):
        result_index, left = valid_polygons[left_index]
        for right_index in range(left_index + 1, len(valid_polygons)):
            other_result_index, right = valid_polygons[right_index]
            intersection_area = left.intersection(right).area
            smaller_area = min(left.area, right.area)
            if smaller_area > 0 and intersection_area / smaller_area > 0.02:
                overlap = round(intersection_area * mm_per_unit * mm_per_unit / 1_000_000, 3)
                results[result_index]["warnings"].append(
                    f"与 {results[other_result_index]['name']} 重叠约 {overlap}㎡"
                )
                results[other_result_index]["warnings"].append(
                    f"与 {results[result_index]['name']} 重叠约 {overlap}㎡"
                )

    total_area = sum(item.get("area_sqm", 0) for item in results if item["valid"])
    return {
        "drawing_id": request.drawing_id,
        "unit": unit_name,
        "mm_per_unit": mm_per_unit,
        "unit_source": unit_source,
        "detected_unit": detected_unit,
        "calibration": calibration_result,
        "rooms": results,
        "valid_room_count": sum(1 for item in results if item["valid"]),
        "total_area_sqm": round(total_area, 3),
    }


def _rotated_dimensions(polygon: Polygon, mm_per_unit: float) -> dict:
    rectangle = polygon.minimum_rotated_rectangle
    coordinates = list(rectangle.exterior.coords)
    lengths = []
    for index in range(4):
        x1, y1 = coordinates[index]
        x2, y2 = coordinates[index + 1]
        lengths.append(math.hypot(x2 - x1, y2 - y1) * mm_per_unit)
    width_mm, height_mm = sorted((lengths[0], lengths[1]), reverse=True)
    return {
        "width_mm": round(width_mm),
        "height_mm": round(height_mm),
        "width_m": round(width_mm / 1000, 3),
        "height_m": round(height_mm / 1000, 3),
    }
