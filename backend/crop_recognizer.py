"""
BuildSight 分区域裁剪识别模块
============================================
负责：
1. 图像裁剪（ceiling/wall/floor + full）
2. 分区域模型推理
3. 裁剪图片保存（调试用）
4. 结果合并与归一化

使用方式：
    from crop_recognizer import CropRecognizer
    recognizer = CropRecognizer()
    result = recognizer.recognize_with_crop(image_path, model, upload_dir, task_id)
"""

import os
import time
import base64
import logging
from pathlib import Path

from vision_harness.stages.preprocessor import ImagePreprocessor
from vision_harness.stages.inferrer import (
    ModelInferrer, extract_json, normalize_result, build_crop_prompt
)

logger = logging.getLogger(__name__)

# region_name 到 field 的映射
REGION_TO_FIELD = {
    "ceiling": "ceiling_material",
    "wall": "wall_material",
    "floor": "floor_material",
}

class CropRecognizer:
    """
    分区域裁剪识别器。
    
    功能：
    1. 裁剪图像为 ceiling/wall/floor/full 四个区域
    2. 对每个区域独立推理
    3. 保存裁剪图片到调试目录
    4. 合并结果并返回标准格式
    """

    def __init__(self, model_type: str = None, api_base_url: str = None,
                 api_token: str = None, api_format: str = None):
        self.preprocessor = ImagePreprocessor()
        self.inferrer = ModelInferrer()
        if api_base_url or api_token:
            self.inferrer.set_custom_model_config(
                api_base_url=api_base_url or "",
                api_token=api_token or "",
                api_format=api_format or "openai",
            )
        self._model_type = model_type

    def save_crop_images(
        self,
        crops: dict,
        upload_dir: Path,
        task_id: str,
    ) -> tuple[list[str], str]:
        """
        保存裁剪图片到调试目录。

        参数:
            crops: {region_name: base64_string}
            upload_dir: 上传目录
            task_id: 任务 ID

        返回:
            (crop_paths, crop_debug_dir)
            crop_paths: 保存的图片路径列表
            crop_debug_dir: 调试目录路径
        """
        crop_paths = []
        crop_debug_dir = upload_dir / f"{task_id}_crops"
        crop_debug_dir.mkdir(exist_ok=True)

        for region_name, region_b64 in crops.items():
            try:
                img_bytes = base64.b64decode(region_b64)
                crop_img_path = crop_debug_dir / f"{region_name}.jpg"
                crop_img_path.write_bytes(img_bytes)
                crop_paths.append(str(crop_img_path))
                logger.debug("裁剪区域 %s 已保存: %s", region_name, crop_img_path)
            except Exception as e:
                logger.error("保存裁剪图片失败 %s: %s", region_name, e)

        return crop_paths, str(crop_debug_dir)

    def recognize_with_crop(
        self,
        image_path: str,
        model: str,
        upload_dir: Path,
        task_id: str,
    ) -> dict:
        """
        执行分区域裁剪识别。
        """
        timings = {}
        t0 = time.time()

        # ====== 步骤1：裁剪区域 ======
        crops = self.preprocessor.crop_regions(image_path)
        timings["crop"] = round(time.time() - t0, 3)

        # 添加全图到 crops 中，用于空间类型识别
        full_img_b64 = self.preprocessor.full_image_base64(image_path)
        crops["full"] = full_img_b64

        # ====== 步骤2：保存裁剪图片（调试用）=====
        # crop_paths, crop_debug_dir = "", ""
        # t_save = time.time()
        # crop_paths, crop_debug_dir = self.save_crop_images(
        #     crops, upload_dir, task_id
        # )
        # timings["store_crop_img"] = round(time.time() - t_save, 3)

        # ====== 步骤3：分区域推理 ======
        crop_results = {}
        for region_name, region_b64 in crops.items():
            region_t0 = time.time()

            if region_name == "full":
                # 全图 → 空间类型 + 装修风格
                prompt = self.inferrer.full_prompt
            else:
                # 裁剪区域 → 材质
                field = REGION_TO_FIELD.get(region_name, region_name)
                prompt = build_crop_prompt(field)

                if not prompt:
                    logger.warning(
                        "未找到区域 %s (field=%s) 对应的 prompt，跳过",
                        region_name, field,
                    )
                    continue

            try:
                raw_text = self.inferrer.infer(prompt, region_b64, model=model, model_type=self._model_type)
                parsed = extract_json(raw_text)
                if parsed:
                    crop_results.update(parsed)
                timings[f"inference_{region_name}"] = round(time.time() - region_t0, 3)
            except Exception as e:
                logger.error("区域 %s 推理失败: %s", region_name, e)
                timings[f"inference_{region_name}"] = round(time.time() - region_t0, 3)

        # ====== 步骤4：合并结果 ======
        structured = normalize_result(crop_results)
        structured["_crop_mode"] = "enabled"
        structured["_crop_details"] = {
            "regions_processed": list(crops.keys()),
            "fields_extracted": list(crop_results.keys()),
        }

        return {
            "success": True,
            "structured": structured,
            "raw_response": "",
            "model_used": model,
            "error": "",
            "timing": timings,
            # "debug": {
            #     "crop_images": crop_paths,
            #     "crop_dir": crop_debug_dir,
            # },
        }