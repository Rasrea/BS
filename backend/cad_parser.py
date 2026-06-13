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


# == DXF 矢量解析（保持原有逻辑） ==

def _parse_dxf(file_path: str) -> dict:
    import ezdxf
    from shapely.geometry import Polygon, Point

    try:
        doc = ezdxf.readfile(file_path)
    except Exception as e:
        return {"error": f"DXF 文件读取失败: {str(e)}", "spaces": [], "parse_method": "dxf矢量解析"}

    msp = doc.modelspace()

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
        t = entity.plain_text().strip()
        if t:
            texts.append({
                "text": t,
                "position": (entity.dxf.insert.x, entity.dxf.insert.y),
                "layer": entity.dxf.layer,
                "height": 4.0,
            })

    dimensions = []
    for entity in msp.query("DIMENSION"):
        try:
            dim_text = ""
            if hasattr(entity.dxf, 'text') and entity.dxf.text:
                dim_text = entity.dxf.text
            elif hasattr(entity, 'get_measurement'):
                dim_text = str(round(entity.get_measurement()))
            def_point = entity.dxf.defpoint2
            angle = entity.dxf.angle if hasattr(entity.dxf, 'angle') else 0
            dimensions.append({
                "text": dim_text,
                "position": (def_point.x, def_point.y),
                "angle": angle,
                "layer": entity.dxf.layer,
            })
        except Exception:
            pass

    room_keywords = [
        "客厅", "餐厅", "主卧", "次卧", "卧室", "厨房",
        "卫生间", "厕所", "浴室", "阳台", "书房", "衣帽间",
        "玄关", "走廊", "过道", "储藏室", "儿童房", "老人房",
        "living", "dining", "bedroom", "kitchen", "bathroom",
        "balcony", "study", "corridor", "living room",
        "客餐厅", "主卫", "次卫", "公卫",
        "家政", "储物", "多功能", "棋牌", "影音",
        "门厅", "西厨", "中厨", "阳光房",
    ]

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
    ]

    def _first_line(text: str) -> str:
        """多行文字合并后取首行（处理DXF中\"客\\n厅\"之类的断行）"""
        # 先合并被换行符打断的短行：如果每段很短（≤2字符），合并回来
        parts = text.split("\n")
        if len(parts) >= 2 and all(0 < len(p.strip()) <= 2 for p in parts if p.strip()):
            return "".join(p.strip() for p in parts)
        return parts[0].strip()

    # ── 构建所有候选文字标签（先关键词过滤，保留全部候选用于兜底）──
    ROOM_TEXT_LAYERS = {"000-墙体1", "0"}

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
            # 短文本但含中文字符，可能为房间名（如"茶室""棋牌室"等不在关键词列表的）
            has_cjk = any('\u4e00' <= c <= '\u9fff' for c in first)
            if has_cjk:
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

    # 按面积降序排列多边形，大空间优先匹配房间名
    valid_polylines.sort(key=lambda vp: vp["polygon"].area, reverse=True)

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

    return {
        "spaces": result_spaces,
        "total_polylines": len(polylines),
        "total_texts": len(texts),
        "total_dimensions": len(dimensions),
        "parse_method": "dxf矢量解析",
    }


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
