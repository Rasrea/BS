"""
PDF 矢量路径解析模块
从 CAD 导出的 PDF 中提取矢量路径（矩形/线段/多段线），
自动识别房间空间、计算面积、匹配空间名称。
与 cad_parser 完全独立，零耦合。

输出 Schema 与 _parse_dxf 完全对齐：
{
    "spaces": [
        {
            "name": "客厅",
            "area_sqm": 35.24,
            "perimeter_m": 24.58,
            "dimensions": {"width_mm": 6500, "height_mm": 5420, ...},
            "vertex_count": 4,
            "confidence": 0.85,
        }
    ],
    "total_polylines": N,    # 对应提取的矢量路径数
    "total_texts": N,
    "total_dimensions": 0,
    "parse_method": "PDF矢量解析",
}

依赖：PyMuPDF (fitz) + Shapely
"""

import os
import math
from typing import Optional

# ── 常量 ──

# PDF 坐标单位：1 point = 1/72 inch = 0.3528 mm
PT_TO_MM = 0.352777778
MM_TO_PT = 1.0 / PT_TO_MM  # ≈ 2.83465

# 房间面积过滤（平方米）
MIN_ROOM_AREA = 1.5
MAX_ROOM_AREA = 300.0

# ── 房间关键词（与 cad_parser.py 完全一致）──
ROOM_KEYWORDS = [
    "客厅", "餐厅", "主卧", "次卧", "卧室", "厨房", "客房",
    "卫生间", "厕所", "浴室", "阳台", "书房", "衣帽间",
    "玄关", "走廊", "过道", "储藏室", "儿童房", "老人房",
    "living", "dining", "bedroom", "kitchen", "bathroom",
    "balcony", "study", "corridor", "living room",
    "客餐厅", "主卫", "次卫", "公卫",
    "家政", "储物", "多功能", "棋牌", "影音",
    "门厅", "西厨", "中厨", "阳光房",
    "茶室", "棋牌室", "影音室", "健身房", "瑜伽",
    "保姆房", "工人房", "杂物间", "设备间",
    "入户花园", "观景台", "露台", "花园",
    "主卧套房", "套房", "步入式", "更衣室",
    "北次卧", "南次卧", "东次卧", "西次卧",
    "北卧", "南卧", "东卧", "西卧",
    "主卫", "次卫", "客卫", "公卫",
    "中厨", "西厨", "开放式厨房",
    "大厅", "中厅", "小厅",
    "休息室", "娱乐室", "活动室",
    "电梯厅", "电梯间", "前室",
    "spa", "sauna", "laundry", "pantry",
    "foyer", "hall", "lobby", "atrium",
]

# 文字黑名单（过滤施工标注、尺寸等）
TEXT_BLACKLIST = [
    "施工说明", "设计规范", "图例", "DRAWING", "DATE", "CHEDKED",
    "DESIGNER", "TEL", "TLEI", "OWNER", "www.", "华杰东方",
    "设计部", "业主", "设计师", "公司", "有限公司", "规格",
    "序号", "名称", "材料", "备注", "工艺", "mm", "此墙",
    "承重墙", "砸不了", "LTD", "INTERLOR", "BUREAU", "NO.",
    "比例", "图号", "图纸", "目录", "说明", "图框",
    "铝扣板", "灯带", "灯槽", "吊顶", "浴霸", "石膏板",
    "欧松板", "隐形门", "踢脚线", "柜子", "插座", "开关",
    "灯位", "筒灯", "射灯", "轨道灯", "基层", "封假梁",
    "直线吊顶", "反光灯槽", "osb板", "OSB板",
    "浴缸", "淋浴", "洗手台", "包水管", "墨菲床",
    "五斗柜", "鞋柜", "鞋帽柜", "壁龛",
    "窗台石", "拆至上梁", "内嵌式",
    "此墙", "注：", "客户姓名", "工程地址",
    "设 计 师", "日   期", "孙老师", "济宁",
    "标高", "完成面", "建筑完成面", "结构面",
    "地面完成面", "天花完成面", "墙面完成面",
    "原始结构", "拆改", "砌墙", "新建墙体",
    "回填", "找平", "防水", "保护层",
    "排水", "给水", "强电", "弱电", "点位",
    "空调", "新风", "暖气", "地暖", "分水器",
    "烟道", "风道", "管井", "检修口",
    "过梁", "圈梁", "构造柱",
    "定位", "x=", "y=", "偏移",
    "投影", "剖面", "立面", "节点",
    "A0", "A1", "A2", "A3", "A4",
    "图幅", "图名", "图号",
    "立面图", "剖面图", "平面图", "顶面图",
    "地坪", "标高", "层高",
    "门洞", "窗洞", "预留洞",
    "嵌缝", "留缝", "压条", "收口",
    "门槛石", "挡水条",
    "止水带", "反坎",
    "减力墙", "剪力墙",
    "柱位", "梁位",
    "0.000", "±0.000",
]


