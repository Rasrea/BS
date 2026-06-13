"""
效果图识别模块 v2.0

核心改造：
1. 强制结构化JSON输出（space_type, wall_material, floor_material, ceiling_material, decor_style, remark）
2. 支持运行时切换模型（默认 llava:7b，可选 qwen2.5:7b）
3. 健壮的JSON提取与异常降级
4. 保留原有调用规则：单图同步、无并发、受任务锁控制
"""

import os
import base64
import json
import re
import requests
import logging

logger = logging.getLogger(__name__)

# 固定结构化输出 Prompt
STRUCTURED_PROMPT = """你是一位专业的室内装修识别专家。请识别这张家装效果图中的信息，**严格按照以下JSON格式返回，不要输出任何多余文字**。

{
  "space_type": "空间名称（如客厅、卧室、厨房、卫生间、餐厅、阳台、书房等）",
  "wall_material": "墙面材质（如乳胶漆、墙布/壁纸、瓷砖、木饰面、护墙板、石材、玻璃、硅藻泥等）",
  "floor_material": "地面材质（如木地板、瓷砖、大理石、地毯、水磨石、环氧地坪等）",
  "ceiling_material": "顶面/吊顶材质（如石膏板吊顶、铝扣板吊顶、平顶、裸顶、木吊顶、无吊顶等）",
  "decor_style": "装修风格（如现代简约、北欧、新中式、轻奢、工业风、美式、日式、欧式等）",
  "remark": "补充说明——如特殊工艺、特色装饰、定制家具等，若无则填空字符串"
}

要求：
- 每个字段必须填写，未知则填"未知"
- space_type 只填一个主要空间类型
- 只返回JSON，不要包含```json、不要任何解释"""


def _ollama_chat(prompt: str, image_base64: str, model: str = "llava:7b", timeout: int = 120) -> str:
    """调用 Ollama 本地模型进行图像识别"""
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64]
            }
        ],
        "stream": False
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("message", {}).get("content", "")


def _image_to_base64(image_path: str) -> str:
    """将图片转为 base64 格式"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _extract_json(raw_text: str) -> dict:
    """
    从模型返回文本中健壮提取JSON。
    策略：
    1. 尝试直接整体解析
    2. 用正则 {…} 提取首块
    3. 修复常见格式错误（末尾逗号、单引号等）
    4. 全部失败返回 None
    """
    if not raw_text:
        return None

    # 策略1：整体解析
    text = raw_text.strip()
    # 去掉可能的 ```json 和 ``` 包裹
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    for attempt in [
        lambda t: json.loads(t),
        lambda t: json.loads(re.search(r'\{[\s\S]*\}', t).group()),
        lambda t: json.loads(re.sub(r',\s*}', '}', re.search(r'\{[\s\S]*\}', t).group())),  # 修复末尾逗号
        lambda t: json.loads(re.sub(r"'", '"', re.search(r'\{[\s\S]*\}', t).group())),     # 单引号→双引号
        lambda t: json.loads(re.sub(r',\s*}', '}', re.sub(r"'", '"', re.search(r'\{[\s\S]*\}', t).group()))),
    ]:
        try:
            return attempt(text)
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def _normalize_result(parsed: dict) -> dict:
    """
    归一化结构化结果，确保6个字段都存在且类型正确。
    """
    fields = {
        "space_type": str,
        "wall_material": str,
        "floor_material": str,
        "ceiling_material": str,
        "decor_style": str,
        "remark": str,
    }
    result = {}
    for key, typ in fields.items():
        val = parsed.get(key, "")
        # 兼容旧格式：可能用不同key名
        if not val:
            aliases = {
                "space_type": ["space", "type", "room_type", "room"],
                "wall_material": ["wall", "wall_mat"],
                "floor_material": ["floor", "floor_mat"],
                "ceiling_material": ["ceiling", "ceiling_mat", "ceiling_type", "ceiling"],
                "decor_style": ["style", "overall_style", "decoration_style"],
                "remark": ["notes", "note", "description", "other"],
            }
            for alias in aliases.get(key, []):
                val = parsed.get(alias, "")
                if val:
                    break
        if not isinstance(val, typ):
            try:
                val = str(val)
            except Exception:
                val = ""
        result[key] = val.strip() if val else ""
    return result


def recognize_image(image_path: str, model: str = "llava:7b") -> dict:
    """
    识别单张效果图，返回结构化数据。

    返回格式：
    {
        "success": bool,
        "structured": {            # 结构化字段
            "space_type": "...",
            "wall_material": "...",
            "floor_material": "...",
            "ceiling_material": "...",
            "decor_style": "...",
            "remark": "..."
        },
        "raw_response": str,       # 原始模型输出
        "model_used": str,         # 本调用使用的模型
        "error": str,              # 出错时填充
    }
    """
    try:
        img_b64 = _image_to_base64(image_path)
        raw_text = _ollama_chat(STRUCTURED_PROMPT, img_b64, model=model)

        parsed = _extract_json(raw_text)

        if parsed:
            return {
                "success": True,
                "structured": _normalize_result(parsed),
                "raw_response": raw_text[:2000],
                "model_used": model,
                "error": "",
            }
        else:
            # JSON 解析失败，尝试从文本中提取关键信息
            return {
                "success": False,
                "structured": _normalize_result({
                    "space_type": "",
                    "wall_material": "",
                    "floor_material": "",
                    "ceiling_material": "",
                    "decor_style": "",
                    "remark": f"模型返回非标准格式，原始文本: {raw_text[:500]}",
                }),
                "raw_response": raw_text[:2000],
                "model_used": model,
                "error": "JSON解析失败，返回文本非标准格式，请人工核实",
            }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "structured": _normalize_result({}),
            "raw_response": "",
            "model_used": model,
            "error": f"模型 {model} 调用超时（120s）",
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "structured": _normalize_result({}),
            "raw_response": "",
            "model_used": model,
            "error": f"Ollama 服务未响应（模型: {model}）",
        }
    except Exception as e:
        return {
            "success": False,
            "structured": _normalize_result({}),
            "raw_response": "",
            "model_used": model,
            "error": f"识别异常: {str(e)}",
        }


def recognize_with_fallback(image_path: str, model: str = "llava:7b") -> dict:
    """
    识别效果图（对外接口，与旧版签名兼容）。
    新增 model 参数支持运行时切换。
    """
    result = recognize_image(image_path, model=model)
    return result
