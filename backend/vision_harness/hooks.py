"""
BuildSight 视觉识别 Harness — 全局 Hook 拦截器
============================================
职责：在各阶段插入日志、指标收集、性能监控。

Hook 点：
  • before_infer — 推理前记录输入信息
  • after_infer — 推理后记录耗时和输出长度
  • before_retry — 重试前记录触发原因
  • after_retry — 重试后记录修正结果
  • on_error — 异常时记录错误详情

当前实现：简单日志，后续可扩展为 Prometheus 指标 / 链路追踪。
"""

import time
import logging

logger = logging.getLogger(__name__)


class HarnessHooks:
    """全局 Hook 拦截器，挂载到流水线各阶段。"""

    def before_infer(self, image_path: str, model: str, stage: str = "full"):
        logger.info("[Hook] 推理开始 | stage=%s | model=%s | image=%s",
                     stage, model, image_path)

    def after_infer(self, stage: str, elapsed: float,
                    output_len: int, model: str):
        logger.info("[Hook] 推理完成 | stage=%s | model=%s | time=%.2fs | output=%dchars",
                     stage, model, elapsed, output_len)

    def before_retry(self, field: str, value: str, reason: str, attempt: int):
        logger.warning("[Hook] 触发重试 | field=%s | value=%s | reason=%s | attempt=%d",
                        field, value, reason, attempt)

    def after_retry(self, field: str, old_value: str,
                    new_value: str, attempt: int, success: bool):
        status = "✅" if success else "❌"
        logger.info("[Hook] 重试结果 %s | field=%s | '%s'→'%s' | attempt=%d",
                     status, field, old_value, new_value, attempt)

    def on_error(self, stage: str, error: str, context: dict = None):
        logger.error("[Hook] 阶段异常 | stage=%s | error=%s | context=%s",
                      stage, error, context or {})

    def report_metrics(self, structured: dict, timing: dict):
        """记录性能指标摘要"""
        logger.info(
            "[Metrics] 识别完成 | "
            "space=%(space)s wall=%(wall)s floor=%(floor)s ceiling=%(ceiling)s | "
            "total_time=%(total).2fs retry=%(retry)d",
            {
                "space": structured.get("space_type", "?"),
                "wall": structured.get("wall_material", "?"),
                "floor": structured.get("floor_material", "?"),
                "ceiling": structured.get("ceiling_material", "?"),
                "total": timing.get("total", 0),
                "retry": len(structured.get("_retry_log", [])),
            }
        )
