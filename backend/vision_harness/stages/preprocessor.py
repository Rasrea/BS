"""
BuildSight 视觉识别 Harness — 图像预处理
============================================
负责图像加载、视图类型检测、动态裁剪、缩放放大、模型输入预处理。

v2.0 新增：
- 视图类型动态检测（perspective / closeup / panorama）
- 放大裁剪（缩窄宽度 + 重放大，凸显材质纹理）
- 裁剪区域独立分辨率
"""

import io
import base64
import os
import logging
from PIL import Image

from vision_harness.config import (
    CROP_RATIOS, MAX_IMAGE_DIM, JPEG_QUALITY,
    CROP_MAX_DIM, CROP_ZOOM_CONFIG,
    VIEW_NEAR_RATIO_LOW, VIEW_NEAR_RATIO_HIGH, VIEW_PANORAMA_RATIO,
    CROP_STRATEGY_PERSPECTIVE, CROP_STRATEGY_PANORAMA,
)

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    图像预处理器（v2.0 — 动态裁剪 + 放大）

    功能：
    1. 加载图片，RGBA→RGB 转换
    2. 自动检测视图类型
    3. 按视图类型动态裁剪（透视/近景/全景）
    4. 放大裁剪（窄宽度→全尺寸放大，凸显纹理）
    5. 缩放压缩 → JPEG base64
    """

    def __init__(self):
        self.max_dim = MAX_IMAGE_DIM
        self.crop_max_dim = CROP_MAX_DIM
        self.jpeg_quality = JPEG_QUALITY
        self.zoom_config = CROP_ZOOM_CONFIG

    # ── 视图类型检测 ──

    def detect_view_type(self, image: Image.Image) -> str:
        """
        根据宽高比检测图片视图类型。

        返回:
            "perspective" — 标准透视效果图（宽高比在正常范围）
            "closeup"     — 近景/特写/局部图（接近正方形或极端比例）
            "panorama"    — 宽幅全景（w/h 很大）
        """
        w, h = image.size
        ratio = w / h

        if ratio < VIEW_NEAR_RATIO_LOW or ratio > VIEW_NEAR_RATIO_HIGH:
            if ratio > VIEW_PANORAMA_RATIO:
                logger.debug(
                    "视图类型=全景: w/h=%.2f > %.1f",
                    ratio, VIEW_PANORAMA_RATIO,
                )
                return "panorama"
            logger.debug(
                "视图类型=近景: w/h=%.2f (低阈值=%.1f, 高阈值=%.1f)",
                ratio, VIEW_NEAR_RATIO_LOW, VIEW_NEAR_RATIO_HIGH,
            )
            return "closeup"

        logger.debug("视图类型=透视: w/h=%.2f", ratio)
        return "perspective"

    # ── 核心预处理 ──

    def preprocess_image(self, image: Image.Image,
                         max_dim: int | None = None) -> bytes:
        """
        单图预处理：缩放 + JPEG压缩。

        参数:
            image: PIL Image
            max_dim: 最长边限制（默认使用实例的 max_dim）

        返回:
            JPEG bytes
        """
        if image.mode == "RGBA":
            image = image.convert("RGB")

        target_dim = max_dim or self.max_dim
        w, h = image.size
        if max(w, h) > target_dim:
            scale = target_dim / max(w, h)
            image = image.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS
            )

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=self.jpeg_quality)
        return buf.getvalue()

    def load_image(self, image_path: str) -> Image.Image:
        """加载图像文件"""
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        img = Image.open(image_path)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        return img

    # ── 裁剪（增强版） ──

    def _crop_with_zoom(self, image: Image.Image, region_name: str) -> Image.Image:
        """
        带放大的智能裁剪。

        流程：
        1. 按透视比例 y 方向裁剪
        2. 缩窄宽度取中心区域（去墙边阴影/过渡区）
        3. 放大到 crop_max_dim，保持宽高比

        参数:
            image: 全图
            region_name: ceiling / wall / floor

        返回:
            裁剪+放大后的 PIL Image
        """
        w, h = image.size
        y_start, y_end = CROP_RATIOS[region_name]

        # 步骤1：y 方向裁剪
        y1, y2 = int(h * y_start), int(h * y_end)
        cropped = image.crop((0, y1, w, y2))

        # 步骤2：缩窄宽度，取中心区域
        zoom_cfg = self.zoom_config.get(region_name)
        if zoom_cfg:
            cx, cw_ratio = zoom_cfg[2], zoom_cfg[3]
            crop_w = cropped.width
            new_w = int(crop_w * cw_ratio)
            x1 = int(crop_w * (cx - cw_ratio / 2))
            x2 = x1 + new_w
            # 边界保护
            x1 = max(0, x1)
            x2 = min(crop_w, x2)
            cropped = cropped.crop((x1, 0, x2, cropped.height))

        # 步骤3：放大到 crop_max_dim（保留纹理细节）
        cw, ch = cropped.size
        if max(cw, ch) < self.crop_max_dim:
            scale = self.crop_max_dim / max(cw, ch)
            cropped = cropped.resize(
                (int(cw * scale), int(ch * scale)), Image.LANCZOS
            )

        return cropped

    def crop_regions(self, image_path: str,
                     force_strategy: str | None = None) -> dict[str, str]:
        """
        智能裁剪：自动检测视图类型 + 动态裁剪策略。

        参数:
            image_path: 图片路径
            force_strategy: 强制指定策略（perspective/closeup/panorama）
                           不指定则自动检测

        返回:
            {"ceiling": "base64...", "wall": "base64...", "floor": "base64..."}
            如果是 closeup 视图，返回空 dict（不裁剪）
        """
        img = self.load_image(image_path)

        # 检测视图类型
        view_type = force_strategy or self.detect_view_type(img)

        # 近景/局部图 → 不裁剪（全图推理即可）
        if view_type == "closeup":
            logger.info("视图类型=近景/局部图，跳过裁剪")
            return {}

        # 选择策略
        if view_type == "panorama":
            strategy = CROP_STRATEGY_PANORAMA
        else:
            strategy = CROP_STRATEGY_PERSPECTIVE

        w, h = img.size
        crops = {}

        for region_name, cfg in strategy.items():
            y_start, y_end = cfg["y"]
            y1, y2 = int(h * y_start), int(h * y_end)

            if cfg.get("zoom", False):
                # 放大裁剪
                cropped = self._crop_with_zoom(img, region_name)
            else:
                # 标准裁剪（全宽）
                cropped = img.crop((0, y1, w, y2))

            preprocessed = self.preprocess_image(
                cropped, max_dim=self.crop_max_dim
            )
            crops[region_name] = base64.b64encode(preprocessed).decode("utf-8")

            logger.debug(
                "裁剪 [%s|%s]: y=[%d:%d] zoom=%s size=%dB",
                view_type, region_name, y1, y2,
                cfg.get("zoom", False), len(crops[region_name]),
            )

        return crops

    def full_image_base64(self, image_path: str) -> str:
        """返回全图预处理后的 base64"""
        img = self.load_image(image_path)
        preprocessed = self.preprocess_image(img)
        return base64.b64encode(preprocessed).decode("utf-8")

    # ── 新旧 API 兼容 ──

    def crop_regions_legacy(self, image_path: str) -> dict[str, str]:
        """
        旧版裁剪（纯透视比例，无放大）—— 兼容旧调用方。
        用于 benchmark 对比新旧策略效果。
        """
        img = self.load_image(image_path)
        w, h = img.size
        crops = {}

        for name, (y_start, y_end) in CROP_RATIOS.items():
            y1 = int(h * y_start)
            y2 = int(h * y_end)
            cropped = img.crop((0, y1, w, y2))
            preprocessed = self.preprocess_image(cropped, max_dim=self.crop_max_dim)
            crops[name] = base64.b64encode(preprocessed).decode("utf-8")

        return crops