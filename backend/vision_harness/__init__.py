"""
BuildSight 视觉识别 Harness

分层架构（借鉴 OpenHarness 设计思想）：
  config.py          → 中心化配置
  material_library.py → 材料库枚举 + 空间规则 + 同义词
  stages/
    preprocessor.py   → 图像裁剪预处理
    inferrer.py       → 模型调用 + Prompt构建 + JSON提取
    validator.py      → 枚举校验 + 规则引擎 + 模糊修正
    retry_harness.py  → 重试调度（裁剪→推理→校验闭环）
  pipeline.py         → 主流水线编排
  hooks.py            → 全局拦截器（日志/指标）

兼容接口：
  recognize_image(path, model)  → 旧版 image_recognizer 同名函数
"""

from vision_harness.pipeline import VisionHarnessPipeline

# 全局流水线实例（单例，避免重复初始化）
_pipeline: VisionHarnessPipeline | None = None


def get_pipeline() -> VisionHarnessPipeline:
    """获取全局流水线实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = VisionHarnessPipeline()
    return _pipeline


def recognize_image(image_path: str,
                    model: str = "qwen2.5:7b",
                    model_type: str = None,
                    api_base_url: str = None,
                    api_token: str = None,
                    api_format: str = None) -> dict:
    """
    兼容接口（与旧版 image_recognizer.recognize_image 签名一致）。
    内部委托给 VisionHarnessPipeline。
    """
    return get_pipeline().recognize(image_path, model=model,
                                    model_type=model_type,
                                    api_base_url=api_base_url,
                                    api_token=api_token,
                                    api_format=api_format)
