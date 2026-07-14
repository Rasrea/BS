"""
BuildSight 视觉识别 Harness — 图像预处理
============================================
负责图像加载、透视裁剪、模型输入预处理。

职责单一：输入路径 → 输出各区域 base64。
"""

import io
import base64
import os
import logging
from PIL import Image

from vision_harness.config import CROP_RATIOS, MAX_IMAGE_DIM, JPEG_QUALITY

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    图像预处理器。

    功能：
    1. 加载图片，RGBA→RGB 转换
    2. 按透视比例裁剪为 ceiling/wall/floor 三个区域
    3. 缩放至模型输入尺寸（最长边 MAX_IMAGE_DIM）
    4. 压缩为 JPEG 格式
    5. 返回各区域 base64 编码
    """

    def __init__(self):
        self.crop_ratios = CROP_RATIOS
        self.max_dim = MAX_IMAGE_DIM
        self.jpeg_quality = JPEG_QUALITY

    def preprocess_image(self, image: Image.Image) -> bytes:
        """
        单图预处理：缩放 + JPEG压缩。
        返回 bytes，可直接送 base64 编码。
        """
        if image.mode == "RGBA":
            image = image.convert("RGB")
        w, h = image.size
        if max(w, h) > self.max_dim:
            scale = self.max_dim / max(w, h)
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

    def crop_regions(self, image_path: str) -> dict[str, str]:
        """
        对效果图进行透视裁剪。

        返回:
            {"ceiling": "base64...", "wall": "base64...", "floor": "base64..."}

        透视分割示意:
          ┌───────────────────┐
          │    CEILING 0-30%  │  ← 顶面/吊顶区域
          ├───────────────────┤
          │    WALL 25-75%    │  ← 墙面区域（重叠，保完整）
          ├───────────────────┤
          │    FLOOR 60-100%  │  ← 地面区域
          └───────────────────┘
        """
        img = self.load_image(image_path)
        w, h = img.size
        crops = {}

        for name, (y_start, y_end) in self.crop_ratios.items():
            y1 = int(h * y_start)
            y2 = int(h * y_end)
            cropped = img.crop((0, y1, w, y2))
            preprocessed = self.preprocess_image(cropped)
            crops[name] = base64.b64encode(preprocessed).decode("utf-8")
            logger.debug(
                "裁剪区域 %s: y=[%d:%d], size=%dB",
                name, y1, y2, len(crops[name]),
            )

        return crops

    def full_image_base64(self, image_path: str) -> str:
        """返回全图预处理后的 base64"""
        img = self.load_image(image_path)
        preprocessed = self.preprocess_image(img)
        return base64.b64encode(preprocessed).decode("utf-8")