# ── 坐标转换工具 ──

def pt_to_mm(pt_val: float) -> float:
    """PDF point → 毫米"""
    return pt_val * PT_TO_MM


def pt_to_m(pt_val: float) -> float:
    """PDF point → 米"""
    return pt_val * PT_TO_MM / 1000.0


# ── 主入口 ──

def parse_pdf_vector(pdf_path: str) -> dict:
    """
    PDF 矢量路径解析主入口。

    1. 用 PyMuPDF get_drawings() 提取矢量路径
    2. 筛选封闭矩形/多边形作为房间候选
    3. 用 get_text('blocks') 提取文字匹配房间名
    4. 输出与 _parse_dxf() 一致的 schema

    若矢量数=0，返回 {"vector_count": 0} 触发上层回退视觉识别
    """
    import fitz

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {
            "error": f"PDF 文件读取失败: {str(e)}",
            "spaces": [],
            "parse_method": "PDF矢量解析",
            "vector_count": 0,
        }

    try:
        total_pages = len(doc)
        all_spaces = []

        for page_num in range(total_pages):
            page = doc[page_num]

            # ── 步骤1：提取矢量路径 ──
            drawings = page.get_drawings()

            # ── 步骤2：提取文字块 ──
            text_blocks = page.get_text("blocks")

            # ── 步骤3：从 drawings 提取房间多边形 ──
            room_polygons = _extract_room_polygons(drawings)

            # ── 步骤4：从 text_blocks 提取房间标签 ──
            room_labels = _extract_room_labels(text_blocks)

            # ── 步骤5：多边形 → 房间，自动匹配标签 ──
            page_spaces = _polygons_to_spaces(room_polygons, room_labels)

            # 标记来源页码
            for s in page_spaces:
                s["_page"] = page_num + 1

            all_spaces.extend(page_spaces)

        doc.close()

        if not all_spaces:
            return {
                "spaces": [],
                "total_polylines": 0,
                "total_texts": 0,
                "total_dimensions": 0,
                "parse_method": "PDF矢量解析",
                "vector_count": 0,
                "total_pages": total_pages,
                "notes": "未从PDF中提取到有效矢量路径，建议回退视觉识别",
            }

        return {
            "spaces": all_spaces,
            "total_polylines": len(all_spaces),
            "total_texts": 0,
            "total_dimensions": 0,
            "parse_method": f"PDF矢量解析 (共{total_pages}页)",
            "vector_count": len(all_spaces),
            "total_pages": total_pages,
        }

    except Exception as e:
        return {
            "error": f"PDF 矢量解析失败: {str(e)}",
            "spaces": [],
            "parse_method": "PDF矢量解析",
            "vector_count": 0,
        }


# ── 步骤3：从 drawings 提取房间多边形 ──

