"""
BuildSight 视觉识别 Harness — 主流水线
============================================
编排所有阶段：Preprocess → Infer → Validate → Retry → Output。

设计原则（借鉴 OpenHarness 分层思想）：
  • 每个阶段职责单一，可独立替换
  • 阶段间通过标准接口通信（dict）
  • 全局 Hook 拦截（日志/指标）
  • 中心化配置（vision_harness/config.py）

流水线流程：
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 全图推理  │ →  │ 类型校验  │ →  │ 规则校验  │ →  │ 裁剪重试  │ →  │ 输出     │
  │(Inferrer) │    │(Validator)│    │(Validator)│    │(Retry)   │    │(Result)  │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                    ↑ 发现触发条件  ↑ 发现规则冲突
"""

import time
import logging

from vision_harness.config import DEFAULT_MODEL, FIELD_TO_CROP, MATERIAL_FIELDS
from vision_harness.stages.preprocessor import ImagePreprocessor
from vision_harness.stages.inferrer import ModelInferrer, extract_json, normalize_result
from vision_harness.stages.validator import OutputValidator
from vision_harness.stages.retry_harness import RetryHarness
from vision_harness.material_library import ENUM_MAPS

logger = logging.getLogger(__name__)


class VisionHarnessPipeline:
    """
    视觉识别 Harness 主流水线。

    使用方式:
        pipeline = VisionHarnessPipeline()
        result = pipeline.recognize("path/to/image.jpg")
        print(result["structured"])
    """

    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        self.inferrer = ModelInferrer()
        self.validator = OutputValidator()
        self.retry_harness = RetryHarness(
            self.preprocessor, self.inferrer, self.validator
        )

    def recognize(self, image_path: str,
                  model: str = DEFAULT_MODEL,
                  model_type: str = None,
                  api_base_url: str = None,
                  api_token: str = None,
                  api_format: str = None) -> dict:
        """
        全流水线执行。

        参数:
            image_path: 图片路径
            model: Ollama 模型名
            model_type: 模型类型 ('cloud' 或 'local')
            api_base_url: 自定义API地址
            api_token: 自定义API Token
            api_format: API格式 ('openai', 'dashscope', 'qwen_vl_legacy')

        返回:
            {
                "success": bool,
                "structured": dict,   # 6个字段 + _retry_log + _warnings
                "raw_response": str,  # 全图推理原始输出
                "model_used": str,
                "error": str,
                "timing": {...},      # 各阶段耗时
            }
        """
        if api_base_url or api_token:
            self.inferrer.set_custom_model_config(
                api_base_url=api_base_url or "",
                api_token=api_token or "",
                api_format=api_format or "openai",
            )
        # 捕获所有异常，确保不击穿
        try:
            return self._run(image_path, model, model_type=model_type)
        except Exception as e:
            logger.exception("Harness 流水线异常")
            return {
                "success": False,
                "structured": {
                    "space_type": "", "wall_material": "",
                    "floor_material": "", "ceiling_material": "",
                    "decor_style": "", "remark": f"流水线异常: {str(e)}",
                    "_warnings": [], "_retry_log": [],
                },
                "raw_response": "",
                "model_used": model,
                "error": f"Harness异常: {str(e)}",
            }

    def _run(self, image_path: str, model: str, model_type: str = None) -> dict:
        timing = {}

        # ====== Stage 1: 全图推理 ======
        t0 = time.time()
        img_b64 = self.preprocessor.full_image_base64(image_path)
        raw_text = self.inferrer.infer(
            self.inferrer.full_prompt, img_b64, model=model, model_type=model_type
        )
        timing["full_inference"] = round(time.time() - t0, 2)

        parsed = extract_json(raw_text)
        if not parsed:
            parsed = {
                "space_type": "", "wall_material": "",
                "floor_material": "", "ceiling_material": "",
                "decor_style": "", "remark": "",
            }

        result = normalize_result(parsed)

        # ====== Stage 2: 校验 + 重试 ======
        t1 = time.time()
        result, retry_log = self.retry_harness.execute(
            image_path, result, model, model_type=model_type
        )
        timing["retry"] = round(time.time() - t1, 2)

        # ====== Stage 3: 后验校验 & 修正兜底 ======
        t2 = time.time()
        validated = self.validator.validate_and_fix(result)
        timing["post_validation"] = round(time.time() - t2, 2)

        # ====== 附加元数据 ======
        validated["_retry_log"] = retry_log
        validated["_crop_retry_count"] = len(retry_log)
        validated["_timing"] = timing
        timing["total"] = round(sum(timing.values()), 2)

        return {
            "success": True,
            "structured": validated,
            "raw_response": raw_text[:2000],
            "model_used": model,
            "error": "",
            "timing": timing,
        }
