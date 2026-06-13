"""
效果图识别模块 v3.0 — Harness 兼容层
============================================
本文件为向后兼容层，所有逻辑委托给 vision_harness 流水线。

核心改造：
1. 所有识别逻辑移至 vision_harness/ 分层模块
2. 此文件保持函数签名不变，内部调用流水线
3. 导出函数：recognize_image, recognize_with_fallback
   （维持 main.py 和 benchmark_runner.py 无感知）
"""

import logging
import sys
import os

# 绝对导入 vision_harness（兼容从外部直接 import image_recognizer 的场景）
_cur_dir = os.path.dirname(os.path.abspath(__file__))
if _cur_dir not in sys.path:
    sys.path.insert(0, _cur_dir)

from vision_harness import recognize_image as _harness_recognize

logger = logging.getLogger(__name__)


def recognize_image(image_path: str, model: str = "qwen2.5:7b") -> dict:
    """
    识别单张效果图（委托 Harness 流水线）。

    返回格式与 v2.x 完全兼容。
    """
    return _harness_recognize(image_path, model=model)


def recognize_with_fallback(image_path: str, model: str = "qwen2.5:7b") -> dict:
    """
    识别效果图（对外接口，与旧版兼容）。
    """
    return _harness_recognize(image_path, model=model)
