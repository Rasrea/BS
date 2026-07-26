"""
CAD 图纸解析模块
支持 DXF 矢量解析 + 图片/PDF 的视觉 AI 识别（Ollama 本地 LLaVA）
"""
import os
import base64
import json
import re
import requests
from typing import Optional


def _ollama_chat(prompt: str, image_b64: str) -> str:
    """调用 Ollama 本地 LLaVA 进行图像识别"""
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "llava:7b",
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64]
            }
        ],
        "stream": False
    }
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "")


def _image_to_ollama_b64(image_path: str) -> str:
    """将图片转 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# == 主入口：根据文件扩展名自动选择解析方式 ==

def parse_cad_file(file_path: str) -> dict:
    """
    解析 CAD 文件（自动判断文件类型）

    支持:
      .dxf  → 矢量解析 (ezdxf)
      .dwg  → 尝试转 DXF 后解析 + 图片回退
      .jpg/.png/.webp/.bmp → Ollama/LLaVA 视觉识别
      .pdf  → 提取页面为图片后用 Ollama/LLaVA 识别
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".dxf":
        return _parse_dxf(file_path)

    elif ext == ".dwg":
        dxf_path = convert_dwg_to_dxf(file_path)
        if dxf_path:
            result = _parse_dxf(dxf_path)
            result["parse_method"] = "dwg→dxf矢量解析"
            return result
        return _parse_cad_image(file_path, source_type="DWG图纸（视觉识别）")

    elif ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        return _parse_cad_image(file_path, source_type="CAD图片（视觉识别）")

    elif ext == ".pdf":
        return _parse_cad_pdf(file_path)

    else:
        return {
            "error": f"不支持的 CAD 格式: {ext}",
            "spaces": [],
            "supported": [".dxf", ".dwg", ".jpg", ".png", ".pdf"],
        }


# == DXF 矢量解析（待按 DXF_REWRITE_PLAN.md 重写） ==

