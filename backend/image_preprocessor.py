"""
图片预处理模块
功能：缩放、JPEG压缩、去EXIF，提升LLaVA识别稳定性和速度
"""

import os
from pathlib import Path
from PIL import Image

# 最长边目标尺寸
MAX_LONG_SIDE = 1024
# JPEG 压缩质量
JPEG_QUALITY = 85


def preprocess_image(input_path: str, output_dir: str = None) -> str:
    """
    预处理单张图片：
    1. 最长边缩放到 1024px（保持宽高比）
    2. JPEG 压缩质量 85
    3. 去除 EXIF 信息
    4. 保存到 output_dir（默认同目录，文件名加 _processed 后缀）
    5. 返回新文件路径

    Args:
        input_path: 原始图片路径
        output_dir: 输出目录（默认与输入同目录）

    Returns:
        处理后的图片文件路径
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"图片文件不存在: {input_path}")

    # 确定输出目录和文件名
    out_dir = Path(output_dir) if output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    suffix = input_path.suffix.lower()

    # 输出统一为 .jpg 格式
    out_name = f"{stem}_processed.jpg"
    out_path = out_dir / out_name

    img = Image.open(input_path)

    # ---------- 1. 缩放：最长边 <= MAX_LONG_SIDE ----------
    w, h = img.size
    if max(w, h) > MAX_LONG_SIDE:
        if w >= h:
            new_w = MAX_LONG_SIDE
            new_h = int(h * MAX_LONG_SIDE / w)
        else:
            new_h = MAX_LONG_SIDE
            new_w = int(w * MAX_LONG_SIDE / h)
        # 使用 LANCZOS 重采样（高质量）
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # ---------- 2+3. 去除EXIF + 转RGB（确保JPEG保存兼容）----------
    # 创建一个不带 EXIF 的副本：用 img.tobytes 重建 Image 对象
    # 但更干净的方法是用 img.getdata() 新建
    if img.mode in ("RGBA", "P", "LA"):
        # 有透明通道的图需要转 RGB（白色背景）
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # ---------- 4. 保存（JPEG 质量85，无EXIF）----------
    img.save(
        out_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        exif=b"",  # 显式清空 EXIF
    )

    return str(out_path)


def preprocess_image_stats(input_path: str, output_path: str) -> dict:
    """返回预处理前后文件大小对比统计"""
    in_size = os.path.getsize(input_path)
    out_size = os.path.getsize(output_path)
    return {
        "original_path": input_path,
        "processed_path": output_path,
        "original_size_bytes": in_size,
        "processed_size_bytes": out_size,
        "original_size_kb": round(in_size / 1024, 1),
        "processed_size_kb": round(out_size / 1024, 1),
        "compression_ratio": (
            round((1 - out_size / in_size) * 100, 1) if in_size > 0 else 0
        ),
    }