def _extract_room_polygons(drawings: list) -> list:
    """从 PyMuPDF get_drawings() 结果中提取封闭多边形作为房间候选"""
    from shapely.geometry import Polygon

    candidates = []

    for d in drawings:
        items = d.get("items", [])
        rect = d.get("rect")
        fill = d.get("fill")
        fill_opacity = d.get("fill_opacity")

        # ── 情况A：矩形 (re) ──
        for item in items:
            if item[0] == "re":
                r = item[1]  # fitz.Rect
                w_mm = pt_to_mm(r.width)
                h_mm = pt_to_mm(r.height)
                area_sqm = w_mm * h_mm / 1_000_000

                if area_sqm < MIN_ROOM_AREA or area_sqm > MAX_ROOM_AREA:
                    continue

                poly = Polygon([
                    (pt_to_m(r.x0), pt_to_m(r.y0)),
                    (pt_to_m(r.x1), pt_to_m(r.y0)),
                    (pt_to_m(r.x1), pt_to_m(r.y1)),
                    (pt_to_m(r.x0), pt_to_m(r.y1)),
                ])
                candidates.append({
                    "polygon": poly,
                    "area_sqm": round(area_sqm, 2),
                    "centroid": (pt_to_m((r.x0 + r.x1) / 2), pt_to_m((r.y0 + r.y1) / 2)),
                    "points": [
                        (pt_to_mm(r.x0), pt_to_mm(r.y0)),
                        (pt_to_mm(r.x1), pt_to_mm(r.y0)),
                        (pt_to_mm(r.x1), pt_to_mm(r.y1)),
                        (pt_to_mm(r.x0), pt_to_mm(r.y1)),
                    ],
                    "confidence": 0.85,
                    "source": "rect",
                })
                break

        # ── 情况B：线段闭合路径（多线段凑的封闭多边形）──
        # 取所有 line 端点，若形成闭合路径则构建 polygon
        line_pts = []
        is_closed = False
        for item in items:
            if item[0] == "l":
                line_pts.append((item[1].x, item[1].y))

        if len(line_pts) >= 3:
            # 检查是否闭合：首尾距离 < 5pt
            first = line_pts[0]
            last = line_pts[-1]
            dx = first[0] - last[0]
            dy = first[1] - last[1]
            is_closed = (dx * dx + dy * dy) ** 0.5 < 5

            if is_closed:
                coords_m = [(pt_to_m(x), pt_to_m(y)) for x, y in line_pts]
                try:
                    poly = Polygon(coords_m)
                    if poly.is_valid and not poly.is_empty:
                        area_sqm = poly.area
                        if MIN_ROOM_AREA < area_sqm < MAX_ROOM_AREA:
                            candidates.append({
                                "polygon": poly,
                                "area_sqm": round(area_sqm, 2),
                                "centroid": (poly.centroid.x, poly.centroid.y),
                                "points": [(pt_to_mm(x), pt_to_mm(y)) for x, y in line_pts],
                                "confidence": 0.80,
                                "source": "path",
                            })
                except Exception:
                    pass

    return candidates


# ── 步骤4：从 text_blocks 提取房间标签 ──

def _extract_room_labels(text_blocks: list) -> list:
    """从 PDF 文字块中提取房间名标签"""
    labels = []

    for b in text_blocks:
        # blocks format: (x0, y0, x1, y1, text, block_no, block_type)
        if len(b) < 5:
            continue
        text = b[4].strip()
        if not text:
            continue

        # 黑名单过滤
        if any(kw in text for kw in TEXT_BLACKLIST):
            continue
        # 跳过纯数字/过短
        if len(text) <= 1:
            continue
        # 跳过纯英文上标
        if text.isascii() and len(text) <= 2:
            continue
        # 跳过过长文字
        if len(text) > 20:
            continue

        x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
        cx = pt_to_m((x0 + x1) / 2)
        cy = pt_to_m((y0 + y1) / 2)

        is_keyword = any(kw in text for kw in ROOM_KEYWORDS)

        # 只保留含中文或含关键词的文字
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in text)
        if is_keyword or has_cjk:
            labels.append({
                "name": text,
                "x_m": cx,
                "y_m": cy,
                "is_keyword": is_keyword,
            })

    return labels


# ── 步骤5：多边形 → 房间空间 ──

def _polygons_to_spaces(polygons: list, labels: list) -> list:
    """将候选多边形 + 文字标签 → 结构化房间列表"""
    from shapely.geometry import Point

    # 按面积降序
    polygons.sort(key=lambda p: p["area_sqm"], reverse=True)
    unused_labels = list(labels)

    result = []

    for cand in polygons:
        poly = cand["polygon"]
        centroid = Point(cand["centroid"])

        # 找最佳匹配文字标签
        best_name = "未命名空间"
        best_dist = float("inf")
        best_idx = -1

        for i, lbl in enumerate(unused_labels):
            lbl_pt = Point(lbl["x_m"], lbl["y_m"])
            if poly.contains(lbl_pt) or poly.touches(lbl_pt):
                dist = 0
            else:
                dist = centroid.distance(lbl_pt)

            if dist < best_dist:
                best_name = lbl["name"]
                best_dist = dist
                best_idx = i

        if best_idx >= 0:
            unused_labels.pop(best_idx)

        # 计算 dimensions
        points = cand["points"]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        width_mm = max(xs) - min(xs)
        height_mm = max(ys) - min(ys)

        conf = cand["confidence"]
        if best_name == "未命名空间":
            conf = 0.6

        space = {
            "name": best_name,
            "area_sqm": cand["area_sqm"],
            "perimeter_m": round(poly.length, 2),
            "dimensions": {
                "width_mm": round(width_mm),
                "height_mm": round(height_mm),
                "width_m": round(width_mm / 1000, 3),
                "height_m": round(height_mm / 1000, 3),
            },
            "vertex_count": len(points),
            "confidence": conf,
        }
        result.append(space)

    return result
