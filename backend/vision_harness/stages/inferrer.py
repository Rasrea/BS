"""
BuildSight 视觉识别 Harness — 模型推理层
============================================
封装 Ollama / DashScope API 调用，隔离模型通信细节。

职责：
1. 发送图片+Prompt → Ollama
2. 返回模型原始文本
3. 异常处理（超时/断连）
4. 不关注业务逻辑
"""

import json
import re
import logging
import requests
import base64

from vision_harness.config import (
    OLLAMA_BASE_URL,
    OLLAMA_API_CHAT,
    OLLAMA_TIMEOUT,
    OLLAMA_TEMPERATURE,
    DEFAULT_MODEL,
    # 导入云百炼配置
    DASHSCOPE_BASE_URL,
    DASHSCOPE_API_CHAT,
    DASHSCOPE_API_TOKEN,
    DASHSCOPE_MODEL,  # 目前该值冗余
)
from vision_harness.material_library import (
    SPACE_TYPES, WALL_MATERIALS, FLOOR_MATERIALS, CEILING_MATERIALS,
    SPACE_VISUAL_GUIDE, WALL_MATERIAL_VISUAL_GUIDE, FLOOR_MATERIAL_VISUAL_GUIDE, CEILING_MATERIAL_VISUAL_GUIDE
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# Prompt 构建
# ═══════════════════════════════════════════════

def build_full_prompt() -> str:
    """构建全图结构化识别 Prompt（含枚举约束）"""
    return f"""你是一位专业的室内装修材料识别专家。请识别这张家装效果图，**仅提取以下4项信息**，所有取值必须从下方给定列表中**严格选择**，禁止自行编造、造词、拼写错误。

▼ 可识别的空间类型（仅选其一）：
{SPACE_TYPES}

▼ 可识别的墙面材质（仅选其一）：
{WALL_MATERIALS}

▼ 可识别的地面材质（仅选其一）：
{FLOOR_MATERIALS}

▼ 可识别的顶面材质（仅选其一）：
{CEILING_MATERIALS}

{''.join([SPACE_VISUAL_GUIDE, WALL_MATERIAL_VISUAL_GUIDE, FLOOR_MATERIAL_VISUAL_GUIDE, CEILING_MATERIAL_VISUAL_GUIDE])}

要求：
1. 所有字段必须从上方列表中精确选择名称，禁止造词、改字、写错别字
2. 如果图片中的材质不在列表内，选最接近的，不要填"未知"
3. 输出严格JSON格式，字段固定如下，不要包含任何多余文字

示例1：一张现代客厅效果图
输出：{{"space_type": "客厅", "wall_material": "乳胶漆", "floor_material": "地砖", "ceiling_material": "石膏板吊顶", "decor_style": "现代简约", "remark": ""}}

示例2：一张卧室效果图
输出：{{"space_type": "卧室", "wall_material": "墙布", "floor_material": "木地板", "ceiling_material": "玻璃顶", "decor_style": "轻奢", "remark": ""}}

{{{{
  "space_type": "<从空间类型列表中选择>",
  "wall_material": "<从墙面材质列表中选择>",
  "floor_material": "<从地面材质列表中选择>",
  "ceiling_material": "<从顶面材质列表中选择>",
  "decor_style": "<装修风格，自由填写>",
  "remark": "<无特殊说明则填空字符串>"
}}}}

只返回JSON，不要包含```json、不要任何解释、不要任何多余文字。"""


def build_crop_prompt(field: str) -> str:
    """构建裁剪区域单字段识别 Prompt"""
    prompts = {
        "wall_material": f"""你是室内装修材料识别专家。请仔细分析这张**墙面局部图**，识别墙面材质。

{''.join([WALL_MATERIAL_VISUAL_GUIDE])}

▼ 可选墙面材质（严格从中选择，禁止编造）：
{WALL_MATERIALS}

输出JSON（只返回JSON，不要多余文字）：
{{{{"wall_material": "<从上面列表中选择>"}}}}""",

        "floor_material": f"""你是室内装修材料识别专家。请仔细分析这张**地面局部图**，识别地面材质。

{''.join([FLOOR_MATERIAL_VISUAL_GUIDE])}

▼ 可选地面材质（严格从中选择，禁止编造）：
{FLOOR_MATERIALS}

输出JSON（只返回JSON，不要多余文字）：
{{{{"floor_material": "<从上面列表中选择>"}}}}""",

        "ceiling_material": f"""你是室内装修材料识别专家。请仔细分析这张**顶面/吊顶局部图**，识别顶面材质。

{''.join([CEILING_MATERIAL_VISUAL_GUIDE])}

▼ 可选顶面材质（严格从中选择，禁止编造）：
{CEILING_MATERIALS}

输出JSON（只返回JSON，不要多余文字）：
{{{{"ceiling_material": "<从上面列表中选择>"}}}}""",

        "full": f"""你是一位专业的室内装修材料识别专家。请仔细分析这张**家装效果图**，识别的空间类型。

{''.join([SPACE_VISUAL_GUIDE])}
  
▼ 可选空间类型（严格从中选择，禁止编造）：
{SPACE_TYPES}

输出JSON（只返回JSON，不要多余文字）：
{{{{"space_type": "<从上面列表中选择>"}}}}"""
    }
    return prompts.get(field, "")


# ═══════════════════════════════════════════════
# Ollama 通信
# ═══════════════════════════════════════════════

class ModelInferrer:
    """
    模型推理器。

    封装 Ollama /api/chat 调用，支持全图和裁剪图推理。
    调用者只需要提供 prompt + image_base64 + model_name。
    """

    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or OLLAMA_BASE_URL
        self.chat_url = self.base_url + OLLAMA_API_CHAT
        self.timeout = timeout or OLLAMA_TIMEOUT
        self._full_prompt: str | None = None
        self._session = requests.Session()
        self._custom_model_config: dict | None = None

    def set_custom_model_config(self, api_base_url: str = "", api_token: str = "",
                                api_format: str = "openai"):
        """设置自定义模型的 API 配置（用于覆盖默认环境变量）"""
        self._custom_model_config = {
            "api_base_url": api_base_url,
            "api_token": api_token,
            "api_format": api_format or "openai",
        }

    @property
    def full_prompt(self) -> str:
        """全图Prompt（惰性初始化，保证枚举列表是最新的）"""
        if self._full_prompt is None:
            self._full_prompt = build_full_prompt()
        return self._full_prompt

    def infer(self, prompt: str, image_base64: str, model: str, model_type: str = None) -> str:
        """
        调用模型推理（自动识别 Ollama / Cloud）。

        参数:
            prompt: 推理提示词
            image_base64: 图片 base64 编码
            model: 模型名称 (例如: 'qwen-vl-plus' 或 'llava:7b')
            model_type: 模型类型 ('cloud' 或 'local')，优先级高于 model 前缀判断

        返回:
            模型原始输出文本
        """
        # 决策逻辑：优先使用显式传入的 model_type，其次兼容旧版的前缀判断
        is_cloud = False
        if model_type == "cloud":
            is_cloud = True
        elif model_type == "local":
            is_cloud = False
        elif model.startswith("dashscope:"):
            is_cloud = True
            model = model.replace("dashscope:", "")

        # ===== 情况 1: 云端模型调用 =====
        if is_cloud:
            base_url = DASHSCOPE_BASE_URL
            api_token = DASHSCOPE_API_TOKEN
            api_format = "openai"

            if self._custom_model_config:
                base_url = self._custom_model_config.get("api_base_url", base_url)
                api_token = self._custom_model_config.get("api_token", api_token)
                api_format = self._custom_model_config.get("api_format", "openai")

            if not api_token:
                raise ValueError("云端模型 API Token 未配置，请在自定义模型配置中设置。")
            if not base_url:
                raise ValueError("云端模型 API Base URL 未配置。")

            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
            image_url_data = f"data:image/jpeg;base64,{image_base64}"

            payload = self._build_cloud_payload(api_format, model, prompt, image_url_data)

            logger.info(f"Calling Cloud API [{api_format}]: {model} @ {base_url}")
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()

            data = resp.json()
            return self._parse_cloud_response(api_format, data)

        # ===== 情况 2: 本地 Ollama 模型调用 =====
        else:
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }],
                "stream": False,
                "options": {
                    "temperature": OLLAMA_TEMPERATURE,
                },
            }

            logger.info(f"Calling Local Ollama API: {model}")
            resp = requests.post(
                self.chat_url, json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    @staticmethod
    def _build_cloud_payload(api_format: str, model: str, prompt: str, image_url_data: str) -> dict:
        """根据 api_format 构建不同格式的请求体"""

        if api_format == "dashscope":
            return {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url_data}},
                        {"type": "text", "text": prompt},
                    ]
                }],
                "temperature": 0.1,
                "stream": False,
            }

        elif api_format == "qwen_vl_legacy":
            return {
                "model": model,
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"image": image_url_data},
                            {"text": prompt},
                        ]
                    }]
                },
                "parameters": {"temperature": 0.1},
            }

        else:
            return {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url_data}},
                        {"type": "text", "text": prompt},
                    ]
                }],
                "temperature": 0.1,
                "stream": False,
            }

    @staticmethod
    def _parse_cloud_response(api_format: str, data: dict) -> str:
        """根据 api_format 解析响应"""
        if api_format == "qwen_vl_legacy":
            output = data.get("output", {})
            choices = output.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return output.get("text", "")
        else:
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def health_check(self) -> bool:
        """检查 Ollama 服务是否正常"""
        try:
            resp = requests.get(
                self.base_url + "/api/tags", timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False


# ═══════════════════════════════════════════════
# JSON 提取（从模型原始文本中健壮提取）
# ═══════════════════════════════════════════════

def extract_json(raw_text: str) -> dict | None:
    """
    从模型返回文本中健壮提取JSON。

    5层降级解析策略：
    1. 直接解析
    2. 正则提取 {…} 再解析
    3. 修复末尾逗号
    4. 单引号→双引号
    5. 组合修复
    """
    if not raw_text:
        return None

    text = raw_text.strip()
    # 去掉 ```json / ``` 包裹
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    for attempt in [
        lambda t: json.loads(t),
        lambda t: json.loads(re.search(r'\{[\s\S]*\}', t).group()),
        lambda t: json.loads(
            re.sub(r',\s*}', '}', re.search(r'\{[\s\S]*\}', t).group())
        ),
        lambda t: json.loads(
            re.sub(r"'", '"', re.search(r'\{[\s\S]*\}', t).group())
        ),
        lambda t: json.loads(
            re.sub(r',\s*}', '}',
                   re.sub(r"'", '"',
                          re.search(r'\{[\s\S]*\}', t).group()))
        ),
    ]:
        try:
            return attempt(text)
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def parse_single_field(raw_text: str, field: str) -> str:
    """从模型返回中提取单字段值"""
    parsed = extract_json(raw_text)
    if parsed:
        return parsed.get(field, "")
    # 正则直接摘出
    m = re.search(rf'"{field}"\s*:\s*"([^"]+)"', raw_text)
    if m:
        return m.group(1)
    return ""


def normalize_result(parsed: dict) -> dict:
    """
    归一化结构化结果，确保6个字段都存在且类型正确。
    兼容旧格式的不同key名。
    """
    from vision_harness.config import ALL_FIELDS

    result = {}
    aliases = {
        "space_type": ["space", "type", "room_type", "room"],
        "wall_material": ["wall", "wall_mat"],
        "floor_material": ["floor", "floor_mat"],
        "ceiling_material": ["ceiling", "ceiling_mat", "ceiling_type"],
        "decor_style": ["style", "overall_style", "decoration_style"],
        "remark": ["notes", "note", "description", "other"],
    }

    for key in ALL_FIELDS:
        val = parsed.get(key, "")
        if not val:
            for alias in aliases.get(key, []):
                val = parsed.get(alias, "")
                if val:
                    break
        if not isinstance(val, str):
            try:
                val = str(val)
            except Exception:
                val = ""
        result[key] = val.strip() if val else ""

    return result
