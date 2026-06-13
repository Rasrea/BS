"""
BuildSight 视觉识别 Harness — 校验层
============================================
职责：模型输出校验 + 枚举约束检查 + 空间-材质规则引擎 + 模糊修正。

校验链：
  1. 枚举存在性 → 值是否在材料库枚举内
  2. 枚举模糊匹配 → 相似度过阈值则归正
  3. 空间-材质规则 → 值与空间是否合理搭配
  4. 规则模糊匹配 → 规则内找最接近项

每个校验步骤都有 "pass → continue" / "fail → try fix" 路径。
"""

import logging
from difflib import SequenceMatcher

from vision_harness.config import MATERIAL_FIELDS
from vision_harness.material_library import (
    SPACE_TYPE_LIST, ENUM_MAPS, SPACE_MATERIAL_RULES, is_synonym,
)

logger = logging.getLogger(__name__)


class OutputValidator:
    """
    输出校验器。

    提供逐层校验方法，供 RetryHarness 和 Pipeline 调用。
    不持有状态，纯函数式设计。
    """

    def check_in_enum(self, value: str, field: str) -> bool:
        """检查值是否在枚举列表内"""
        if not value or value in ("未知", "(空)", ""):
            return False
        if field == "space_type":
            return value in SPACE_TYPE_LIST
        valid_list = ENUM_MAPS.get(field, [])
        return value in valid_list

    def fuzzy_match_in_enum(self, value: str, field: str) -> str | None:
        """在枚举列表中模糊匹配，返回最佳匹配或None"""
        if field == "space_type":
            valid_list = SPACE_TYPE_LIST
        else:
            valid_list = ENUM_MAPS.get(field, [])
        best_match, best_ratio = "", 0
        for vl in valid_list:
            ratio = SequenceMatcher(None, value, vl).ratio()
            if ratio > best_ratio:
                best_match, best_ratio = vl, ratio
        if best_ratio >= 0.8:
            return best_match
        return None

    def check_space_rules(self, space_type: str, field: str, value: str) -> bool:
        """检查值是否满足空间-材质规则"""
        if space_type not in SPACE_MATERIAL_RULES:
            return True  # 无规则约束视为通过
        rules = SPACE_MATERIAL_RULES[space_type]
        if field not in rules:
            return True  # 该字段无规则约束
        allowed = rules[field]
        if value in allowed:
            return True
        # 同义词匹配
        for al in allowed:
            if is_synonym(value, al):
                return True
        return False

    def fuzzy_match_in_rules(self, space_type: str, field: str,
                              value: str) -> str | None:
        """在空间规则允许列表中模糊匹配"""
        if space_type not in SPACE_MATERIAL_RULES:
            return None
        rules = SPACE_MATERIAL_RULES[space_type]
        if field not in rules:
            return None
        allowed = rules[field]
        best_match, best_ratio = "", 0
        for al in allowed:
            ratio = SequenceMatcher(None, value, al).ratio()
            if ratio > best_ratio:
                best_match, best_ratio = al, ratio
        if best_ratio >= 0.8:
            return best_match
        return None

    def is_valid(self, value: str, field: str, space_type: str = "") -> bool:
        """
        综合校验：枚举存在性 + 空间-材质规则。
        返回 True=有效 / False=需要重试或修正。
        """
        # 1. 基本存在性
        if not value or value in ("未知", "(空)"):
            return False
        # 2. 枚举校验
        if not self.check_in_enum(value, field):
            return False
        # 3. 空间-材质规则校验
        if space_type:
            return self.check_space_rules(space_type, field, value)
        return True

    def validate_and_fix(self, structured: dict) -> dict:
        """
        全量后验校验+修正。

        对 structured 中的每个字段执行：
        1. 枚举检查 → 不在则模糊修正
        2. 空间-材质规则 → 冲突则规则内模糊修正
        3. 记录所有告警

        返回修正后的结构体（含 _warnings 元数据）。
        """
        warnings = []
        result = dict(structured)
        space_type = result.get("space_type", "")

        # ---- 校验空间类型 ----
        if space_type and space_type not in SPACE_TYPE_LIST:
            best = self.fuzzy_match_in_enum(space_type, "space_type")
            if best:
                logger.info("空间类型模糊修正: '%s' → '%s'", space_type, best)
                result["space_type"] = best
                warnings.append(f"空间类型修正: {space_type}→{best}")
                space_type = best

        # ---- 校验材质字段 ----
        for field in MATERIAL_FIELDS:
            val = result.get(field, "")
            if not val:
                continue

            # 枚举检查 + 模糊修正
            if not self.check_in_enum(val, field):
                match = self.fuzzy_match_in_enum(val, field)
                if match:
                    logger.info("材质模糊修正 [%s]: '%s' → '%s'", field, val, match)
                    result[field] = match
                    warnings.append(f"{field}修正: {val}→{match}")
                    val = match

            # 空间-材质规则检查 + 修正
            if space_type and not self.check_space_rules(space_type, field, val):
                match = self.fuzzy_match_in_rules(space_type, field, val)
                if match:
                    logger.warning(
                        "空间-材质规则修正: %s.字段=%s→%s",
                        space_type, field, match,
                    )
                    result[field] = match
                    warnings.append(
                        f"空间\"{space_type}\"禁用{field}={val},修正→{match}"
                    )

        result["_warnings"] = warnings
        return result
