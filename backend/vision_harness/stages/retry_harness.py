"""
BuildSight 视觉识别 Harness — 重试调度层
============================================
职责：发现异常输出 → 裁剪对应区域 → 针对性重推理 → 校验闭环。

触发器（任一满足即触发重试）：
  A. 字段值为 "未知" / "(空)"
  B. 字段值不在枚举列表内
  C. 字段值不满足空间-材质规则

流程：
  全图推理 → 逐字段校验 → 发现问题字段 →
  裁剪对应区域 → 区域推理 → 替换字段值 → 再次校验 →
  最多 MAX_RETRY_ATTEMPTS 次/字段
"""

import logging
from copy import deepcopy

from vision_harness.config import MAX_RETRY_ATTEMPTS, FIELD_TO_CROP, MATERIAL_FIELDS
from vision_harness.stages.validator import OutputValidator
from vision_harness.stages.preprocessor import ImagePreprocessor
from vision_harness.stages.inferrer import ModelInferrer, build_crop_prompt, parse_single_field, normalize_result
from vision_harness.material_library import SPACE_MATERIAL_RULES

logger = logging.getLogger(__name__)


class RetryHarness:
    """
    重试调度器。

    组合 Preprocessor + Inferrer + Validator 完成重试闭环。
    不感知业务逻辑，只负责"检测问题→重试→替换"。
    """

    def __init__(self, preprocessor: ImagePreprocessor,
                 inferrer: ModelInferrer,
                 validator: OutputValidator):
        self.preprocessor = preprocessor
        self.inferrer = inferrer
        self.validator = validator
        self.max_attempts = MAX_RETRY_ATTEMPTS

    def _get_triggered_fields(self, structured: dict) -> list[str]:
        """
        检测哪些字段触发了重试条件。

        返回需要重试的字段名列表。
        """
        space_type = structured.get("space_type", "")
        triggered = []
        for field in MATERIAL_FIELDS:
            value = structured.get(field, "")
            if not self.validator.is_valid(value, field, space_type):
                triggered.append(field)
        return triggered

    def execute(self, image_path: str, initial_result: dict,
                model: str, model_type: str = None) -> tuple[dict, list[str]]:
        """
        执行重试闭环。

        参数:
            image_path: 原始图片路径
            initial_result: 全图推理的归一化结果
            model: 模型名称

        返回:
            (修正后的 result, retry_log)
        """
        result = deepcopy(initial_result)
        retry_log = []
        space_type = result.get("space_type", "")

        # 逐字段检查
        for field in MATERIAL_FIELDS:
            value = result.get(field, "")
            attempts = 0

            while (not self.validator.is_valid(value, field, space_type)
                   and attempts < self.max_attempts):
                attempts += 1
                crop_key = FIELD_TO_CROP.get(field)
                if not crop_key:
                    break

                # 获取裁剪区域
                try:
                    crops = self.preprocessor.crop_regions(image_path)
                except Exception as e:
                    logger.warning("裁剪失败 [%s]: %s", field, e)
                    break

                crop_b64 = crops.get(crop_key, "")
                if not crop_b64:
                    break

                crop_prompt = build_crop_prompt(field)
                if not crop_prompt:
                    break

                # 区域推理
                try:
                    crop_raw = self.inferrer.infer(
                        crop_prompt, crop_b64, model=model, model_type=model_type
                    )
                    new_val = parse_single_field(crop_raw, field)

                    if new_val and new_val != value:
                        old_val = value
                        value = new_val
                        result[field] = new_val
                        retry_log.append(
                            f"{field}: 裁剪重试#{attempts} '{old_val}'→'{new_val}'"
                        )
                        logger.info(
                            "裁剪重试成功: %s '%s'→'%s' (尝试#%d)",
                            field, old_val, new_val, attempts,
                        )
                except Exception as e:
                    logger.warning("裁剪重试异常 [%s]: %s", field, e)
                    break

            # 如果重试后仍无效，用规则引擎最接近项兜底
            if not self.validator.is_valid(value, field, space_type):
                # 枚举模糊匹配
                match = self.validator.fuzzy_match_in_enum(value, field)
                if match:
                    result[field] = match
                    retry_log.append(f"{field}: 枚举模糊兜底→'{match}'")
                elif space_type:
                    # 规则模糊匹配
                    match = self.validator.fuzzy_match_in_rules(
                        space_type, field, value
                    )
                    if match:
                        result[field] = match
                        retry_log.append(
                            f"{field}: 规则模糊兜底→'{match}'"
                        )

        return result, retry_log