def _parse_dxf(file_path: str) -> dict:
    import ezdxf
    from shapely.geometry import Polygon, Point

    try:
        doc = ezdxf.readfile(file_path)
        auditor = doc.audit()
        dxf_repair_count = len(auditor.fixes)
    except Exception as e:
        return {"error": f"DXF 文件读取失败: {str(e)}", "spaces": [], "parse_method": "dxf矢量解析"}

    msp = doc.modelspace()

    # DXF V2 TODO [P0-标准化]: 读取 $INSUNITS 并统一换算到毫米；处理 OCS/WCS、
    # INSERT/BLOCK 的平移、旋转和缩放，避免直接把原始坐标当作毫米坐标。

    # DXF V2 TODO [P0-实体提取]: 不应只识别 LWPOLYLINE。需要统一提取
    # LWPOLYLINE、POLYLINE、HATCH 边界，并保留 bulge/ARC 曲线信息和实体 handle。
    polylines = []
    for entity in msp.query("LWPOLYLINE"):
        points = [(v[0], v[1]) for v in entity.get_points()]
        if entity.closed and len(points) >= 3:
            polylines.append({"points": points, "layer": entity.dxf.layer})

    texts = []
    for entity in msp.query("TEXT"):
        texts.append({
            "text": entity.dxf.text.strip(),
            "position": (entity.dxf.insert.x, entity.dxf.insert.y),
            "layer": entity.dxf.layer,
            "height": entity.dxf.height,
        })
    for entity in msp.query("MTEXT"):
        text = entity.plain_text().strip()
        if text:
            texts.append({
                "text": text,
                "position": (entity.dxf.insert.x, entity.dxf.insert.y),
                "layer": entity.dxf.layer,
                "height": 4.0,
            })

    # DXF V2 TODO [P1-尺寸]: DIMENSION 只作为几何结果的校验证据，不用于创造房间；
    # 正确处理 <>、文字覆盖、dimlfac、前后缀和不同标注类型。
    dimensions = []
    for entity in msp.query("DIMENSION"):
        try:
            dim_text = ""
            if hasattr(entity.dxf, 'text') and entity.dxf.text:
                dim_text = entity.dxf.text
            elif hasattr(entity, 'get_measurement'):
                dim_text = str(round(entity.get_measurement()))
            def_point = entity.dxf.defpoint2
            # 收集所有定义点用于后续过滤
            dim_points = []
            if hasattr(entity.dxf, 'defpoint'):
                dim_points.append((entity.dxf.defpoint.x, entity.dxf.defpoint.y))
            dim_points.append((def_point.x, def_point.y))
            if hasattr(entity.dxf, 'text_midpoint') and entity.dxf.text_midpoint:
                dim_points.append((entity.dxf.text_midpoint.x, entity.dxf.text_midpoint.y))
            angle = entity.dxf.angle if hasattr(entity.dxf, 'angle') else 0
            dimensions.append({
                "text": dim_text,
                "position": (def_point.x, def_point.y),
                "points": dim_points,
                "angle": angle,
                "layer": entity.dxf.layer,
            })
        except Exception:
            pass

    # DXF V2 TODO [P1-语义]: 房间词典、文本黑名单和图层规则应移到可配置模块，
    # 文本分类应输出候选类型与证据，不能仅依赖子串命中。
    room_keywords = [
        "客厅", "餐厅", "主卧", "次卧", "卧室", "厨房", "客房",
        "卫生间", "厕所", "浴室", "阳台", "书房", "衣帽间",
        "玄关", "走廊", "过道", "储藏室", "儿童房", "老人房",
        "living", "dining", "bedroom", "kitchen", "bathroom",
        "balcony", "study", "corridor", "living room",
        "客餐厅", "主卫", "次卫", "公卫",
        "家政", "储物", "多功能", "棋牌", "影音",
        "门厅", "西厨", "中厨", "阳光房",
        # 补充常见房间名
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

    # DXF V2 TODO [P0-几何]: 这里需要替换为“空间候选生成”流程：离散化曲线、
    # 校验/修复 Polygon、处理洞，并根据单位自适应面积范围，不能硬编码平方毫米阈值。
    valid_polylines = []
    for pl in polylines:
        poly = Polygon(pl["points"])
        area_mm2 = poly.area
        if 4_000_000 < area_mm2 < 200_000_000:
            valid_polylines.append({"polygon": poly, "points": pl["points"]})
        elif "墙体" in str(pl.get("layer", "")).lower() or "wall" in str(pl.get("layer", "")).lower():
            valid_polylines.append({"polygon": poly, "points": pl["points"]})

    # ── 文字黑名单：过滤施工标注、尺寸、公司信息等无效文本 ──
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
        # 补充过滤项
        "标高", "完成面", "建筑完成面", "结构面",
        "地面完成面", "天花完成面", "墙面完成面",
        "原始结构", "拆改", "砌墙", "新建墙体",
        "回填", "找平", "防水", "保护层",
        "排水", "给水", "强电", "弱电", "点位",
        "空调", "新风", "暖气", "地暖", "分水器",
        "烟道", "风道", "管井", "检修口",
        "过梁", "圈梁", "构造柱",
        "定位", "x=\"", "y=\"", "偏移",
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

    def _first_line(text: str) -> str:
        """多行文字合并后取首行（处理DXF中"客\\n厅"之类的断行）"""
        # 先合并被换行符打断的短行：如果每段很短（≤2字符），合并回来
        parts = text.split("\n")
        if len(parts) >= 2 and all(0 < len(p.strip()) <= 2 for p in parts if p.strip()):
            return "".join(p.strip() for p in parts)
        return parts[0].strip()

    # ── 构建尺寸标注位置的快速查找集（用于过滤标注文字）──
    # 收集所有尺寸线位置，用于剔除紧邻尺寸标注的纯数字/短文本
    dim_positions = []
    for d in dimensions:
        for dp in d.get("points", []):
            dim_positions.append(dp)
        # 标注文本本身也加入
        dim_positions.append(d["position"])
    # 如果文字位置在任意尺寸标注点 500mm 范围内且为纯数字，跳过
    def _is_near_dimension(pt, threshold_mm=500):
        for dp in dim_positions:
            dx = pt[0] - dp[0]
            dy = pt[1] - dp[1]
            if (dx*dx + dy*dy) ** 0.5 < threshold_mm:
                return True
        return False

    # ── 构建所有候选文字标签（先关键词过滤，保留全部候选用于兜底）──
    # DXF V2 TODO [P0-图层]: 删除固定白名单依赖。图层先做名称归一化，再结合
    # 图层名称、实体组成和项目配置推断 wall/room/text/dimension 等角色。
    ROOM_TEXT_LAYERS = {"000-墙体1", "0", "TEXT", "标注", "文字", "房间名", "空间名", "名称", "公共"}

    # 一层：含关键词的文字（高置信度）
    keyword_labels = []
    # 二层：短文本但无关键词的候选（低置信度兜底）
    fallback_labels = []
    for t in texts:
        layer = t.get("layer", "")
        if layer not in ROOM_TEXT_LAYERS:
            continue
        raw_text = t["text"]
        first = _first_line(raw_text)
        # 跳过过长的文字（施工说明等）
        if len(first) > 20:
            continue
        # 黑名单过滤
        if any(kw in first for kw in TEXT_BLACKLIST):
            continue
        pt = Point(t["position"])
        label = {"name": first, "pt": pt, "layer": layer}
        is_keyword = any(kw in first for kw in room_keywords)
        if is_keyword:
            keyword_labels.append(label)
        elif len(first) <= 6:
            # 短文本但含中文字符，可能为房间名
            has_cjk = any('\u4e00' <= c <= '\u9fff' for c in first)
            if has_cjk:
                # 仅在远离尺寸标注时才考虑
                if not _is_near_dimension(t["position"]):
                    fallback_labels.append(label)

    # 去重：相同位置（100格）取最短名称
    def dedup_labels(labels):
        seen = {}
        for rl in labels:
            key = (round(rl["pt"].x, -2), round(rl["pt"].y, -2))
            if key not in seen or len(rl["name"]) < len(seen[key]["name"]):
                seen[key] = rl
        return list(seen.values())

    keyword_labels = dedup_labels(keyword_labels)
    fallback_labels = dedup_labels(fallback_labels)

    # 剔除 fallback 中已含关键词的文本（避免重复）
    fallback_pt_keys = {(round(rl["pt"].x, -2), round(rl["pt"].y, -2)) for rl in fallback_labels}
    kw_pt_keys = {(round(rl["pt"].x, -2), round(rl["pt"].y, -2)) for rl in keyword_labels}
    fallback_labels = [rl for rl in fallback_labels
                       if (round(rl["pt"].x, -2), round(rl["pt"].y, -2)) not in kw_pt_keys]

    # DXF V2 TODO [P0-候选清洗]: 在标签关联前处理重复、近似重合、包含和交叠关系；
    # 不能仅按面积降序，因为建筑外框可能优先消费所有内部标签。
    # 按面积降序排列多边形，大空间优先匹配房间名
    valid_polylines.sort(key=lambda vp: vp["polygon"].area, reverse=True)

    # DXF V2 TODO [P0-标签关联]: 只自动确认位于候选空间内部的标签；内部有多个标签时
    # 根据图层、文本类型、字高和距 representative_point 的距离评分。外部最近标签只能告警，不能强配。
    def _find_best_label(poly, unused_labels):
        """找最佳匹配标签：先检查文本是否在多边形内部，其次就近匹配"""
        centroid = poly.centroid
        best_name = "未命名空间"
        best_dist = float("inf")
        best_idx = -1

        for i, rl in enumerate(unused_labels):
            # 第一优先：文本点落在多边形内部
            if poly.contains(rl["pt"]) or poly.touches(rl["pt"]):
                # 内部点的距离设为0，确保优先选中
                dist = 0
            else:
                dist = centroid.distance(rl["pt"])
            if dist < best_dist:
                best_name = rl["name"]
                best_dist = dist
                best_idx = i

        # 不设距离阈值——DXF为多户型拼版，文字离多边形质心可能很远
        # 靠"贪婪匹配+去重"机制保证每个房间名只对应一个空间

        return best_name, best_idx

    spaces_raw = []
    # 第一轮：用关键字标签匹配
    unused_keyword = list(keyword_labels)
    for vp in valid_polylines:
        poly = vp["polygon"]
        best_name, best_idx = _find_best_label(poly, unused_keyword)
        if best_idx >= 0:
            unused_keyword.pop(best_idx)
        spaces_raw.append((best_name, poly, vp["points"]))

    # 第二轮：未命名空间尝试用 fallback 标签兜底
    unused_fallback = list(fallback_labels)
    for i, (name, poly, points) in enumerate(spaces_raw):
        if name == "未命名空间":
            best_name, best_idx = _find_best_label(poly, unused_fallback)
            if best_idx >= 0:
                spaces_raw[i] = (best_name, poly, points)
                unused_fallback.pop(best_idx)

    # DXF V2 TODO [P0-结果]: 面积需注明口径和边界来源；宽高使用最小旋转矩形，
    # 异形空间不强行解释为开间/进深；置信度由可追溯证据计算，不能使用固定常量。
    result_spaces = []
    for name, poly, points in spaces_raw:
        try:
            area_m2 = poly.area / 1_000_000
            perimeter_m = poly.length / 1000
            minx, miny, maxx, maxy = poly.bounds
            result_spaces.append({
                "name": name,
                "area_sqm": round(area_m2, 2),
                "perimeter_m": round(perimeter_m, 2),
                "vertices": [[float(x), float(y)] for x, y in points],
                "boundary_source": "lwpolyline",
                "dimensions": {
                    "width_mm": round(maxx - minx),
                    "height_mm": round(maxy - miny),
                    "width_m": round((maxx - minx) / 1000, 3),
                    "height_m": round((maxy - miny) / 1000, 3),
                },
                "vertex_count": len(points),
                "confidence": 0.85 if name != "未命名空间" else 0.6,
            })
        except Exception:
            pass

    # DXF V2 TODO [P0-停用]: 当前墙线兜底没有从 segments 构造边界，输出主要来自
    # 标签间距、默认尺寸和经验系数。新版上线前应停用，避免估算面积进入自动报价。
    # ── 补充：当LW闭合多边形无法提取房间时，使用LINE墙体线+尺寸标注推算 ──
    if len(result_spaces) == 0 and keyword_labels:
        result_spaces = _calc_rooms_from_lines(msp, keyword_labels, dimensions)
        parse_method = "dxf墙线拓扑识别"
        needs_manual_review = True
        if result_spaces:
            furniture_fallback_names = [
                space["name"]
                for space in result_spaces
                if space.get("boundary_source") == "wall_mask_furniture_fallback"
            ]
            if furniture_fallback_names:
                manual_review_reason = (
                    f"{', '.join(furniture_fallback_names)} 的闭合边界受家具混线影响，"
                    "已作为低置信预填保留，请优先人工核对"
                )
            else:
                manual_review_reason = "已从墙线拓扑生成候选房间边界，请人工调整并核对低置信区域"
        else:
            manual_review_reason = "墙线无法形成包含房间文字的可靠闭合区域，请进入人工测量补画"
    else:
        parse_method = "dxf矢量解析"
        needs_manual_review = any(space.get("confidence", 0) < 0.8 for space in result_spaces)
        manual_review_reason = "部分空间名称或边界置信度较低，请在人工测量中核对" if needs_manual_review else ""

    return {
        "spaces": result_spaces,
        "total_polylines": len(polylines),
        "total_texts": len(texts),
        "total_dimensions": len(dimensions),
        "parse_method": parse_method,
        "needs_manual_review": needs_manual_review,
        "manual_review_reason": manual_review_reason,
        "dxf_repair_count": dxf_repair_count,
    }


# ── 墙线拓扑兜底：从线网构造真实闭合区域 ──

def _calc_rooms_from_lines(msp, room_labels, dimensions) -> list:
    import math
    from statistics import median

    from shapely.geometry import LineString, Point, box
    from shapely.ops import polygonize, snap, split, unary_union

    del dimensions  # 尺寸标注仅作为后续校验依据，不用于创造房间边界。

    wall_tokens = (
        "墙", "建筑", "结构", "模块外线", "wall", "a-wall", "partition", "structure",
    )
    auxiliary_tokens = (
        "标注", "尺寸", "轴", "文字", "家具", "洁具", "电气", "门", "窗",
        "dimension", "dim", "axis", "text", "furniture", "door", "window",
        "hatch", "填充",
    )
    furniture_tokens = (
        "家具", "衣柜", "橱柜", "柜", "床", "桌", "椅", "沙发", "茶几", "马桶",
        "洁具", "灶", "水槽", "洗衣", "冰箱", "电视", "浴缸", "花洒", "盆",
        "furniture", "sofa", "table", "chair", "bed", "cabinet", "wardrobe",
        "toilet", "sink", "stove", "appliance",
    )
    opening_tokens = (
        "门", "窗", "door", "window", "opening", "推拉", "平开", "折叠",
    )
    annotation_tokens = (
        "标注", "尺寸", "文字", "轴", "图框", "索引", "引线", "填充",
        "dimension", "annotation", "text", "axis", "frame", "hatch",
    )

    def iter_source_entities(entities, parent_layer="0", block_path=(), depth=0):
        if depth > 12:
            return
        for entity in entities:
            raw_layer = str(entity.dxf.get("layer", "0"))
            effective_layer = parent_layer if raw_layer == "0" and parent_layer != "0" else raw_layer
            if entity.dxftype() != "INSERT":
                yield entity, raw_layer, effective_layer, block_path
                continue
            block_name = str(entity.dxf.get("name", ""))
            try:
                virtual_entities = list(entity.virtual_entities())
            except Exception:
                continue
            yield from iter_source_entities(
                virtual_entities,
                effective_layer,
                (*block_path, block_name),
                depth + 1,
            )

    def entity_segments(entity):
        entity_type = entity.dxftype()
        points = []
        closed = False
        if entity_type == "LINE":
            points = [entity.dxf.start, entity.dxf.end]
        elif entity_type == "LWPOLYLINE":
            points = list(entity.get_points("xy"))
            closed = bool(entity.closed)
        elif entity_type == "POLYLINE":
            points = list(entity.points())
            closed = bool(entity.is_closed)
        elif entity_type == "ARC":
            try:
                points = list(entity.flattening(50))
            except Exception:
                return []
        else:
            return []

        coordinates = [(float(point[0]), float(point[1])) for point in points]
        pairs = list(zip(coordinates, coordinates[1:]))
        if closed and len(coordinates) > 2:
            pairs.append((coordinates[-1], coordinates[0]))
        return [
            LineString((start, end))
            for start, end in pairs
            if math.dist(start, end) >= 20
        ]

    source_entities = list(iter_source_entities(msp))
    furniture_block_paths = {
        block_path
        for _, raw_layer, effective_layer, block_path in source_entities
        if block_path
        and any(
            token in f"{raw_layer}|{effective_layer}".lower()
            for token in furniture_tokens
        )
    }

    def belongs_to_mixed_furniture_block(block_path):
        return any(
            len(block_path) >= len(furniture_path)
            and block_path[:len(furniture_path)] == furniture_path
            for furniture_path in furniture_block_paths
        )

    segment_records = []
    potential_door_guides = []
    for entity, raw_layer, effective_layer, block_path in source_entities:
        semantic_source = "|".join((*block_path, raw_layer, effective_layer)).lower()
        if any(token in semantic_source for token in furniture_tokens):
            continue
        if any(token in semantic_source for token in annotation_tokens):
            continue
        opening_hint = any(token in semantic_source for token in opening_tokens)
        wall_hint = any(token in semantic_source for token in wall_tokens)

        if entity.dxftype() == "ARC":
            try:
                radius = float(entity.dxf.radius)
                sweep = (float(entity.dxf.end_angle) - float(entity.dxf.start_angle)) % 360
                center = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                start_point = (float(entity.start_point.x), float(entity.start_point.y))
                end_point = (float(entity.end_point.x), float(entity.end_point.y))
            except Exception:
                radius = 0
                sweep = 0
                center = start_point = end_point = (0.0, 0.0)

            if 350 <= radius <= 1800 and 25 <= sweep <= 135:
                potential_door_guides.append({
                    "center": center,
                    "endpoints": (start_point, end_point),
                    "radius": radius,
                })
                continue
            if opening_hint or not wall_hint:
                continue

        if opening_hint:
            continue
        extracted = entity_segments(entity)
        furniture_suspect = belongs_to_mixed_furniture_block(block_path)
        segment_records.extend(
            (effective_layer, segment, furniture_suspect)
            for segment in extracted
        )

    def matches_door_leaf(segment, guide):
        if not 0.75 * guide["radius"] <= segment.length <= 1.25 * guide["radius"]:
            return False
        coordinates = (segment.coords[0], segment.coords[-1])
        tolerance = max(80.0, min(160.0, guide["radius"] * 0.1))
        for hinge_index in (0, 1):
            if math.dist(coordinates[hinge_index], guide["center"]) > tolerance:
                continue
            leaf_end = coordinates[1 - hinge_index]
            if min(math.dist(leaf_end, endpoint) for endpoint in guide["endpoints"]) <= tolerance:
                return True
        return False

    door_leaf_ids = set()
    for guide in potential_door_guides:
        matching_ids = {
            id(segment)
            for _, segment, _ in segment_records
            if matches_door_leaf(segment, guide)
        }
        door_leaf_ids.update(matching_ids)

    segments_by_layer = {}
    furniture_suspect_ids = set()
    for layer, segment, furniture_suspect in segment_records:
        if id(segment) in door_leaf_ids:
            continue
        segments_by_layer.setdefault(layer, []).append(segment)
        if furniture_suspect:
            furniture_suspect_ids.add(id(segment))

    if not segments_by_layer:
        return []

    preferred_layers = {
        layer for layer in segments_by_layer
        if layer == "0" or any(token in layer.lower() for token in wall_tokens)
    }
    eligible_layers = [
        layer for layer in segments_by_layer
        if not any(token in layer.lower() for token in auxiliary_tokens)
    ]
    eligible_layers.sort(
        key=lambda layer: sum(segment.length for segment in segments_by_layer[layer]),
        reverse=True,
    )
    preferred_segment_count = sum(len(segments_by_layer[layer]) for layer in preferred_layers)
    selected_layers = (
        preferred_layers
        if preferred_segment_count >= 20
        else preferred_layers | set(eligible_layers[:5])
    )
    linework = [
        segment
        for layer in selected_layers
        for segment in segments_by_layer[layer]
    ]
    if len(linework) < 3:
        return []

    typical_length = median(segment.length for segment in linework)
    snap_tolerance = max(20.0, min(150.0, typical_length * 0.02))
    max_gap = 1200.0

    network = unary_union(linework)
    network = unary_union(snap(network, network, snap_tolerance))

    def line_parts(geometry):
        if geometry.geom_type == "LineString":
            return [geometry]
        if hasattr(geometry, "geoms"):
            return [part for item in geometry.geoms for part in line_parts(item)]
        return []

    noded_lines = [line for line in line_parts(network) if line.length >= 20]

    def endpoint_key(point):
        return (
            round(point[0] / snap_tolerance),
            round(point[1] / snap_tolerance),
        )

    endpoint_counts = {}
    endpoint_records = []
    for line in noded_lines:
        coordinates = list(line.coords)
        for point, neighbor in ((coordinates[0], coordinates[1]), (coordinates[-1], coordinates[-2])):
            key = endpoint_key(point)
            endpoint_counts[key] = endpoint_counts.get(key, 0) + 1
            inward_length = math.dist(point, neighbor)
            if inward_length:
                endpoint_records.append({
                    "point": point,
                    "key": key,
                    "inward": (
                        (neighbor[0] - point[0]) / inward_length,
                        (neighbor[1] - point[1]) / inward_length,
                    ),
                })

    dangling = [record for record in endpoint_records if endpoint_counts[record["key"]] == 1]
    gap_candidates = []
    for left_index, left in enumerate(dangling):
        for right_index in range(left_index + 1, len(dangling)):
            right = dangling[right_index]
            distance = math.dist(left["point"], right["point"])
            if distance < snap_tolerance or distance > max_gap:
                continue
            gap_direction = (
                (right["point"][0] - left["point"][0]) / distance,
                (right["point"][1] - left["point"][1]) / distance,
            )
            left_alignment = -sum(a * b for a, b in zip(left["inward"], gap_direction))
            right_alignment = sum(a * b for a, b in zip(right["inward"], gap_direction))
            if left_alignment >= 0.92 and right_alignment >= 0.92:
                gap_candidates.append((distance, left_index, right_index))

    repaired_endpoints = set()
    repair_lines = []
    for _, left_index, right_index in sorted(gap_candidates):
        if left_index in repaired_endpoints or right_index in repaired_endpoints:
            continue
        repaired_endpoints.update((left_index, right_index))
        repair_lines.append(LineString((dangling[left_index]["point"], dangling[right_index]["point"])))

    repaired_network = unary_union([*noded_lines, *repair_lines])
    raw_polygons = list(polygonize(repaired_network))
    polygons = []
    for polygon in raw_polygons:
        if not polygon.is_valid or polygon.is_empty:
            continue
        if not 1_000_000 <= polygon.area <= 300_000_000:
            continue
        compactness = 4 * math.pi * polygon.area / max(polygon.length ** 2, 1)
        if compactness < 0.015:
            continue
        polygons.append(polygon)

    used_polygons = set()
    result = []
    repair_union = unary_union(repair_lines) if repair_lines else None
    for room_label in room_labels:
        exact_matches = [polygon for polygon in polygons if polygon.covers(room_label["pt"])]
        matches = exact_matches or [
            polygon for polygon in polygons
            if polygon.distance(room_label["pt"]) <= snap_tolerance
        ]
        matches.sort(key=lambda polygon: polygon.area)
        polygon = next((item for item in matches if item.wkb not in used_polygons), None)
        if polygon is None:
            continue
        used_polygons.add(polygon.wkb)

        min_x, min_y, max_x, max_y = polygon.bounds
        vertices = [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
        repaired_boundary = bool(
            repair_union is not None
            and polygon.boundary.distance(repair_union) <= snap_tolerance
        )
        result.append({
            "name": room_label["name"],
            "area_sqm": round(polygon.area / 1_000_000, 2),
            "perimeter_m": round(polygon.length / 1000, 2),
            "vertices": vertices,
            "boundary_source": "wall_topology_repaired" if repaired_boundary else "wall_topology",
            "dimensions": {
                "width_mm": round(max_x - min_x),
                "height_mm": round(max_y - min_y),
                "width_m": round((max_x - min_x) / 1000, 3),
                "height_m": round((max_y - min_y) / 1000, 3),
            },
            "vertex_count": len(vertices),
            "confidence": 0.72 if repaired_boundary else 0.82,
        })

    oriented_lines = {"horizontal": [], "vertical": []}
    for index, line in enumerate(linework):
        start, end = line.coords[0], line.coords[-1]
        delta_x = abs(end[0] - start[0])
        delta_y = abs(end[1] - start[1])
        if delta_y <= max(3.0, delta_x * 0.02):
            oriented_lines["horizontal"].append((index, line))
        elif delta_x <= max(3.0, delta_y * 0.02):
            oriented_lines["vertical"].append((index, line))

    parallel_pairs = []
    gap_counts = {}
    for orientation, records in oriented_lines.items():
        axis = 0 if orientation == "horizontal" else 1
        fixed_axis = 1 - axis
        for record_index, (left_index, left) in enumerate(records):
            left_start, left_end = sorted((left.coords[0][axis], left.coords[-1][axis]))
            left_fixed = left.coords[0][fixed_axis]
            for right_index, right in records[record_index + 1:]:
                gap = abs(left_fixed - right.coords[0][fixed_axis])
                if not 80 <= gap <= 400:
                    continue
                right_start, right_end = sorted((right.coords[0][axis], right.coords[-1][axis]))
                overlap = min(left_end, right_end) - max(left_start, right_start)
                if overlap < min(left.length, right.length) * 0.4:
                    continue
                rounded_gap = round(gap / 10) * 10
                gap_counts[rounded_gap] = gap_counts.get(rounded_gap, 0) + 1
                parallel_pairs.append({
                    "gap": gap,
                    "left_index": left_index,
                    "right_index": right_index,
                    "left": left,
                    "right": right,
                    "orientation": orientation,
                })

    if not gap_counts:
        return result

    wall_thickness = max(gap_counts, key=gap_counts.get)
    if gap_counts[wall_thickness] < 8:
        return result

    thickness_tolerance = max(30.0, wall_thickness * 0.25)
    paired_indexes = {
        line_index
        for pair in parallel_pairs
        if abs(pair["gap"] - wall_thickness) <= thickness_tolerance
        for line_index in (pair["left_index"], pair["right_index"])
    }
    paired_lines = [line for index, line in enumerate(linework) if index in paired_indexes]
    if len(paired_lines) < 8:
        return result

    def pair_wall_polygon(pair):
        axis = 0 if pair["orientation"] == "horizontal" else 1
        fixed_axis = 1 - axis
        left = pair["left"]
        right = pair["right"]
        left_start, left_end = sorted((left.coords[0][axis], left.coords[-1][axis]))
        right_start, right_end = sorted((right.coords[0][axis], right.coords[-1][axis]))
        overlap_start = max(left_start, right_start)
        overlap_end = min(left_end, right_end)
        if overlap_end <= overlap_start:
            return None
        fixed_start, fixed_end = sorted((left.coords[0][fixed_axis], right.coords[0][fixed_axis]))
        if pair["orientation"] == "horizontal":
            return box(overlap_start, fixed_start, overlap_end, fixed_end)
        return box(fixed_start, overlap_start, fixed_end, overlap_end)

    confirmed_wall_pairs = [
        pair for pair in parallel_pairs
        if abs(pair["gap"] - wall_thickness) <= thickness_tolerance
    ]
    clean_confirmed_wall_pairs = [
        pair for pair in confirmed_wall_pairs
        if id(pair["left"]) not in furniture_suspect_ids
        and id(pair["right"]) not in furniture_suspect_ids
    ]
    clean_paired_ids = {
        id(line)
        for pair in clean_confirmed_wall_pairs
        for line in (pair["left"], pair["right"])
    }
    clean_paired_lines = [line for line in paired_lines if id(line) in clean_paired_ids]
    if len(clean_paired_lines) < 8:
        clean_paired_lines = paired_lines
        clean_confirmed_wall_pairs = confirmed_wall_pairs
    wall_polygons = [
        polygon
        for pair in clean_confirmed_wall_pairs
        for polygon in [pair_wall_polygon(pair)]
        if polygon is not None and polygon.area >= 20_000
    ]

    outer_candidates = []
    for polygon in raw_polygons:
        if not 20_000_000 <= polygon.area <= 1_000_000_000:
            continue
        contained_labels = sum(polygon.buffer(snap_tolerance).covers(label["pt"]) for label in room_labels)
        if contained_labels >= 2:
            outer_candidates.append((contained_labels, polygon.area, polygon))
    if not outer_candidates:
        return result

    _, _, outer_polygon = max(outer_candidates, key=lambda item: (item[0], item[1]))
    outer_polygon = type(outer_polygon)(outer_polygon.exterior)

    def polygon_parts(geometry):
        if geometry.geom_type == "Polygon":
            return [geometry]
        if hasattr(geometry, "geoms"):
            return [part for item in geometry.geoms for part in polygon_parts(item)]
        return []

    def extend_line(start, end, extension):
        length = math.dist(start, end)
        if length == 0:
            return None
        unit_x = (end[0] - start[0]) / length
        unit_y = (end[1] - start[1]) / length
        return LineString((
            (start[0] - unit_x * extension, start[1] - unit_y * extension),
            (end[0] + unit_x * extension, end[1] + unit_y * extension),
        ))

    wall_solids = unary_union(wall_polygons) if wall_polygons else None

    def build_door_separators():
        if wall_solids is None or wall_solids.is_empty:
            return []
        separators = []
        endpoint_tolerance = max(120.0, wall_thickness * 1.25)
        for guide in potential_door_guides:
            center_point = Point(guide["center"])
            if wall_solids.distance(center_point) > endpoint_tolerance:
                continue
            ranked_endpoints = sorted(
                guide["endpoints"],
                key=lambda endpoint: wall_solids.distance(Point(endpoint)),
            )
            closed_endpoint = ranked_endpoints[0]
            if wall_solids.distance(Point(closed_endpoint)) > endpoint_tolerance:
                continue
            separator = extend_line(
                guide["center"],
                closed_endpoint,
                max(80.0, wall_thickness * 0.75),
            )
            if separator is not None:
                separators.append(separator)

        return separators

    door_separators = build_door_separators()

    def split_at_doors(polygons):
        free_parts = polygons
        for separator in door_separators:
            split_parts = []
            for polygon in free_parts:
                try:
                    pieces = polygon_parts(split(polygon, separator))
                except Exception:
                    pieces = [polygon]
                split_parts.extend(pieces or [polygon])
            free_parts = split_parts
        return free_parts

    def build_inner_face_result():
        if wall_solids is None or wall_solids.is_empty:
            return []

        free_parts = split_at_doors(polygon_parts(outer_polygon.difference(wall_solids)))

        spaces = []
        for polygon in free_parts:
            if not 1_000_000 <= polygon.area <= 100_000_000:
                continue
            matching_labels = [label for label in room_labels if polygon.covers(label["pt"])]
            if len(matching_labels) != 1:
                continue
            compactness = 4 * math.pi * polygon.area / max(polygon.length ** 2, 1)
            if compactness < 0.015:
                continue
            label = matching_labels[0]
            min_x, min_y, max_x, max_y = polygon.bounds
            vertices = [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
            separated_at_door = any(polygon.boundary.intersects(separator) for separator in door_separators)
            spaces.append({
                "name": label["name"],
                "area_sqm": round(polygon.area / 1_000_000, 2),
                "perimeter_m": round(polygon.length / 1000, 2),
                "vertices": vertices,
                "boundary_source": (
                    "wall_inner_faces_door_split" if separated_at_door else "wall_inner_faces"
                ),
                "dimensions": {
                    "width_mm": round(max_x - min_x),
                    "height_mm": round(max_y - min_y),
                    "width_m": round((max_x - min_x) / 1000, 3),
                    "height_m": round((max_y - min_y) / 1000, 3),
                },
                "vertex_count": len(vertices),
                "confidence": 0.8 if separated_at_door else 0.76,
            })
        return spaces

    def build_mask_result(
        mask_linework,
        mask_paired_lines,
        source,
        closure_multiplier=3.0,
        confidence=0.68,
        use_label_envelope=False,
        use_local_door_partition=False,
    ):
        if not mask_linework or not mask_paired_lines:
            return []
        wall_seed_width = max(40.0, wall_thickness * 0.55)
        seed_mask = unary_union(mask_linework).buffer(
            wall_seed_width,
            cap_style="flat",
            join_style="mitre",
        )
        seed_parts = list(seed_mask.geoms) if hasattr(seed_mask, "geoms") else [seed_mask]
        paired_mask = unary_union(mask_paired_lines).buffer(
            wall_thickness * 0.65,
            cap_style="flat",
            join_style="mitre",
        )
        wall_parts = [part for part in seed_parts if part.intersects(paired_mask)]
        if not wall_parts:
            return []
        wall_mask = unary_union(wall_parts)
        door_closure = (
            max(60.0, min(180.0, wall_thickness * 0.75))
            if use_local_door_partition
            else max(400.0, min(1000.0, wall_thickness * closure_multiplier))
        )
        closed_walls = wall_mask.buffer(door_closure, join_style="mitre").buffer(
            -door_closure,
            join_style="mitre",
        )
        free_boundary = outer_polygon
        if use_label_envelope:
            label_x = [label["pt"].x for label in room_labels]
            label_y = [label["pt"].y for label in room_labels]
            margin = max(3000.0, wall_thickness * 15)
            free_boundary = box(
                min(label_x) - margin,
                min(label_y) - margin,
                max(label_x) + margin,
                max(label_y) + margin,
            )
        free_space = free_boundary.difference(closed_walls)
        free_parts = polygon_parts(free_space)
        if use_local_door_partition:
            free_parts = split_at_doors(free_parts)

        candidate_parts = [
            polygon for polygon in free_parts
            if polygon.geom_type == "Polygon" and 1_000_000 <= polygon.area <= 100_000_000
        ]
        assignments = {}
        assigned_label_ids = set()
        ambiguous_label_ids = set()
        for part_index, polygon in enumerate(candidate_parts):
            matching_labels = [label for label in room_labels if polygon.covers(label["pt"])]
            if len(matching_labels) == 1:
                assignments[part_index] = (matching_labels[0], False)
                assigned_label_ids.add(id(matching_labels[0]))
            elif len(matching_labels) > 1:
                ambiguous_label_ids.update(id(label) for label in matching_labels)

        projection_limit = max(500.0, min(900.0, wall_thickness * 3.5))
        projection_candidates = []
        for label in room_labels:
            if id(label) in assigned_label_ids or id(label) in ambiguous_label_ids:
                continue
            for part_index, polygon in enumerate(candidate_parts):
                if part_index in assignments:
                    continue
                distance = polygon.distance(label["pt"])
                if distance <= projection_limit:
                    projection_candidates.append((distance, part_index, label))
        for _, part_index, label in sorted(projection_candidates, key=lambda item: item[0]):
            if part_index in assignments or id(label) in assigned_label_ids:
                continue
            assignments[part_index] = (label, True)
            assigned_label_ids.add(id(label))

        spaces = []
        for part_index, (label, projected) in assignments.items():
            polygon = candidate_parts[part_index]
            inner_face_adjusted = False
            if use_local_door_partition and wall_solids is not None and not wall_solids.is_empty:
                expansion = max(40.0, wall_thickness * 0.55)
                available_floor = free_boundary.difference(wall_solids)
                adjusted_parts = polygon_parts(
                    polygon.buffer(expansion, join_style="mitre").intersection(available_floor)
                )
                adjusted_matches = [part for part in adjusted_parts if part.covers(label["pt"])]
                if adjusted_matches:
                    polygon = max(adjusted_matches, key=lambda part: part.area)
                    inner_face_adjusted = True
            min_x, min_y, max_x, max_y = polygon.bounds
            vertices = [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
            spaces.append({
                "name": label["name"],
                "area_sqm": round(polygon.area / 1_000_000, 2),
                "perimeter_m": round(polygon.length / 1000, 2),
                "vertices": vertices,
                "boundary_source": (
                    f"{source}_label_projected" if projected
                    else f"{source}_inner_face_adjusted" if inner_face_adjusted
                    else source
                ),
                "dimensions": {
                    "width_mm": round(max_x - min_x),
                    "height_mm": round(max_y - min_y),
                    "width_m": round((max_x - min_x) / 1000, 3),
                    "height_m": round((max_y - min_y) / 1000, 3),
                },
                "vertex_count": len(vertices),
                "confidence": max(confidence - 0.06, 0.5) if projected else confidence,
            })
        return spaces

    inner_face_result = build_inner_face_result()
    primary_result = build_mask_result(
        linework,
        clean_paired_lines,
        "wall_mask_repaired",
        confidence=0.76,
        use_local_door_partition=True,
    )
    legacy_primary_result = build_mask_result(
        linework,
        paired_lines,
        "wall_mask_repaired",
    )
    zero_linework = segments_by_layer.get("0", [])
    zero_keys = {line.wkb for line in zero_linework}
    zero_paired_lines = [line for line in clean_paired_lines if line.wkb in zero_keys]
    zero_result = build_mask_result(
        zero_linework,
        zero_paired_lines,
        "wall_mask_layer0_repaired",
        confidence=0.72,
        use_local_door_partition=True,
    )
    strong_result = build_mask_result(
        zero_linework,
        zero_paired_lines,
        "wall_mask_strong_repaired",
        closure_multiplier=4.5,
        confidence=0.58,
    )
    envelope_result = build_mask_result(
        zero_linework,
        zero_paired_lines,
        "wall_mask_envelope_repaired",
        closure_multiplier=4.5,
        confidence=0.52,
        use_label_envelope=True,
    )

    clean_names = {
        space["name"]
        for candidates in (
            inner_face_result,
            primary_result,
            zero_result,
            strong_result,
            envelope_result,
        )
        for space in candidates
    }
    for space in legacy_primary_result:
        if space["name"] not in clean_names:
            space["boundary_source"] = "wall_mask_furniture_fallback"
            space["confidence"] = min(space["confidence"], 0.5)

    merged_result = {space["name"]: space for space in inner_face_result}
    for space in [
        *primary_result,
        *legacy_primary_result,
        *zero_result,
        *strong_result,
        *envelope_result,
    ]:
        merged_result.setdefault(space["name"], space)
    mask_result = list(merged_result.values())
    return mask_result if len(mask_result) > len(result) else result


# 旧版尺寸推算保留作历史对照，不再进入自动解析流程。

def _calc_rooms_from_lines_legacy(msp, room_labels, dimensions) -> list:
    """
    当DXF墙体用LINE线段绘制（无LWPOLYLINE闭合多边形）时，
    通过墙体线位置 + 尺寸标注值推算每个房间的近似尺寸和面积。
    """
    import math

    # 1. 提取墙体LINE线段
    wall_layers = {"000-墙体1", "0", "建筑墙体", "墙体"}
    segments = []
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if e.dxf.layer not in wall_layers:
            continue
        s, ep = e.dxf.start, e.dxf.end
        dx, dy = ep.x - s.x, ep.y - s.y
        length = math.sqrt(dx*dx + dy*dy)
        if length > 200:  # 过滤过短线段
            segments.append({
                "x1": s.x, "y1": s.y, "x2": ep.x, "y2": ep.y,
                "length": length,
            })

    # 2. 提取尺寸标注值
    h_dims, v_dims = [], []
    for d in dimensions:
        val = d.get("text", "")
        try:
            v = float(val) if val else 0
        except ValueError:
            v = 0
        pos = d["position"]
        angle = d.get("angle", 0)
        # 判断水平还是垂直：根据标注线和角度
        if -45 < angle < 45 or angle > 135 or angle < -135:
            h_dims.append({"val_mm": v, "x": pos[0], "y": pos[1]})
        else:
            v_dims.append({"val_mm": v, "x": pos[0], "y": pos[1]})

    # 3. 对每个房间标签，估算尺寸
    def pt_to_seg_dist(px, py, seg):
        """点到线段的最短距离"""
        x1, y1, x2, y2 = seg["x1"], seg["y1"], seg["x2"], seg["y2"]
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        t = ((px - x1)*dx + (py - y1)*dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        nx, ny = x1 + t*dx, y1 + t*dy
        return math.sqrt((px - nx)**2 + (py - ny)**2)

    def find_wall_dir(px, py, segs, dx, dy, max_d=15000, step=100):
        """从px,py出发沿(dx,dy)方向找最近的墙"""
        for d in range(step, max_d, step):
            tx, ty = px + dx*d, py + dy*d
            for s in segs:
                if pt_to_seg_dist(tx, ty, s) < 150:  # 15cm内算碰到墙
                    return d
        return max_d

    def nearest_dim_value(px, py, dims, is_horizontal, max_dist=5000):
        """找最近的尺寸标注值"""
        best_val = 0
        best_dist = max_dist
        for d in dims:
            dist = math.sqrt((px - d["x"])**2 + (py - d["y"])**2)
            if dist < best_dist:
                best_val = d["val_mm"]
                best_dist = dist
        return best_val

    # 把尺寸标注按所在区域（Y轴范围）分组
    # 水平标注通常在墙体外侧，用Y坐标区分不同行的标注
    def group_by_y(dims, threshold=3000):
        groups = []
        used = set()
        for i, d1 in enumerate(dims):
            if i in used:
                continue
            group = [d1]
            used.add(i)
            for j, d2 in enumerate(dims):
                if j not in used and abs(d1["y"] - d2["y"]) < threshold:
                    group.append(d2)
                    used.add(j)
            # 取该组中位Y
            mid_y = sorted(g["y"] for g in group)[len(group)//2]
            # 按X排序
            group.sort(key=lambda g: g["x"])
            groups.append({"y": mid_y, "items": group})
        return groups

    h_groups = group_by_y(h_dims)
    v_groups = group_by_y(v_dims)

    # 按Y坐标（房间行）匹配水平尺寸组
    # 同时计算每行的总宽度和房间数
    def pick_h_group(room_y, h_groups, max_dy=3000):
        best = None
        best_dy = max_dy
        for g in h_groups:
            dy = abs(room_y - g["y"])
            if dy < best_dy:
                best = g
                best_dy = dy
        return best

    result = []
    # 按行处理房间 — 用Y坐标最大间隔自动分行
    rooms_sorted = sorted(room_labels, key=lambda rl: rl["pt"].y, reverse=True)

    # 计算相邻房间的Y间隔，取最大的分隔点作为分行
    y_gaps = []
    for i in range(len(rooms_sorted) - 1):
        gap = abs(rooms_sorted[i]["pt"].y - rooms_sorted[i+1]["pt"].y)
        y_gaps.append((gap, i))
    y_gaps.sort(key=lambda x: -x[0])

    # 取所有>1200mm的间隔作为分行点
    split_indices = sorted({idx for gap, idx in y_gaps if gap > 1200})

    row_map = []
    start = 0
    for si in split_indices:
        row_map.append(rooms_sorted[start:si+1])
        start = si + 1
    if start < len(rooms_sorted):
        row_map.append(rooms_sorted[start:])

    # 找总建筑宽度（所有水平尺寸最大值）
    total_w_mm = max((item["val_mm"] for g in h_groups for item in g["items"]), default=14600)
    # 垂直尺寸按X区域匹配每行的高度
    v_dims_by_x = {}
    for item in v_dims:
        nearby_key = round(item["x"] / 1000)
        if nearby_key not in v_dims_by_x or abs(item["val_mm"] - 3000) < abs(v_dims_by_x[nearby_key]["val_mm"] - 3000):
            v_dims_by_x[nearby_key] = item

    result = []
    for row_rooms in row_map:
        row_rooms.sort(key=lambda r: r["pt"].x)
        n = len(row_rooms)
        x_min = min(r["pt"].x for r in row_rooms)
        x_max = max(r["pt"].x for r in row_rooms)
        x_span = max(x_max - x_min, 1)

        # 找该行的垂直高度：取最近的垂直标注
        row_h_mm = 3000  # 默认3m
        for x_key in sorted(v_dims_by_x.keys()):
            if abs(x_key*1000 - (x_min + x_max)/2) < 5000:
                if 2000 < v_dims_by_x[x_key]["val_mm"] < 7000:
                    row_h_mm = v_dims_by_x[x_key]["val_mm"]
                    break

        for i, r in enumerate(row_rooms):
            if n == 1:
                w_mm = min(total_w_mm * 0.4, 6000)  # 单房间最多6m
            elif i == 0:
                nxt = row_rooms[1]["pt"].x
                ratio = (nxt - r["pt"].x) / x_span
                w_mm = total_w_mm * ratio * 0.9
            elif i == n - 1:
                prev = row_rooms[i-1]["pt"].x
                ratio = (r["pt"].x - prev) / x_span
                w_mm = total_w_mm * ratio * 0.9
            else:
                nxt = row_rooms[i+1]["pt"].x
                prev = row_rooms[i-1]["pt"].x
                ratio = ((nxt - prev) / 2) / x_span
                w_mm = total_w_mm * ratio * 0.9

            w_mm = max(min(w_mm, 12000), 1200)  # 限制1.2m~12m
            h_mm = row_h_mm
            w_m = round(w_mm / 1000, 2)
            h_m = round(h_mm / 1000, 2)
            area = round(w_m * h_m, 2)
            center_x = float(r["pt"].x)
            center_y = float(r["pt"].y)
            half_width = float(w_mm) / 2
            half_height = float(h_mm) / 2
            vertices = [
                [center_x - half_width, center_y - half_height],
                [center_x + half_width, center_y - half_height],
                [center_x + half_width, center_y + half_height],
                [center_x - half_width, center_y + half_height],
            ]
            result.append({
                "name": r["name"],
                "area_sqm": area,
                "perimeter_m": round(2 * (w_m + h_m), 2),
                "vertices": vertices,
                "boundary_source": "wall_dimension_estimate",
                "dimensions": {"width_mm": round(w_mm), "height_mm": round(h_mm), "width_m": w_m, "height_m": h_m},
                "vertex_count": 4, "confidence": 0.6,
            })

    return result


CAD_IMAGE_PROMPT = """你是一位专业的建筑CAD图纸分析专家。请仔细分析这张CAD户型图，提取以下信息：

1. **房间识别**：识别图中所有的房间/空间，包括客厅、餐厅、主卧、次卧、厨房、卫生间、阳台、书房、玄关、走廊等
2. **尺寸提取**：读取图中标注的尺寸数字（通常在墙线旁边或轴线上），单位为毫米(mm)
3. **面积计算**：根据标注的尺寸，计算每个房间的大致面积（平方米）
4. **整体信息**：户型总面积、几室几厅几卫、朝向（如能识别）

请以 JSON 格式返回：
{
  "spaces": [
    {"name": "房间名称", "width_mm": 开间, "depth_mm": 进深, "area_sqm": 面积, "confidence": 0.95}
  ],
  "total_area_sqm": 总面积,
  "layout": "几室几厅几卫",
  "orientation": "朝向",
  "notes": "补充说明"
}

只返回 JSON，不要包含其他任何文字。"""


def _parse_cad_image(image_path: str, source_type: str = "CAD图片") -> dict:
    """使用 Ollama/LLaVA 本地模型识别 CAD 图纸"""
    try:
        img_b64 = _image_to_ollama_b64(image_path)
        raw_text = _ollama_chat(CAD_IMAGE_PROMPT, img_b64)

        json_match = re.search(r'\{[\s\S]*\}', raw_text)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {"error": "无法解析模型返回", "raw": raw_text}

        raw_spaces = parsed.get("spaces", [])
        result_spaces = []
        for s in raw_spaces:
            area = s.get("area_sqm", 0)
            w = s.get("width_mm", 0)
            d = s.get("depth_mm", 0)
            if not area and w and d:
                area = round((w * d) / 1_000_000, 2)
            result_spaces.append({
                "name": s.get("name", "未命名空间"),
                "area_sqm": area,
                "perimeter_m": round(((w or 0) + (d or 0)) * 2 / 1000, 2) if w and d else 0,
                "dimensions": {
                    "width_mm": w,
                    "height_mm": d,
                    "width_m": round((w or 0) / 1000, 3),
                    "height_m": round((d or 0) / 1000, 3),
                },
                "confidence": s.get("confidence", 0.8),
            })

        return {
            "spaces": result_spaces,
            "total_area_sqm": parsed.get("total_area_sqm"),
            "layout": parsed.get("layout", ""),
            "orientation": parsed.get("orientation", ""),
            "notes": parsed.get("notes", ""),
            "parse_method": source_type,
            "raw_text": raw_text[:1000],
        }

    except Exception as e:
        return {
            "error": f"CAD 图片识别失败: {str(e)}",
            "spaces": [],
            "parse_method": source_type,
        }


def _parse_effect_image(image_path: str) -> dict:
    """使用 Ollama/LLaVA 识别效果图中的空间和材质（结构化输出）"""
    try:
        from image_recognizer import STRUCTURED_PROMPT, _image_to_base64, _extract_json, _normalize_result, _ollama_chat

        img_b64 = _image_to_base64(image_path)
        raw_text = _ollama_chat(STRUCTURED_PROMPT, img_b64, model="llava:7b")
        parsed = _extract_json(raw_text)

        if parsed:
            structured = _normalize_result(parsed)
            return {
                "success": True,
                "spaces": [{
                    "type": structured["space_type"],
                    "materials": {
                        "floor": structured["floor_material"],
                        "wall": structured["wall_material"],
                        "ceiling": structured["ceiling_material"],
                    },
                    "description": structured["remark"],
                }],
                "overall_style": structured["decor_style"],
                "structured": structured,
                "raw_response": raw_text[:2000],
            }
        else:
            return {
                "success": False,
                "error": "LLaVA返回非标准JSON格式",
                "spaces": [],
                "overall_style": "未知",
                "raw_response": raw_text[:1000],
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"效果图识别失败: {str(e)}",
            "spaces": [],
            "overall_style": "未知",
        }


def _parse_cad_pdf(pdf_path: str) -> dict:
    """提取 PDF 中的页面为图片，用 Ollama/LLaVA 识别"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {
            "error": "PDF 识别需要安装 PyMuPDF: pip install PyMuPDF",
            "spaces": [],
            "parse_method": "PDF→图片→视觉识别",
        }

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        temp_images = []

        for page_num in range(min(total_pages, 5)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            img_path = pdf_path + f"_page{page_num}.png"
            pix.save(img_path)
            temp_images.append((page_num, img_path))

        doc.close()

        all_spaces = []
        notes_list = []
        total_area = None
        layout = ""

        for page_num, img_path in temp_images:
            result = _parse_cad_image(img_path, source_type=f"PDF第{page_num + 1}页")
            all_spaces.extend(result.get("spaces", []))
            if result.get("total_area_sqm"):
                total_area = result["total_area_sqm"]
            if result.get("layout") and not layout:
                layout = result["layout"]
            if result.get("notes"):
                notes_list.append(f"第{page_num + 1}页: {result['notes']}")

            try:
                os.remove(img_path)
            except Exception:
                pass

        seen = {}
        for s in all_spaces:
            name = s.get("name", "")
            if name == "未命名空间":
                continue
            if name not in seen or s.get("confidence", 0) > seen[name].get("confidence", 0):
                seen[name] = s

        return {
            "spaces": list(seen.values()),
            "total_area_sqm": total_area,
            "layout": layout,
            "notes": "; ".join(notes_list) if notes_list else "",
            "parse_method": f"PDF→图片→视觉识别 (共{total_pages}页)",
            "total_pages": total_pages,
        }

    except Exception as e:
        return {
            "error": f"PDF 解析失败: {str(e)}",
            "spaces": [],
            "parse_method": "PDF→图片→视觉识别",
        }


def convert_dwg_to_dxf(input_path: str, output_dir: str = None) -> Optional[str]:
    import subprocess

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    base = os.path.splitext(os.path.basename(input_path))[0]

    attempts = [
        {"cmd": ["dwg2dxf", input_path, "-o", os.path.join(output_dir, f"{base}_converted.dxf")], "expected_output": os.path.join(output_dir, f"{base}_converted.dxf")},
        {"cmd": ["ODAFileConverter", input_path, output_dir, "ACAD2018", "DXF", "0", "1"], "expected_output": os.path.join(output_dir, f"{base}.dxf")},
    ]

    for attempt in attempts:
        try:
            result = subprocess.run(attempt["cmd"], capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(attempt["expected_output"]):
                return attempt["expected_output"]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None
