"""
FastAPI 主服务 - 家装智能自动报价系统（首期工程化版）
核心功能：
1. DXF矢量解析 + 工程量计算 + 基础报价
2. LLaVA效果图单图材质识别
3. 数据融合（CAD精准数据 + AI材质）→ 标准化分层报价
4. Excel导出（4Sheet）
5. 全局任务状态机 + 异步锁 + 三层门禁
"""
import os
import uuid
from collections import OrderedDict
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout

import data

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import logging
from cad_parser import parse_cad_file
from image_recognizer import recognize_with_fallback
from quantity_estimator import estimate_quantities
from fusion_validator import merge_dxf_and_vl
from deduct_rule import apply_deductions
from image_preprocessor import preprocess_image, preprocess_image_stats

from db import db
from excel_export import export_quote_excel
import space_synonyms
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

# ─────────────────── App ───────────────────

app = FastAPI(title="家装智能自动报价系统", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR = Path.home() / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

# ─────────────────── 任务状态机 ───────────────────
# 5种固定状态
STATE_IDLE = "idle"
STATE_CAD = "cad_running"
STATE_AI = "ai_running"
STATE_MERGE = "merge_running"
STATE_EXPORT = "export_running"

VALID_STATES = {STATE_IDLE, STATE_CAD, STATE_AI, STATE_MERGE, STATE_EXPORT}

# 需要独占锁的任务类型 → 对应状态
TASK_LOCKS = {
    "cad": STATE_CAD,
    "ai": STATE_AI,
    "merge": STATE_MERGE,
    "export": STATE_EXPORT,
}

# 超时阈值（秒），设为0表示不超时
TIMEOUT_CAD = 0     # 不设超时
TIMEOUT_AI = 0     # 不设超时
TIMEOUT_MERGE = 10
TIMEOUT_EXPORT = 15


class TaskState:
    """全局任务状态机 + 异步锁"""
    def __init__(self):
        self._lock = asyncio.Lock()
        self._state = STATE_IDLE
        self._trace_id = ""
        self._executor = ProcessPoolExecutor(max_workers=1)

    @property
    def state(self) -> str:
        return self._state

    @property
    def trace_id(self) -> str:
        return self._trace_id

    async def acquire(self, task_type: str) -> tuple[bool, str]:
        """尝试获取锁，成功返回 (True, trace_id)，失败返回 (False, current_state)"""
        target_state = TASK_LOCKS.get(task_type)
        if not target_state:
            return False, self._state

        async with self._lock:
            if self._state != STATE_IDLE:
                return False, self._state
            self._state = target_state
            self._trace_id = datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
            return True, self._trace_id

    async def release(self):
        """释放锁，重置为 idle"""
        async with self._lock:
            self._state = STATE_IDLE
            self._trace_id = ""

    async def reset(self):
        """强制重置（异常恢复时使用）"""
        async with self._lock:
            self._state = STATE_IDLE
            self._trace_id = ""


task_state = TaskState()


# ─────────────────── 统一响应格式 ───────────────────

def ok(data=None, message="操作成功", task_status=None, trace_id="") -> dict:
    return {
        "success": True,
        "code": 200,
        "message": message,
        "data": data or {},
        "task_status": task_status or task_state.state,
        "trace_id": trace_id or task_state.trace_id,
    }


def err(code: int, message: str, data=None, task_status=None, trace_id="") -> dict:
    return {
        "success": False,
        "code": code,
        "message": message,
        "data": data,
        "task_status": task_status or task_state.state,
        "trace_id": trace_id or task_state.trace_id,
    }


# ─────────────────── 门禁工具函数 ───────────────────

ALLOWED_CAD_EXT = {".dxf", ".dwg", ".pdf"}
ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pdf"}
ALLOWED_PDF_EXT = {".pdf"}
MAX_CAD_SIZE = 120 * 1024 * 1024   # 120MB
MAX_IMG_SIZE = 10 * 1024 * 1024    # 10MB
MAX_PDF_SIZE = 50 * 1024 * 1024    # 50MB


def check_mixed_request(cad_file: UploadFile, image_file: UploadFile):
    """门禁：禁止同一请求同时携带CAD+图片"""
    if cad_file and image_file:
        raise HTTPException(status_code=409, detail="禁止混合请求：CAD解析与效果图识别必须分两次单独调用")


async def check_file_gate(file: UploadFile, max_size: int, allowed_ext: set, file_type: str):
    """门禁：文件格式/大小校验"""
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=415, detail=f"不支持的文件格式: {ext}")
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"文件过大：{file_type}最大{max_size//1024//1024}MB")
    await file.seek(0)
    return content, ext


async def require_idle(task_type: str):
    """门禁：要求系统空闲才能执行任务"""
    ok_flag, tid = await task_state.acquire(task_type)
    if not ok_flag:
        raise HTTPException(
            status_code=409,
            detail=f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作"
        )
    return tid


async def safe_run(task_type: str, timeout: int, fn, *args, **kwargs):
    """
    带超时熔断的安全执行器
    - timeout=0 表示不设超时（适配CPU慢速推理）
    - 耗时 CAD 操作在子进程运行，可强杀
    - 普通协程用 asyncio.wait_for
    """
    tid = await require_idle(task_type)
    log_id = await db.add_log(task_type, operation_action=f"{task_type}_run", trace_id=tid)

    start = time.time()
    error_info = ""
    data = None
    try:
        to = timeout if timeout > 0 else None  # 0 → None 表示不超时
        if task_type == "cad":
            loop = asyncio.get_event_loop()
            fut = loop.run_in_executor(task_state._executor, fn, *args, **kwargs)
            data = await asyncio.wait_for(fut, timeout=to)
        else:
            # 同步函数用线程池执行，避免asyncio无法await普通返回值
            loop = asyncio.get_event_loop()
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = loop.run_in_executor(pool, fn, *args, **kwargs)
                data = await asyncio.wait_for(fut, timeout=to)

        duration = time.time() - start
        await db.update_log(log_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "success", duration)
        return data, tid, None

    except asyncio.TimeoutError:
        duration = time.time() - start
        error_info = f"{task_type} 执行超时（>{timeout}s）"
        await db.update_log(log_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "timeout", duration, error_info)
        return None, tid, error_info

    except Exception as e:
        duration = time.time() - start
        error_info = str(e)
        await db.update_log(log_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "error", duration, error_info)
        return None, tid, error_info

    finally:
        await task_state.release()


# ─────────────────── 启动事件 ───────────────────

@app.on_event("startup")
async def startup():
    await db.connect()
    await db.init_db()
    print(f"[startup] 数据库初始化完成: {db.db_path}")


@app.on_event("shutdown")
async def shutdown():
    await db.close()


# ─────────────────── 接口：系统状态 ───────────────────

@app.get("/api/system/status")
async def get_system_status():
    """实时查询系统任务锁状态、服务连通性（无锁，常驻接口）"""
    try:
        import requests
        ollama_resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        llava_ok = ollama_resp.status_code == 200 and ("llava" in ollama_resp.text.lower() or "llama" in ollama_resp.text.lower())
    except Exception:
        llava_ok = False

    return ok({
        "task_state": task_state.state,
        "trace_id": task_state.trace_id,
        "llava_available": llava_ok,
        "db_path": str(db.db_path),
        "db_connected": db._conn is not None,
        "upload_dir": str(UPLOAD_DIR),
        "export_dir": str(EXPORT_DIR),
    })


@app.get("/api/system/health")
async def get_health():
    """检测模型、数据库、文件服务健康状态（常驻接口）"""
    issues = []
    # 数据库
    if not db._conn:
        issues.append("数据库未连接")
    # LLaVA
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        llava_ok = r.status_code == 200
        if not llava_ok:
            issues.append("LLaVA模型不可用")
    except Exception:
        llava_ok = False
        issues.append("LLaVA模型服务未响应")
    # 文件服务
    upload_ok = UPLOAD_DIR.exists()
    if not upload_ok:
        issues.append("上传目录异常")
    # 磁盘空间
    st = os.statvfs(str(EXPORT_DIR))
    free_gb = st.f_frsize * st.f_bavail / 1024 / 1024 / 1024
    if free_gb < 1:
        issues.append(f"磁盘空间不足（剩余{free_gb:.1f}GB）")

    return ok({
        "status": "healthy" if not issues else "degraded",
        "llava": llava_ok,
        "db": db._conn is not None,
        "upload_dir": upload_ok,
        "free_disk_gb": round(free_gb, 1),
        "issues": issues,
    })


# ─────────────────── 接口：CAD解析+报价（接口1） ───────────────────

@app.post("/api/analyze_full")
async def analyze_full(
    cad_file: UploadFile = File(None),
    quote_db: str = Form(None),
    project_name: str = Form("装修工程"),
):
    """
    接口1：CAD 文件解析 + 报价
    入参：cad_file=@xxx.dxf / @xxx.dwg / @xxx.pdf
    能力：解析空间、精准算量、自动报价
        - .dxf/.dwg → 矢量解析 (ezdxf)
        - .pdf     → 矢量路径解析 (优先) / 视觉识别 (回退)
    状态约束：仅idle可调用，占用cad_running锁
    """
    if not cad_file:
        return err(400, "请上传CAD文件（.dxf/.dwg/.pdf）")

    check_mixed_request(cad_file, None)

    content, ext = await check_file_gate(cad_file, MAX_CAD_SIZE, ALLOWED_CAD_EXT, "CAD")

    # 保存文件
    task_id = uuid.uuid4().hex[:12]
    save_path = UPLOAD_DIR / f"{task_id}_cad{ext}"
    save_path.write_bytes(content)

    # PDF 路径：矢量解析（优先）+ 视觉识别（回退）
    if ext == ".pdf":
        from pdf_parser import parse_pdf_vector
        from cad_parser import _parse_cad_pdf

        data, tid, error = await safe_run("cad", TIMEOUT_CAD, parse_pdf_vector, str(save_path))

        # 回退条件：矢量数为0 或 解析出错且无数据
        need_fallback = error or (data and data.get("vector_count", 0) == 0 and not data.get("spaces"))
        if need_fallback:
            fb_data, _, fb_error = await safe_run("cad", TIMEOUT_CAD, _parse_cad_pdf, str(save_path))
            if fb_error:
                return err(504, "PDF解析失败（矢量+视觉回退均失败）: " + fb_error, task_status=STATE_IDLE)
            if fb_data and fb_data.get("spaces"):
                data = fb_data
                data["parse_method"] = "PDF→图片→视觉识别（矢量回退）"

        if error and not data:
            return err(504, "PDF解析失败: " + error, task_status=STATE_IDLE)

    # DXF/DWG 路径（原有逻辑，完全不变）
    else:
        from cad_parser import _parse_dxf
        data, tid, error = await safe_run("cad", TIMEOUT_CAD, _parse_dxf, str(save_path))

    if error:
        return err(504, f"CAD解析失败: {error}", task_status=STATE_IDLE)

    if not data:
        return err(500, "CAD解析无结果返回", task_status=STATE_IDLE)

    # 计算报价
    spaces = data.get("spaces", data.get("data", []))
    if not spaces:
        return ok({"spaces": [], "base_price": 0, "total_area": 0, "space_count": 0})

    total_area = sum(s.get("area", s.get("area_sqm", 0)) for s in spaces)

    # 从数据库读取配置单价
    settings = await db.get_settings()
    unit_price = float(settings.get("base_unit_price", 9374))
    manage_rate = float(settings.get("manage_fee_rate", 0.05))
    tax_rate = float(settings.get("tax_rate", 0.03))

    base_price = total_area * unit_price
    manage_fee = base_price * manage_rate
    tax_fee = base_price * tax_rate
    final_price = base_price + manage_fee + tax_fee

    # 写数据库
    drawing_id = await db.add_drawing(cad_file.filename, str(save_path), len(content))
    for s in spaces:
        area = s.get("area", s.get("area_sqm", 0))
        length = s.get("length", s.get("dimensions", {}).get("width_m", 0))
        width = s.get("width", s.get("dimensions", {}).get("height_m", 0))
        await db.add_cad_result(drawing_id, s.get("name", ""), area, length, width)
    await db.update_drawing_parse(drawing_id, "completed", {"spaces_count": len(spaces), "total_area": total_area})

    result = {
        "drawing_id": drawing_id,
        "spaces": spaces,
        "space_count": len(spaces),
        "total_area": round(total_area, 2),
        "unit_price": unit_price,
        "base_price": round(base_price, 2),
        "manage_fee": round(manage_fee, 2),
        "tax_fee": round(tax_fee, 2),
        "final_price": round(final_price, 2),
        "project_name": project_name,
    }

    return ok(result, task_status=STATE_IDLE, trace_id=tid)


# ─────────────────── 接口：清理临时上传文件 ───────────────────

@app.post("/api/upload/clear")
async def upload_clear():
    """清空前端未提交的临时上传文件"""
    if task_state.state != STATE_IDLE:
        return err(409, f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作")
    import time
    now = time.time()
    deleted = 0
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in ('.dxf', '.dwg', '.jpg', '.jpeg', '.png', '.webp'):
            fname = f.name
            # 只删文件名不含数据库记录ID标记的临时文件（上传但未解析的）
            if not any(id_prefix in fname for id_prefix in ['_cad', '_img', '_test', '_processed']):
                f.unlink(missing_ok=True)
                deleted += 1
            # 也删掉被reset标记的临时文件
            elif fname.startswith('temp_'):
                f.unlink(missing_ok=True)
                deleted += 1
    return ok({"deleted_count": deleted})


# ─────────────────── 接口：效果图识别（接口2） ───────────────────

@app.post("/api/analyze")
async def analyze_image(
    image_file: UploadFile = File(None),
):
    """
    接口2：单张效果图材质/空间同步识别
    入参：image_file=@效果图.jpg
    能力：LLaVA识别材质、空间、软装
    状态约束：仅idle可调用，占用ai_running锁
    """
    if not image_file:
        return err(400, "请上传效果图（jpg/png/webp）")

    content, ext = await check_file_gate(image_file, MAX_IMG_SIZE, ALLOWED_IMG_EXT, "图片")

    task_id = uuid.uuid4().hex[:12]
    save_path = UPLOAD_DIR / f"{task_id}_img{ext}"
    save_path.write_bytes(content)

    # ── 图片预处理：缩放/压缩/去EXIF ──
    processed_path = preprocess_image(str(save_path), output_dir=str(UPLOAD_DIR))
    stats = preprocess_image_stats(str(save_path), processed_path)
    print(f"[image_preprocessor] {image_file.filename}: "
          f"{stats['original_size_kb']}KB -> {stats['processed_size_kb']}KB "
          f"({stats['compression_ratio']}% reduction)")

    # 读取当前配置的视觉模型
    settings = await db.get_settings()
    vl_model = settings.get("active_vl_model", "llava:7b")

    # 从数据库查询自定义模型的完整配置
    custom_models = await db.get_custom_vl_models()
    model_info = next((cm for cm in custom_models if cm["model_key"] == vl_model), None)
    model_type = model_info.get("model_type") if model_info else None
    api_base_url = model_info.get("api_base_url") if model_info else None
    api_token = model_info.get("api_token") if model_info else None

    data, tid, error = await safe_run("ai", TIMEOUT_AI, recognize_with_fallback,
                                      processed_path, vl_model,
                                      model_type=model_type,
                                      api_base_url=api_base_url,
                                      api_token=api_token)

    if error:
        return err(504, f"AI识别失败: {error}", task_status=STATE_IDLE, trace_id=tid)

    if not data:
        return err(500, "AI识别无结果", task_status=STATE_IDLE, trace_id=tid)

    # 解析结构化数据（v2.0格式）
    structured = data.get("structured", {})
    recognized_space = structured.get("space_type", "")
    wall_mat = structured.get("wall_material", "")
    floor_mat = structured.get("floor_material", "")
    ceiling_mat = structured.get("ceiling_material", "")
    decor_style = structured.get("decor_style", "")
    remark = structured.get("remark", "")
    model_used = data.get("model_used", vl_model)
    success = data.get("success", False)

    if not recognized_space and not data.get("error"):
        # 兼容旧格式：尝试从 spaces[0] 提取
        spaces_list = data.get("spaces", [])
        first_space = spaces_list[0] if spaces_list else {}
        recognized_space = first_space.get("type", first_space.get("space", ""))
        mats = first_space.get("materials", {})
        wall_mat = mats.get("wall", wall_mat)
        floor_mat = mats.get("floor", floor_mat)
        ceiling_mat = mats.get("ceiling", ceiling_mat)
        decor_style = data.get("overall_style", decor_style)

    # 构造完整 material_info
    material_info = {
        "wall": wall_mat,
        "floor": floor_mat,
        "ceiling": ceiling_mat,
        "style": decor_style,
        "remark": remark,
        "model_used": model_used,
    }

    confidence = 0.85 if recognized_space else (0.5 if success else 0)

    img_id = await db.add_image_result(
        str(save_path),
        recognized_space=recognized_space,
        material_info=material_info,
        confidence=confidence,
    )

    result = {
        "image_result_id": img_id,
        "filename": image_file.filename,
        "recognized_space": recognized_space,
        "wall_material": wall_mat,
        "floor_material": floor_mat,
        "ceiling_material": ceiling_mat,
        "decor_style": decor_style,
        "remark": remark,
        "confidence": confidence,
        "model_used": model_used,
        "structured": structured,
    }

    if not success and data.get("error"):
        result["warning"] = data["error"]

    return ok(result, task_status=STATE_IDLE, trace_id=tid)


# ─────────────────── 接口：视觉识别独立测试（诊断用） ───────────────────
@app.post("/api/vision_test")
@app.post("/api/vision_test")
async def vision_test(
    image_file: UploadFile = File(None),
    model: str = Form(""),
    crop_enabled: str = Form("true"),
    data: str = Form(default="{}")  # ✅ 前端 JSON 字符串
):
    logger.info("🚀 /api/vision_test called")
    logger.info("📷 filename=%s", image_file.filename)
    logger.info("🧠 raw data param=%s", data)  # ✅ 打字符串，不打 .get()

    # ✅ 解析前端传来的 structured 标志（安全）
    structured_flag = False
    try:
        parsed_data = json.loads(data)
        structured_flag = parsed_data.get("structured", False)
        logger.info("🧠 parsed structured flag=%s", structured_flag)
    except Exception as e:
        logger.warning("⚠️ data JSON 解析失败: %s", e)

    if not image_file:
        return err(400, "请上传图片（jpg/png/webp）")

    content, ext = await check_file_gate(image_file, MAX_IMG_SIZE, ALLOWED_IMG_EXT, "图片")
    task_id = uuid.uuid4().hex[:8]
    save_path = UPLOAD_DIR / f"{task_id}_test{ext}"
    save_path.write_bytes(content)

    t_total = time.time()
    timings = {}

    # 步骤1：图像预处理
    t0 = time.time()
    from image_preprocessor import preprocess_image, preprocess_image_stats
    processed_path = preprocess_image(str(save_path), output_dir=str(UPLOAD_DIR))
    stats = preprocess_image_stats(str(save_path), processed_path)
    timings["preprocess"] = round(time.time() - t0, 3)

    # 步骤2：模型推理
    t0 = time.time()
    from image_recognizer import recognize_with_fallback

    if model:
        vl_model = model
    else:
        settings = await db.get_settings()
        vl_model = settings.get("active_vl_model", "qwen2.5:7b")

    # 从数据库查询自定义模型的完整配置
    custom_models = await db.get_custom_vl_models()
    model_info = next((cm for cm in custom_models if cm["model_key"] == vl_model), None)
    vl_model_type = model_info.get("model_type") if model_info else None
    vl_api_base_url = model_info.get("api_base_url") if model_info else None
    vl_api_token = model_info.get("api_token") if model_info else None
    vl_api_format = model_info.get("api_format") if model_info else None

    use_crop = crop_enabled.lower() in ("true", "1", "yes")

        # ✅ 关键：不要用 data 这个名字存识别结果
    if use_crop:
        from crop_recognizer import CropRecognizer
        recognizer = CropRecognizer(
            model_type=vl_model_type,
            api_base_url=vl_api_base_url,
            api_token=vl_api_token,
            api_format=vl_api_format,
        )
        recognition_result = recognizer.recognize_with_crop(
            image_path=processed_path,
            model=vl_model,
            upload_dir=UPLOAD_DIR,
            task_id=task_id,
        )
    else:
        recognition_result = recognize_with_fallback(
            processed_path, vl_model,
            model_type=vl_model_type,
            api_base_url=vl_api_base_url,
            api_token=vl_api_token,
            api_format=vl_api_format,
        )
        recognition_result["_crop_mode"] = "disabled"

    timings["inference"] = round(time.time() - t0, 3)
    t_total = round(time.time() - t_total, 3)

    from vision_harness.similarity import get_expect_pretect, evaluate_similarity

    # ✅ 从识别结果中取 structured
    expected, predicted = get_expect_pretect(
        image_file.filename,
        recognition_result.get("structured", {})
    )

    similarity_json = evaluate_similarity(expected, predicted)

    # 清理临时文件
    try:
        os.remove(save_path)
        os.remove(processed_path)
    except Exception:
        pass

    try:
        from db import db as _db
        settings_data = await _db.get_settings()
        available = settings_data.get("available_vl_models", [])
    except Exception:
        available = []

    result = {
        "timings": {
            "preprocess": timings["preprocess"],
            "inference": timings["inference"],
            "total": t_total,
        },
        "model_used": vl_model,
        "available_models": available,
        "image_info": {
            "filename": image_file.filename,
            "original_size_kb": round(stats["original_size_kb"], 1),
            "processed_size_kb": round(stats["processed_size_kb"], 1),
        },
        "raw_result": recognition_result,
        "similarity": similarity_json,
    }
    logger.info("📤 vision_test response: expected=%s, predicted=%s", expected, predicted)
    return ok(result)
   
@app.post("/api/analyze_pdf")
async def analyze_pdf(pdf_file: UploadFile = File(None)):
    """PDF施工图识别：PDF→图片→复用LLaVA识别"""
    if not pdf_file:
        return err(400, "请上传PDF文件")

    content, ext = await check_file_gate(pdf_file, MAX_PDF_SIZE, ALLOWED_PDF_EXT, "PDF")

    import fitz  # PyMuPDF
    task_id = uuid.uuid4().hex[:12]
    pdf_path = UPLOAD_DIR / f"{task_id}_src.pdf"
    pdf_path.write_bytes(content)

    # 逐页转图
    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(2, 2)  # 2x缩放 提高清晰度
        pix = page.get_pixmap(matrix=mat)
        img_path = UPLOAD_DIR / f"{task_id}_p{page_num}.jpg"
        pix.save(str(img_path))
        pages.append(str(img_path))
    doc.close()

    if not pages:
        return err(400, "PDF为空或无法渲染")

    # 对每一页做识别（只认第一页返回详细结构，其余统计）
    settings = await db.get_settings()
    vl_model = settings.get("active_vl_model", "llava:7b")

    results = []
    for i, img_path in enumerate(pages):
        processed = preprocess_image(img_path, output_dir=str(UPLOAD_DIR))
        data, tid, error = await safe_run("ai", TIMEOUT_AI, recognize_with_fallback, processed, vl_model)
        page_result = {
            "page": i + 1,
            "total_pages": len(pages),
        }
        if error:
            page_result["error"] = error
        elif data:
            structured = data.get("structured", {})
            page_result["recognized_space"] = structured.get("space_type", "")
            page_result["wall_material"] = structured.get("wall_material", "")
            page_result["floor_material"] = structured.get("floor_material", "")
            page_result["ceiling_material"] = structured.get("ceiling_material", "")
            page_result["confidence"] = data.get("success", False)
        results.append(page_result)

    return ok({
        "filename": pdf_file.filename,
        "total_pages": len(pages),
        "results": results,
    }, task_status=STATE_IDLE, trace_id=tid)


# ─────────────────── 接口：CAD 解析误差评估（对比真实值） ───────────────────
    
@app.post("/api/cad_test")
async def cad_test(
    cad_result: str = Form(""),
    ground_truth_json: str = Form(""),
):
    """
    CAD 解析结果与真实值对比评估
    
    Args:
        cad_result: JSON 字符串，CAD 解析结果（包含 spaces 列表）
        ground_truth_json: JSON 字符串，真实值数据
    
    Returns:
        每个空间的面积误差、百分比误差等评估信息
    """
    
    from vision_harness.cad_metrics import evaluate_cad_evaluations
    
    try:
        cad_data = json.loads(cad_result) if cad_result else {}
        true_data = json.loads(ground_truth_json) if ground_truth_json else {}
    except json.JSONDecodeError as e:
        return err(400, f"JSON 格式错误: {e}")
    
    # 提取 spaces 列表
    predict_spaces = []
    predict_spaces = cad_data["spaces"]
    
    if not predict_spaces:
        return err(400, "CAD 结果中未找到 predict_spaces 数据")
    
    # 构建真实值查找表：name -> area, perimeter
    true_map = {}
    true_spaces = true_data.get("spaces", [])
    for item in true_spaces:
        name = item.get("name")
        true_map[name] = {
            "area_sqm": item.get("area_sqm"), 
            "perimeter_m": item.get("perimeter_m")
        }       
    
    # 计算每个空间的误差
    raw_data = []
    
    for space in predict_spaces:
        # 读取预测值
        name = space.get("name") or "未知空间"
        predict_area = float(space.get("area_sqm") or 0)
        predict_perimeter = space.get("perimeter_m")
        
        # 读取测试值
        true_area = None
        true_perimeter = None
        if true_map.get(name):
            true_area = true_map.get(name).get("area_sqm")
            true_perimeter = true_map.get(name).get("perimeter_m")
        
        error_info = {
            "name": name,
            "predict_area": predict_area,
            "true_area": true_area,
            "predict_perimeter": predict_perimeter,
            "true_perimeter": true_perimeter,
        }
        
        raw_data.append(error_info)
    
    cad_evaluations = evaluate_cad_evaluations(raw_data)

    result = {
        "total_spaces": len(raw_data),
        "raw_data": raw_data,
        "cad_evaluations": cad_evaluations,
    }
    
    return ok(result)
   
# ─────────────────── 接口：数据融合 ───────────────────

@app.post("/api/data_merge")
async def data_merge(
    cad_result_id: int = Form(...),
    image_result_ids: str = Form("[]"),
    manual_bindings: str = Form("[]"),
):
    """
    接口3：CAD工程量 + 已确认材质数据融合
    入参：cad_result_id, image_result_ids, manual_bindings(人工绑定)
    状态约束：仅idle可调用，占用merge_running锁
    """
    img_ids = json.loads(image_result_ids) if isinstance(image_result_ids, str) else image_result_ids
    bindings = json.loads(manual_bindings) if isinstance(manual_bindings, str) else manual_bindings

    # 读CAD数据
    cad_rows = await db.get_cad_results(cad_result_id)
    if not cad_rows:
        return err(422, "CAD数据为空或不完整，无法执行融合")

    # 读图片识别数据
    image_rows = await db.get_image_results(img_ids) if img_ids else []

    tid = ""
    try:
        ok_flag, tid = await task_state.acquire("merge")
        if not ok_flag:
            return err(409, f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作")

        # 执行融合逻辑
        total_area = sum(r.get("area", 0) for r in cad_rows)

        # 获取配置
        settings = await db.get_settings()
        unit_price = float(settings.get("base_unit_price", 9374))
        manage_rate = float(settings.get("manage_fee_rate", 0.05))
        tax_rate = float(settings.get("tax_rate", 0.03))
        loss_rate = float(settings.get("loss_rate", 0.03))

        # 基础报价
        base_price = total_area * unit_price

        # ── 材质匹配：CAD 空间名 ↔ AI 识别空间名（同义词智能匹配） ──

        # 构建 AI 图片材质索引：recognized_space → material_info
        ai_material_index = {}
        for img in image_rows:
            raw_space = img.get("recognized_space", "").strip()
            if not raw_space:
                continue
            # AI输出归一化：将模型输出的空间名通过space_synonyms标准化
            # 例如 "卧室" → "次卧", "大厅" → "客厅"
            space = space_synonyms.normalize_name(raw_space) or raw_space
            mat = img.get("material_info", {})
            if isinstance(mat, str):
                try:
                    mat = json.loads(mat)
                except Exception:
                    mat = {}
            # 多个图识别同空间时取最新的
            if space not in ai_material_index or img["id"] > ai_material_index[space].get("image_id", 0):
                ai_material_index[space] = {
                    "image_id": img["id"],
                    "materials": mat,
                    "confidence": img.get("confidence", 0),
                }

        # 构建手动绑定索引：cad_space_name → material_info
        manual_index = {}
        for b in bindings:
            if isinstance(b, dict):
                cad_name = b.get("cad_name", "") or b.get("space_name", "")
                mat_info = b.get("material_info", b.get("materials", {}))
                if cad_name:
                    manual_index[cad_name] = mat_info

        # 为每个 CAD 空间匹配材质
        space_material_map = {}  # cad_space_name → (materials, source, image_id, confidence)
        for r in cad_rows:
            cad_name = r.get("space_name", "")
            if not cad_name:
                continue

            # 1. 优先使用 manual_bindings（人工绑定兜底）
            if cad_name in manual_index:
                space_material_map[cad_name] = {
                    "materials": manual_index[cad_name],
                    "source": "manual",
                    "image_id": None,
                    "confidence": 1.0,
                }
                continue

            # 2. 尝试同义词智能匹配
            matched = None
            for ai_space, ai_data in ai_material_index.items():
                if space_synonyms.match_space_name(cad_name, ai_space):
                    matched = ai_data
                    break

            if matched:
                space_material_map[cad_name] = {
                    "materials": matched["materials"],
                    "source": "ai",
                    "image_id": matched["image_id"],
                    "confidence": matched["confidence"],
                }
            else:
                space_material_map[cad_name] = {
                    "materials": {},
                    "source": "",
                    "image_id": None,
                    "confidence": 0,
                }

        # 材质差价（按空间匹配结果逐项估算）
        material_diff = 0

        # 读取定价模板用于自动匹配项目单价
        pricing_items = await db.get_pricing_items()
        # 构建价格索引
        price_index = {}
        for pi in sorted(pricing_items, key=lambda x: x.get("id", 0)):
            st = pi.get("surface_type", "")
            name = pi.get("item_name", "")
            mat_p = pi.get("unit_price_material", 0) or 0
            lab_p = pi.get("unit_price_labor", 0) or 0
            if st not in ("wall", "floor", "ceiling"):
                continue
            for kw in ["乳胶漆", "瓷砖", "墙纸", "木饰面", "地砖", "地板",
                        "实木地板", "复合地板", "大理石", "石膏板", "铝扣板"]:
                if kw in name and (st, kw) not in price_index:
                    price_index[(st, kw)] = {"material": mat_p, "labor": lab_p}

        def _auto_match_price(category, material_name):
            surface_map = {"墙面工程": "wall", "地面工程": "floor", "吊顶工程": "ceiling"}
            st = surface_map.get(category, "")
            if not st or not material_name:
                return None
            for kw in ["乳胶漆", "瓷砖", "墙纸", "木饰面", "地砖", "地板",
                        "实木地板", "复合地板", "大理石", "石膏板", "铝扣板"]:
                if kw in material_name:
                    match = price_index.get((st, kw))
                    if match:
                        return match
            return None

        for r in cad_rows:
            cad_name = r.get("space_name", "")
            space_area = r.get("area", 0)
            sm = space_material_map.get(cad_name, {})
            mat = sm.get("materials", {})
            wall_mat = str(mat.get("wall", mat.get("墙面材质", "")))
            floor_mat = str(mat.get("floor", mat.get("地面材质", "")))
            ceiling_mat = str(mat.get("ceiling", mat.get("顶面材质", "")))
            # 墙面材质差价（相对于基础乳胶漆18元/㎡）
            WALL_BASE = 18
            wall_premium = {"瓷砖": 45, "大理石": 90, "墙布": 30, "墙纸": 30,
                           "壁纸": 30, "木饰面": 90, "岩板": 120, "护墙板": 90}
            for kw, price in wall_premium.items():
                if kw in wall_mat:
                    material_diff += space_area * 0.6 * (price - WALL_BASE)
                    break
            # 地面材质差价（相对于基础地砖铺贴45元/㎡）
            FLOOR_BASE = 45
            floor_premium = {"实木地板": 120, "复合地板": 60, "地板": 60,
                           "大理石": 260, "地毯": 80, "岩板": 200}
            for kw, price in floor_premium.items():
                if kw in floor_mat:
                    material_diff += space_area * 0.3 * (price - FLOOR_BASE)
                    break
            # 顶面材质差价（相对于基础石膏板吊顶60元/㎡）
            CEIL_BASE = 60
            ceil_premium = {"铝扣板": 50, "蜂窝大板": 100, "集成吊顶": 50,
                          "木饰面": 100, "造型吊顶": 80, "格栅吊顶": 80}
            for kw, price in ceil_premium.items():
                if kw in ceiling_mat:
                    diff = price - CEIL_BASE
                    if diff > 0:
                        material_diff += space_area * 1.0 * diff

        loss_price = base_price * loss_rate
        process_add_price = total_area * 5  # 基础造型费
        manage_fee = base_price * manage_rate
        tax_fee = (base_price + material_diff + loss_price + manage_fee) * tax_rate
        final_price = base_price + material_diff + process_add_price + loss_price + manage_fee + tax_fee

        # 生成分项明细（按空间聚合材质信息）
        items = []
        # 工序映射：工种分类 → 工序名称
        CATEGORY_PROCESS_MAP = {
            "拆除工程": "拆除工程",
            "墙面工程": "油漆工程",
            "地面工程": "瓦工工程",
            "吊顶工程": "木工工程",
            "门窗工程": "安装工程",
            "窗户工程": "安装工程",
            "给排水工程": "水电改造",
            "电气工程": "安装工程",
            "垃圾清运": "保洁收尾",
            "防水工程": "防水工程",
        }
        # 读取工序列表用于映射ID
        sys_procs = await db.get_processes()
        proc_name_to_id = {p["name"]: p["id"] for p in sys_procs}
        for r in cad_rows:
            cad_name = r.get("space_name", "")
            space_area = r.get("area", 0)
            wall_area = space_area * 2.5
            sm = space_material_map.get(cad_name, {})
            mat = sm.get("materials", {})
            mat_source = sm.get("source", "")

            wall_mat_name = str(mat.get("wall", mat.get("墙面材质", "乳胶漆")))
            floor_mat_name = str(mat.get("floor", mat.get("地面材质", "地砖")))

            # 墙面项
            source_label = f"CAD工程量 + AI材质识别{'(人工绑定)' if mat_source == 'manual' else ''}" if mat_source else "CAD工程量"
            wall_match = _auto_match_price("墙面工程", wall_mat_name)
            wall_mat_price = wall_match["material"] if wall_match else 18
            wall_lab_price = wall_match["labor"] if wall_match else 22
            items.append({
                "space_name": cad_name,
                "category": "墙面工程",
                "project_name": f"{wall_mat_name}墙面",
                "quantity": round(wall_area, 2),
                "unit": "㎡",
                "material_unit_price": wall_mat_price,
                "labor_unit_price": wall_lab_price,
                "subtotal": round(wall_area * (wall_mat_price + wall_lab_price), 2),
                "source": source_label,
                "material_name": wall_mat_name,
                "material_source": mat_source,
                "process_name": CATEGORY_PROCESS_MAP.get("墙面工程", ""),
                "process_id": proc_name_to_id.get(CATEGORY_PROCESS_MAP.get("墙面工程", ""), 0),
            })
            # 地面项
            floor_match = _auto_match_price("地面工程", floor_mat_name)
            floor_mat_price = floor_match["material"] if floor_match else 45
            floor_lab_price = floor_match["labor"] if floor_match else 35
            items.append({
                "space_name": cad_name,
                "category": "地面工程",
                "project_name": f"{floor_mat_name}铺贴",
                "quantity": round(space_area, 2),
                "unit": "㎡",
                "material_unit_price": floor_mat_price,
                "labor_unit_price": floor_lab_price,
                "subtotal": round(space_area * (floor_mat_price + floor_lab_price), 2),
                "source": source_label,
                "material_name": floor_mat_name,
                "material_source": mat_source,
                "process_name": CATEGORY_PROCESS_MAP.get("地面工程", ""),
                "process_id": proc_name_to_id.get(CATEGORY_PROCESS_MAP.get("地面工程", ""), 0),
            })

        # ── 去重聚合：相同空间+相同类目的分项合并 ──
        merged = OrderedDict()
        for it in items:
            key = (it.get("space_name", ""), it.get("category", ""), it.get("project_name", ""))
            if key in merged:
                merged[key]["quantity"] = round(merged[key]["quantity"] + it["quantity"], 2)
                merged[key]["subtotal"] = round(merged[key]["subtotal"] + it["subtotal"], 2)
                src = it.get("source", "")
                if src and src not in merged[key].get("source", ""):
                    merged[key]["source"] = merged[key].get("source", "") + " + " + src
            else:
                merged[key] = dict(it)
        items = sorted(merged.values(), key=lambda x: (
            {"墙面工程": 0, "地面工程": 1, "吊顶工程": 2}.get(x.get("category", ""), 9),
            x.get("project_name", "")
        ))

        trace = {
            "cad_result_id": cad_result_id,
            "image_result_ids": img_ids,
            "bindings": bindings,
            "settings": settings,
            "fusion_time": datetime.now().isoformat(),
        }

        # 存报价
        quote_id = await db.add_quote(
            cad_result_id, img_ids,
            round(base_price, 2), round(material_diff, 2),
            round(process_add_price, 2), round(loss_price, 2),
            round(manage_fee, 2), round(tax_fee, 2), round(final_price, 2),
            items, trace
        )

        # 更新AI识别确认状态
        for img in image_rows:
            await db.update_image_confirm(img["id"], "confirmed")

        # 记录操作日志
        await db.add_log(
            task_type="merge",
            operation_action=f"数据融合: quote_id={quote_id}, cad_result_id={cad_result_id}, {len(cad_rows)}个空间, 总计¥{final_price:.0f}",
            lock_status="idle",
            trace_id=tid,
            run_status="success",
        )

        return ok({
            "quote_id": quote_id,
            "base_price": round(base_price, 2),
            "material_diff_price": round(material_diff, 2),
            "process_add_price": round(process_add_price, 2),
            "loss_price": round(loss_price, 2),
            "manage_fee": round(manage_fee, 2),
            "tax_fee": round(tax_fee, 2),
            "final_price": round(final_price, 2),
            "items": items,
            "space_count": len(cad_rows),
            "total_area": round(total_area, 2),
        }, task_status=STATE_IDLE, trace_id=tid)

    except Exception as e:
        return err(500, f"融合失败: {str(e)}", task_status=STATE_IDLE, trace_id=tid)
    finally:
        await task_state.release()


# ─────────────────── 接口：报价项编辑+重算 ───────────────────

@app.put("/api/quote/{quote_id}/items")
async def update_quote_items(quote_id: int, body: dict):
    """
    更新报价明细项并自动重算汇总金额
    入参：{"items": [...]}
    每个 item 支持修改: quantity, material_unit_price, labor_unit_price,
                        material_name, project_name, category
    自动匹配 pricing_items 获取标准单价（用户可覆盖）
    """
    quote = await db.get_quote(quote_id)
    if not quote:
        return err(404, "报价记录不存在")

    tid = ""
    try:
        ok_flag, tid = await task_state.acquire("merge")
        if not ok_flag:
            return err(409, f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作")

        updated = body.get("items", [])
        if not updated:
            return err(422, "缺少 items 参数")

        # 读取定价模板用于自动匹配单价
        pricing_items = await db.get_pricing_items()
        settings = await db.get_settings()
        loss_rate = float(settings.get("loss_rate", 0.03))
        manage_rate = float(settings.get("manage_fee_rate", 0.05))
        tax_rate = float(settings.get("tax_rate", 0.03))

        # 构建定价索引：surface_type + material_name_keyword → unit_price
        # 如 wall+乳胶漆 → (18, 22), floor+地砖 → (45, 35)
        # 按id排序取最早（非删除）的匹配项
        price_index = {}  # (surface_type, keyword) → {material: ..., labor: ..., total: ...}
        for pi in sorted(pricing_items, key=lambda x: x.get("id", 0)):
            st = pi.get("surface_type", "")
            name = pi.get("item_name", "")
            mat = pi.get("unit_price_material", 0) or 0
            lab = pi.get("unit_price_labor", 0) or 0
            if st not in ("wall", "floor", "ceiling"):
                continue
            for kw in ["乳胶漆", "瓷砖", "墙纸", "木饰面", "地砖", "地板",
                        "实木地板", "复合地板", "大理石", "石膏板", "铝扣板"]:
                if kw in name and (st, kw) not in price_index:
                    price_index[(st, kw)] = {"material": mat, "labor": lab}

        def _auto_match_price(category, material_name):
            """根据类别和材质名自动匹配单价"""
            surface_map = {"墙面工程": "wall", "地面工程": "floor", "吊顶工程": "ceiling"}
            st = surface_map.get(category, "")
            if not st or not material_name:
                return None
            for kw in ["乳胶漆", "瓷砖", "墙纸", "木饰面", "地砖", "地板",
                        "实木地板", "复合地板", "大理石", "石膏板", "铝扣板"]:
                if kw in material_name:
                    match = price_index.get((st, kw))
                    if match:
                        return match
            return None

        # 处理每个 item
        for item in updated:
            qty = float(item.get("quantity", 0))
            mat_name = item.get("material_name", "")
            cat = item.get("category", "")

            # 自动匹配单价（用户未手动修改时）
            if "material_unit_price" not in item or item.get("_auto_priced", True):
                match = _auto_match_price(cat, mat_name)
                if match:
                    item["material_unit_price"] = match["material"]
                    item["labor_unit_price"] = match["labor"]
                    item["_auto_priced"] = True

            mat_price = float(item.get("material_unit_price", 0) or 0)
            lab_price = float(item.get("labor_unit_price", 0) or 0)
            item["subtotal"] = round(qty * (mat_price + lab_price), 2)

        # 重算汇总
        base_price = sum(
            float(i.get("subtotal", 0)) for i in updated
        )
        material_diff = 0  # 已含在 item 单价中，无需额外计算
        process_add = sum(
            float(i.get("subtotal", 0)) for i in updated if "造型" in i.get("project_name", "")
        )
        loss_price = base_price * loss_rate
        manage_fee = base_price * manage_rate
        tax_fee = (base_price + loss_price + manage_fee) * tax_rate
        final_price = base_price + loss_price + manage_fee + tax_fee

        totals = {
            "base_price": round(base_price, 2),
            "material_diff_price": round(material_diff, 2),
            "process_add_price": round(process_add, 2),
            "loss_price": round(loss_price, 2),
            "manage_fee": round(manage_fee, 2),
            "tax_fee": round(tax_fee, 2),
            "final_price": round(final_price, 2),
        }

        trace = {
            "previous_items_count": len(quote.get("quote_detail_json", [])),
            "updated_items_count": len(updated),
            "update_time": datetime.now().isoformat(),
            "settings": settings,
        }

        await db.update_quote_items(quote_id, updated, totals, trace)

        # 记录操作日志
        tid_log = uuid.uuid4().hex[:12]
        await db.add_log(
            task_type="manual_edit",
            operation_action=f"报价编辑: quote_id={quote_id}, {len(updated)}项, 总计¥{totals['final_price']:.0f}",
            lock_status="idle",
            trace_id=tid_log,
            run_status="success",
        )

        return ok({
            "quote_id": quote_id,
            **totals,
            "items": updated,
        }, task_status=STATE_IDLE, trace_id=tid)

    except Exception as e:
        return err(500, f"编辑报价失败: {str(e)}", task_status=STATE_IDLE, trace_id=tid)
    finally:
        await task_state.release()


# ─────────────────── 接口：Excel导出 ───────────────────

@app.post("/api/export_excel")
async def export_excel(
    quote_id: int = Form(...),
):
    """
    接口4：生成4Sheet报价Excel
    入参：quote_id
    状态约束：仅idle可调用，占用export_running锁
    """
    quote = await db.get_quote(quote_id)
    if not quote:
        return err(422, "报价记录不存在")

    tid = ""
    try:
        ok_flag, tid = await task_state.acquire("export")
        if not ok_flag:
            return err(409, f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作")

        # 读取CAD数据补充到Excel
        cad_rows = await db.get_cad_results(quote.get("cad_result_id", 0))

        # 构建Excel数据
        excel_data = {
            "project_name": quote.get("project_name", "智能报价单"),
            "create_time": quote.get("create_time", ""),
            "rule_version": "v1.0",
            "base_price": quote.get("base_price", 0),
            "material_diff_price": quote.get("material_diff_price", 0),
            "process_add_price": quote.get("process_add_price", 0),
            "loss_price": quote.get("loss_price", 0),
            "manage_fee": quote.get("manage_fee", 0),
            "tax_fee": quote.get("tax_fee", 0),
            "final_price": quote.get("final_price", 0),
            "items": quote.get("quote_detail_json", []),
            "cad_data": cad_rows,
            "material_data": [],
        }

        # 补充材质数据
        img_ids = quote.get("image_result_ids", [])
        if img_ids:
            img_rows = await db.get_image_results(img_ids)
            excel_data["material_data"] = [
                {
                    "space_name": r.get("recognized_space", ""),
                    "material_info": r.get("material_info", {}),
                    "confidence": r.get("confidence", 0),
                }
                for r in img_rows
            ]

        filepath = export_quote_excel(excel_data)

        # 更新导出路径
        await db.update_quote_export(quote_id, filepath)

        # 记录操作日志
        await db.add_log(
            task_type="export",
            operation_action=f"Excel导出: quote_id={quote_id}, 文件={Path(filepath).name}",
            lock_status="idle",
            trace_id=tid,
            run_status="success",
        )

        return ok({
            "quote_id": quote_id,
            "export_path": filepath,
            "filename": Path(filepath).name,
            "sheets": ["报价总表", "分项明细", "工程量清单", "材质清单"],
        }, task_status=STATE_IDLE, trace_id=tid)

    except Exception as e:
        return err(500, f"导出失败: {str(e)}", task_status=STATE_IDLE, trace_id=tid)
    finally:
        await task_state.release()


@app.get("/api/download_excel/{quote_id}")
async def download_excel(quote_id: int):
    """直接返回Excel文件二进制流供前端下载"""
    quote = await db.get_quote(quote_id)
    if not quote:
        return err(422, "报价记录不存在")
    filepath = quote.get("export_filepath") or quote.get("export_path") or ""
    if not filepath or not os.path.exists(filepath):
        # 尝试重新生成
        try:
            ok_flag, tid = await task_state.acquire("export")
            if not ok_flag:
                return err(409, "系统正忙，请稍后重试")
            cad_rows = await db.get_cad_results(quote.get("cad_result_id", 0))
            excel_data = {
                "project_name": quote.get("project_name", "智能报价单"),
                "create_time": quote.get("create_time", ""),
                "rule_version": "v1.0",
                "base_price": quote.get("base_price", 0),
                "material_diff_price": quote.get("material_diff_price", 0),
                "process_add_price": quote.get("process_add_price", 0),
                "loss_price": quote.get("loss_price", 0),
                "manage_fee": quote.get("manage_fee", 0),
                "tax_fee": quote.get("tax_fee", 0),
                "final_price": quote.get("final_price", 0),
                "items": quote.get("quote_detail_json", []),
                "cad_data": cad_rows,
                "material_data": [],
            }
            img_ids = quote.get("image_result_ids", [])
            if img_ids:
                img_rows = await db.get_image_results(img_ids)
                excel_data["material_data"] = [{"space_name": r.get("recognized_space", ""), "material_info": r.get("material_info", {}), "confidence": r.get("confidence", 0)} for r in img_rows]
            filepath = export_quote_excel(excel_data)
            await db.update_quote_export(quote_id, filepath)
        except Exception as e:
            return err(500, f"生成Excel失败: {str(e)}")
        finally:
            await task_state.release()
    if not os.path.exists(filepath):
        return err(500, "Excel文件不存在，生成失败")
    filename = Path(filepath).name
    # 记录导出日志
    try:
        await db.add_log("export", operation_action=f"文件下载: quote_id={quote_id}, 文件={filename}", lock_status="idle", run_status="success")
    except:
        pass
    return FileResponse(filepath, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─────────────────── 接口：历史记录 ───────────────────

@app.get("/api/history")
async def history_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页查询所有历史任务列表（只读，无锁）"""
    quotes = await db.get_quotes(page, page_size)
    logs = await db.get_logs(page, page_size)
    return ok({
        "quotes": quotes,
        "logs": logs,
    })


@app.get("/api/history/{task_id}")
async def history_detail(task_id: int):
    """查询单条报价详情（只读，无锁）"""
    quote = await db.get_quote(task_id)
    if not quote:
        return err(404, "报价记录不存在")
    # 补充CAD和图片数据
    cad_rows = await db.get_cad_results(quote.get("cad_result_id", 0))
    img_ids = quote.get("image_result_ids", [])
    img_rows = await db.get_image_results(img_ids) if img_ids else []
    return ok({
        "quote": quote,
        "cad_data": cad_rows,
        "image_data": img_rows,
    })


@app.delete("/api/history/{task_id}")
async def history_delete(task_id: int):
    """删除历史记录（逻辑删除，仅空闲可执行）"""
    if task_state.state != STATE_IDLE:
        return err(409, f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作")
    await db.execute("UPDATE quote_records SET is_deleted=1 WHERE id=?", (task_id,))
    return ok({"deleted_id": task_id})


# ─────────────────── 接口：操作日志 ───────────────────

@app.get("/api/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """查询操作日志（只读，无锁）"""
    logs = await db.get_logs(page, page_size)
    return ok({"logs": logs})


# ─────────────────── 接口：定价配置 ───────────────────

@app.get("/api/settings/pricing")
async def get_pricing():
    """查询当前定价配置（只读，无锁）"""
    settings = await db.get_settings()
    return ok(settings)


@app.post("/api/settings/pricing")
async def update_pricing(
    key: str = Form(...),
    value: str = Form(...),
):
    """修改定价配置（仅空闲可执行，操作留痕）"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法修改配置")
    if key not in {
        "base_unit_price", "manage_fee_rate", "tax_rate", "loss_rate",
        "deduct_door", "deduct_window", "deduct_sliding_door", "deduct_bg_wall",
        "wall_area_factor", "ceiling_factor",
    }:
        return err(400, f"无效的配置项: {key}")
    await db.update_setting(key, value)
    settings = await db.get_settings()
    return ok(settings, message=f"配置 {key} 已更新为 {value}")


# ─────────────────── 接口：视觉模型管理 ───────────────────

VL_MODEL_OPTIONS = {
    "llava:7b": "LLaVA 7B（默认，稳定）",
    "qwen2.5:7b": "Qwen2.5 7B（精度升级，中文优化）",
    "qwen2.5vl": "Qwen2.5-VL 7B（专用视觉模型）",
    "minicpm-v:latest": "minicpm-v:8b（llava替代）",
    "qwen3-vl-8b-thinking": "通义千问3 VL 8b（思考）",
    "qwen3-vl-8b-instruct": "通义千问3 VL 8b",
    "qwen2.5-vl-3b-instruct": "通义千问2.5 VL 3b AWQ",
}

SUPPORTED_VL_MODELS = set(VL_MODEL_OPTIONS.keys())


@app.get("/api/settings/vl_model")
async def get_vl_model():
    """查询当前视觉模型配置 + 可用模型列表"""
    settings = await db.get_settings()
    active = settings.get("active_vl_model", "llava:7b")
    # 检查 Ollama 在线状态
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            local_models = {m["name"] for m in r.json().get("models", [])}
        else:
            local_models = set()
    except Exception:
        local_models = set()

    available = []
    for key, label in VL_MODEL_OPTIONS.items():
        available.append({
            "key": key,
            "label": label,
            "installed": key in local_models,
            "active": key == active,
            "is_cloud": False,
            "is_custom": False,
        })

    # 也列出其他本地可用的可能视觉模型
    for m in sorted(local_models):
        if m not in SUPPORTED_VL_MODELS and ("vl" in m.lower() or "llava" in m.lower() or "vision" in m.lower()):
            available.append({
                "key": m,
                "label": f"{m}（本地可用）",
                "installed": True,
                "active": m == active,
                "is_cloud": False,
                "is_custom": False,
            })

    #获取数据库中已经启用的模型，并组装成字典
    custom_models = await db.get_custom_vl_models()
    for cm in custom_models:
        if not cm.get("is_enabled", 1):
            continue
        model_key = cm["model_key"]
        installed = bool(cm.get("api_token"))
        available.append({
            "key": model_key,
            "label": cm.get("label", model_key),
            "installed": installed,
            "active": model_key == active,
            "is_cloud": True,
            "is_custom": True,
            "custom_id": cm["id"],
            "description": cm.get("description", ""),
        })
    return ok({
        "active_model": active,
        "available_models": available,
    })


@app.post("/api/settings/vl_model")
async def set_vl_model(model: str = Form(...)):
    """切换视觉模型，需要系统空闲"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法切换模型")

    # 第一步：查询数据库，获取自定义模型列表
    custom_models = await db.get_custom_vl_models()

    # 第二步：确定模型类型和验证方式
    model_info = next((cm for cm in custom_models if cm["model_key"] == model), None)
    is_cloud = False

    if model_info:
        is_cloud = model_info.get("model_type") == "cloud"
        if is_cloud and not model_info.get("api_token"):
            return err(400, "切换云端模型前请先配置API Token")
    else:
        # 本地模型：检查Ollama中是否存在
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code == 200:
                local_models = {m["name"] for m in r.json().get("models", [])}
            else:
                local_models = set()
        except Exception:
            local_models = set()

        # 检查模型是否在本地可用列表中
        if model not in SUPPORTED_VL_MODELS and model not in local_models:
            return err(400, f"模型 {model} 不在可用列表中，请先通过 ollama pull 安装")

    # 第四步：切换模型
    old_model = (await db.get_settings()).get("active_vl_model", "llava:7b")
    await db.update_setting("active_vl_model", model)
    await db.add_log("config", operation_action=f"vl_model_switch:{old_model}→{model}")

    return ok({
        "previous_model": old_model,
        "active_model": model,
    }, message=f"视觉模型已从 {old_model} 切换为 {model}")



# ─────────────────── 新增接口：自定义视觉模型 CRUD ───────────────────

@app.get("/api/settings/vl_model/custom")
async def list_custom_vl_models():
    """查询所有自定义视觉模型"""
    models = await db.get_custom_vl_models()
    return ok({"models": models})


# ... existing code ...
@app.post("/api/settings/vl_model/custom")
async def create_custom_vl_model(
    model_key: str = Form(...),
    label: str = Form(...),
    api_base_url: str = Form(""),
    api_token: str = Form(""),
    api_format: str = Form("openai"),
    description: str = Form(""),
):
    """新增自定义视觉模型"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法修改模型配置")
    if not model_key or not label:
        return err(400, "模型标识和显示名称不能为空")
    if api_format not in ("openai", "dashscope", "qwen_vl_legacy"):
        return err(400, "API格式必须为 openai、dashscope 或 qwen_vl_legacy")
    if not api_base_url:
        api_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    mid = await db.add_custom_vl_model(
        model_key=model_key, label=label, model_type="cloud",
        api_base_url=api_base_url, api_token=api_token,
        api_format=api_format,
        description=description,
    )
    await db.add_log("config", operation_action=f"custom_model_add:{model_key}({label})")
    return ok({"id": mid, "model_key": model_key}, message=f"模型 {label} 添加成功")



# ... existing code ...
@app.put("/api/settings/vl_model/custom/{mid}")
async def update_custom_vl_model(
    mid: int,
    label: str = Form(None),
    api_base_url: str = Form(None),
    api_token: str = Form(None),
    api_format: str = Form(None),
    description: str = Form(None),
    is_enabled: int = Form(None),
):
    """修改自定义视觉模型"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法修改模型配置")
    updates = {}
    if label is not None:
        updates["label"] = label
    if api_base_url is not None:
        updates["api_base_url"] = api_base_url
    if api_token is not None:
        updates["api_token"] = api_token
    if api_format is not None:
        if api_format not in ("openai", "dashscope", "qwen_vl_legacy"):
            return err(400, "API格式必须为 openai、dashscope 或 qwen_vl_legacy")
        updates["api_format"] = api_format
    if description is not None:
        updates["description"] = description
    if is_enabled is not None:
        updates["is_enabled"] = is_enabled
    if not updates:
        return err(400, "没有需要更新的字段")

    await db.update_custom_vl_model(mid, **updates)
    return ok({"id": mid}, message="模型更新成功")



# ... existing code ...
@app.delete("/api/settings/vl_model/custom/{mid}")
async def delete_custom_vl_model(mid: int):
    """删除自定义视觉模型（移入回收站）"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法修改模型配置")
    models = await db.get_custom_vl_models()
    target = next((m for m in models if m["id"] == mid), None)
    if not target:
        return err(404, "模型不存在")

    active = (await db.get_settings()).get("active_vl_model", "")
    if active == target["model_key"]:
        return err(400, f"模型 '{target['label']}' 正在使用中，请先切换到其他模型再删除")

    await db.delete_custom_vl_model(mid)
    await db.add_log("config", operation_action=f"custom_model_recycle:{target['model_key']}")
    return ok({"deleted_id": mid}, message=f"模型 {target['label']} 已移入回收站")


@app.get("/api/settings/vl_model/custom/recycle")
async def list_deleted_custom_vl_models():
    """获取回收站中的模型"""
    models = await db.get_deleted_custom_vl_models()
    return ok({"models": models})


@app.post("/api/settings/vl_model/custom/recycle/{mid}/restore")
async def restore_custom_vl_model(mid: int):
    """从回收站恢复模型"""
    deleted = await db.get_deleted_custom_vl_models()
    target = next((m for m in deleted if m["id"] == mid), None)
    if not target:
        return err(404, "回收站中无此模型")
    await db.restore_custom_vl_model(mid)
    return ok({"id": mid}, message=f"模型 {target['label']} 已恢复")


@app.delete("/api/settings/vl_model/custom/recycle/{mid}")
async def hard_delete_custom_vl_model(mid: int):
    """彻底删除模型（不可恢复）"""
    deleted = await db.get_deleted_custom_vl_models()
    target = next((m for m in deleted if m["id"] == mid), None)
    if not target:
        return err(404, "回收站中无此模型")
    await db.hard_delete_custom_vl_model(mid)
    await db.add_log("config", operation_action=f"custom_model_permanent_delete:{target['model_key']}")
    return ok({"id": mid}, message=f"模型 {target['label']} 已永久删除")


# ─────────────────── 接口：施工工序管理 ───────────────────
# ... existing code ...


# ─────────────────── 接口：施工工序管理 ───────────────────

@app.get("/api/processes")
async def list_processes():
    """查询所有工序（按排序顺序）"""
    processes = await db.get_processes()
    return ok({"processes": processes})


@app.get("/api/processes/{pid}")
async def get_process(pid: int):
    """查询单个工序"""
    p = await db.get_process(pid)
    if not p:
        return err(404, "工序不存在")
    return ok(p)


@app.post("/api/processes")
async def create_process(
    name: str = Form(...),
    sort_order: int = Form(0),
    work_type: str = Form(""),
    standard_days: float = Form(1.0),
    description: str = Form(""),
    applicable_spaces: str = Form(""),
    color: str = Form("#6366f1"),
):
    """新增工序"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法修改工序")
    pid = await db.add_process(name, sort_order, work_type, standard_days, description, applicable_spaces, color)
    return ok({"id": pid}, message="工序创建成功")


@app.put("/api/processes/{pid}")
async def update_process(
    pid: int,
    name: str = Form(None),
    sort_order: int = Form(None),
    work_type: str = Form(None),
    standard_days: float = Form(None),
    description: str = Form(None),
    applicable_spaces: str = Form(None),
    color: str = Form(None),
):
    """修改工序"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法修改工序")
    kwargs = {}
    if name is not None: kwargs["name"] = name
    if sort_order is not None: kwargs["sort_order"] = sort_order
    if work_type is not None: kwargs["work_type"] = work_type
    if standard_days is not None: kwargs["standard_days"] = standard_days
    if description is not None: kwargs["description"] = description
    if applicable_spaces is not None: kwargs["applicable_spaces"] = applicable_spaces
    if color is not None: kwargs["color"] = color
    await db.update_process(pid, **kwargs)
    return ok(message="工序更新成功")


@app.delete("/api/processes/{pid}")
async def delete_process(pid: int):
    """删除工序（软删除）"""
    if task_state.state != STATE_IDLE:
        return err(409, "系统忙，无法删除工序")
    await db.delete_process(pid)
    return ok(message="工序已删除")


@app.get("/api/processes/quotes/summary")
async def process_quote_summary(
    quote_id: int = Query(None),
):
    """按工序汇总报价分项"""
    if quote_id:
        quote = await db.get_quote(quote_id)
        if not quote:
            return err(404, "报价记录不存在")
        items = quote.get("quote_detail_json", [])
    else:
        quotes = await db.get_quotes(1, 1)
        if not quotes["items"]:
            return err(404, "暂无报价记录")
        items = quotes["items"][0].get("quote_detail_json", [])

    if isinstance(items, str):
        try: items = json.loads(items)
        except: items = []

    processes = await db.get_processes()
    proc_map = {p["id"]: p for p in processes}

    # 按工序汇总
    from collections import defaultdict
    by_process = defaultdict(lambda: {"process_name": "", "spaces": set(), "total_qty": 0, "total_amount": 0, "items": []})
    for item in items:
        pid = item.get("process_id", 0)
        if pid in proc_map:
            by_process[pid]["process_name"] = proc_map[pid]["name"]
        by_process[pid]["spaces"].add(item.get("space_name", ""))
        by_process[pid]["total_qty"] += item.get("quantity", 0)
        by_process[pid]["total_amount"] += item.get("subtotal", 0)
        by_process[pid]["items"].append(item)

    result = []
    for proc in processes:
        pid = proc["id"]
        if pid in by_process:
            entry = by_process[pid]
            result.append({
                "process_id": pid,
                "process_name": proc["name"],
                "sort_order": proc["sort_order"],
                "work_type": proc["work_type"],
                "standard_days": proc["standard_days"],
                "color": proc["color"],
                "spaces": sorted(entry["spaces"]),
                "space_count": len(entry["spaces"]),
                "total_quantity": round(entry["total_qty"], 2),
                "total_amount": round(entry["total_amount"], 2),
                "item_count": len(entry["items"]),
            })

    return ok({"process_summary": result, "total_quote": sum(r["total_amount"] for r in result)})


# ─────────────────── 分层工程量（新增：P0补充） ───────────────────


@app.get("/api/drawings")
async def list_drawings():
    """列出所有图纸记录（供前端选择）"""
    try:
        rows = await db.fetchall(
            "SELECT id, filename, file_size, upload_time, parse_status, cad_result_json FROM drawing_records WHERE is_deleted=0 ORDER BY id DESC"
        )
        drawings = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("cad_result_json"), str):
                try:
                    d["cad_result_json"] = json.loads(d["cad_result_json"])
                except:
                    pass
            drawings.append(d)
        return ok(drawings)
    except Exception as e:
        return err(500, f"查询图纸列表失败: {str(e)}")


@app.get("/api/image-results")
async def get_all_image_results():
    """获取所有效果图识别结果"""
    try:
        rows = await db.get_image_results()
        if not rows:
            return ok([])
        results = []
        for r in rows:
            results.append({
                "id": r.get("id"),
                "image_result_id": r.get("id"),
                "recognized_space": r.get("recognized_space", ""),
                "original_filename": r.get("original_filename", r.get("filename", "")),
                "filename": r.get("filename", ""),
                "confidence": r.get("confidence", 0),
            })
        return ok(results)
    except Exception as e:
        return err(500, f"查询效果图识别结果失败: {str(e)}")


@app.post("/api/spaces/{drawing_id}/compute_breakdown")
async def compute_surface_breakdown(drawing_id: int):
    """
    为指定图纸的所有空间计算分层工程量（墙面/地面/顶面）。
    结果存入 cad_analysis_results 的 detail_json 字段。
    不修改任何已有汇总/报价数据。
    """
    try:
        cad_rows = await db.get_cad_results(drawing_id)
        if not cad_rows:
            return err(404, f"图纸 {drawing_id} 没有CAD分析结果")

        from surface_breakdown import batch_compute
        settings = await db.get_settings()

        updates = []
        breakdown_map = {}
        for row in cad_rows:
            cid = row["id"]
            breakdown = batch_compute([row], settings)[0]["surface_breakdown"]
            new_detail = dict(row.get("detail_json", {}))
            new_detail["surface_breakdown"] = breakdown
            updates.append((cid, new_detail))
            breakdown_map[cid] = breakdown

        await db.batch_update_cad_detail(updates)

        return ok({
            "drawing_id": drawing_id,
            "space_count": len(cad_rows),
            "breakdown_count": len(updates),
            "sample": dict(list(breakdown_map.items())[:3]),
        }, message=f"已为 {len(updates)} 个空间计算分层工程量")

    except Exception as e:
        return err(500, f"分层计算失败: {str(e)}", task_status=task_state.state)


@app.get("/api/spaces/{drawing_id}/breakdown")
async def get_surface_breakdown(drawing_id: int):
    """
    获取图纸所有空间的分层工程量 + 关联材质信息。
    材质按空间名称模糊匹配 image_analysis_results。
    """
    try:
        cad_rows = await db.get_cad_results(drawing_id)
        if not cad_rows:
            return err(404, f"图纸 {drawing_id} 没有CAD分析结果")

        # 取所有效果图材质，按 recognized_space 关联
        image_rows = await db.get_image_results()
        material_by_space = {}
        for img in image_rows:
            space = img.get("recognized_space", "").strip()
            if space:
                mat = img.get("material_info", {})
                if isinstance(mat, str):
                    try:
                        mat = json.loads(mat)
                    except Exception:
                        mat = {}
                # 如果多个图识别同空间，取最新的（id最大的）
                if space not in material_by_space or img["id"] > material_by_space[space].get("image_id", 0):
                    material_by_space[space] = {
                        "image_id": img["id"],
                        "materials": mat,
                        "confidence": img.get("confidence", 0),
                    }

        spaces = []
        for row in cad_rows:
            detail = row.get("detail_json", {})
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except Exception:
                    detail = {}
            breakdown = detail.get("surface_breakdown", {})

            # 按空间名称匹配材质（使用同义词映射 + 智能匹配）
            name = row.get("space_name", "")
            # 精确匹配（快速路径）
            mat_link = material_by_space.get(name, {})
            # 如果没精确匹配，尝试同义词智能匹配
            if not mat_link:
                for mat_space, mat_data in material_by_space.items():
                    if space_synonyms.match_space_name(name, mat_space):
                        mat_link = mat_data
                        break

            # 将材质分配到各表面
            mat_info = mat_link.get("materials", {})
            surfaces = breakdown.get("surfaces", {})

            # 也读取手动绑定的材质（surface_materials）
            manual_mats = detail.get("surface_materials", {})

            for sname in ["floor", "wall", "ceiling"]:
                if sname in surfaces:
                    # 优先取手动绑定
                    manual = manual_mats.get(sname, {})
                    if manual.get("name"):
                        surfaces[sname]["material"] = manual["name"]
                        surfaces[sname]["material_source"] = "manual"
                    else:
                        surfaces[sname]["material"] = mat_info.get(sname, "")
                        surfaces[sname]["material_source"] = "ai" if mat_info.get(sname) else ""

            spaces.append({
                "id": row["id"],
                "space_name": row["space_name"],
                "area": row.get("area", 0),
                "surface_breakdown": breakdown,
                "material_source": mat_link.get("image_id"),
                "material_confidence": mat_link.get("confidence", 0),
            })

        # 汇总统计
        total_floor = sum(s["surface_breakdown"].get("surfaces", {}).get("floor", {}).get("area", 0) for s in spaces)
        total_wall_net = sum(s["surface_breakdown"].get("surfaces", {}).get("wall", {}).get("net_area", 0) for s in spaces)
        total_ceiling = sum(s["surface_breakdown"].get("surfaces", {}).get("ceiling", {}).get("area", 0) for s in spaces)
        matched_count = sum(1 for s in spaces if s["material_source"])
        unmatched_count = sum(1 for s in spaces if not s["material_source"])

        return ok({
            "drawing_id": drawing_id,
            "space_count": len(spaces),
            "summary": {
                "total_floor_area": round(total_floor, 2),
                "total_wall_net_area": round(total_wall_net, 2),
                "total_ceiling_area": round(total_ceiling, 2),
                "matched_spaces": matched_count,
                "unmatched_spaces": unmatched_count,
            },
            "spaces": spaces,
        })

    except Exception as e:
        return err(500, f"查询分层数据失败: {str(e)}")


@app.post("/api/spaces/breakdown/bind_material")
async def bind_surface_material(
    cad_id: int = Form(...),
    surface: str = Form(...),
    material_name: str = Form(""),
    material_code: str = Form(""),
):
    """
    手动绑定某空间某表面的材质。
    surface: floor / wall / ceiling
    """
    try:
        rows = await db.fetchall(
            "SELECT * FROM cad_analysis_results WHERE id=? AND is_deleted=0", (cad_id,)
        )
        if not rows:
            return err(404, f"CAD结果 {cad_id} 不存在")

        row = dict(rows[0])
        space_name = row.get("space_name", "")
        detail = row.get("detail_json", {})
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:
                detail = {}

        if "surface_materials" not in detail:
            detail["surface_materials"] = {}
        if surface not in detail["surface_materials"]:
            detail["surface_materials"][surface] = {}
        detail["surface_materials"][surface] = {
            "name": material_name,
            "code": material_code,
            "bound_at": datetime.now().isoformat(),
        }

        await db.update_cad_detail_json(cad_id, detail)

        # 记录操作日志
        trace_id = uuid.uuid4().hex[:12]
        await db.add_log(
            task_type="manual_edit",
            operation_action=f"材质绑定: {space_name} → {surface}={material_name}",
            lock_status="idle",
            trace_id=trace_id,
            run_status="success",
        )

        return ok({
            "cad_id": cad_id,
            "surface": surface,
            "material_name": material_name,
            "detail_preview": detail,
        }, message=f"已绑定 {surface} 材质为 {material_name}")

    except Exception as e:
        return err(500, f"材质绑定失败: {str(e)}")


# ─────────────────── 接口：空间名编辑 ───────────────────

@app.put("/api/spaces/{cad_id}/rename")
async def rename_space(cad_id: int, body: dict):
    """
    编辑 CAD 空间名称
    入参：{"space_name": "新名称"}
    """
    new_name = body.get("space_name", "").strip()
    if not new_name:
        return err(422, "space_name 不能为空")

    try:
        rows = await db.fetchall(
            "SELECT * FROM cad_analysis_results WHERE id=? AND is_deleted=0", (cad_id,)
        )
        if not rows:
            return err(404, f"CAD结果 {cad_id} 不存在")

        old_name = dict(rows[0]).get("space_name", "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "UPDATE cad_analysis_results SET space_name=?, update_time=? WHERE id=?",
            (new_name, now, cad_id)
        )

        # 记录操作日志
        trace_id = uuid.uuid4().hex[:12]
        await db.add_log(
            task_type="manual_edit",
            operation_action=f"空间重命名: '{old_name}' → '{new_name}'",
            lock_status="idle",
            trace_id=trace_id,
            run_status="success",
        )

        return ok({
            "cad_id": cad_id,
            "old_name": old_name,
            "new_name": new_name,
        }, message=f"已重命名: {old_name} → {new_name}")

    except Exception as e:
        return err(500, f"重命名失败: {str(e)}")

# ─────────────────── 接口：自动匹配建议 + 确认绑定（全链路） ───────────────────


@app.post("/api/spaces/auto_suggest_match")
async def auto_suggest_match(
    drawing_id: int = Form(...),
    image_result_ids: str = Form("[]"),
):
    """
    自动建议匹配：根据效果图识别空间，推荐匹配的CAD空间。
    入参：drawing_id（图纸ID）, image_result_ids（效果图结果ID列表，JSON数组）
    返回：每个效果图识别空间 → 匹配的CAD空间列表
    """
    img_ids = json.loads(image_result_ids) if isinstance(image_result_ids, str) else image_result_ids

    # 获取该图纸的所有CAD空间
    cad_rows = await db.get_cad_results(drawing_id)
    if not cad_rows:
        return err(404, f"图纸 {drawing_id} 没有CAD分析结果")

    # 获取效果图识别结果
    image_rows = await db.get_image_results(img_ids) if img_ids else []

    matches = []
    for img in image_rows:
        img_id = img["id"]
        ai_space = img.get("recognized_space", "").strip()
        if not ai_space:
            continue

        # 对每个AI识别空间，查找匹配的CAD空间
        matched_cads = []
        for cad in cad_rows:
            cad_id = cad["id"]
            cad_name = cad.get("space_name", "")
            if cad_name and space_synonyms.match_space_name(cad_name, ai_space):
                matched_cads.append({
                    "cad_id": cad_id,
                    "cad_name": cad_name,
                    "area": cad.get("area", 0),
                })

        # 获取材质信息
        mat_info = img.get("material_info", {})
        if isinstance(mat_info, str):
            try:
                mat_info = json.loads(mat_info)
            except Exception:
                mat_info = {}

        matches.append({
            "image_id": img_id,
            "recognized_space": ai_space,
            "cad_ids": [m["cad_id"] for m in matched_cads],
            "matched_cad_spaces": matched_cads,
            "material_info": mat_info,
            "confidence": img.get("confidence", 0),
            "original_filename": Path(str(img.get("image_path", ""))).name or f"图片#{img_id}",
        })

    return ok({"matches": matches})


@app.post("/api/spaces/auto_confirm_match")
async def auto_confirm_match(
    cad_result_id: int = Form(...),
    image_result_id: int = Form(...),
    surface_materials: str = Form(None),
):
    """
    确认匹配：将效果图材质绑定到CAD空间。
    入参：cad_result_id（CAD空间ID，即 cad_analysis_results.id）,
          image_result_id（效果图结果ID）,
          surface_materials（可选，JSON覆盖材质信息）
    功能：将 image_result 的材质写入 cad_analysis_results.detail_json.surface_materials
    """
    try:
        # 获取效果图识别结果
        img_rows = await db.get_image_results([image_result_id])
        if not img_rows:
            return err(404, f"图片识别结果 {image_result_id} 不存在")
        img = img_rows[0]

        # 提取材质信息
        mat_info = img.get("material_info", {})
        if isinstance(mat_info, str):
            try:
                mat_info = json.loads(mat_info)
            except Exception:
                mat_info = {}

        # 如果提供了覆盖参数，使用覆盖
        if surface_materials:
            try:
                mat_info = json.loads(surface_materials)
            except Exception:
                pass

        # 获取CAD空间
        cad_rows = await db.fetchall(
            "SELECT * FROM cad_analysis_results WHERE id=? AND is_deleted=0", (cad_result_id,)
        )
        if not cad_rows:
            return err(404, f"CAD空间 {cad_result_id} 不存在")

        row = dict(cad_rows[0])
        detail = row.get("detail_json", {})
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:
                detail = {}

        # 写入 surface_materials 到 detail_json
        detail["surface_materials"] = {
            "wall": {
                "name": str(mat_info.get("wall", "")),
                "source": "ai_matched",
                "image_result_id": image_result_id,
            },
            "floor": {
                "name": str(mat_info.get("floor", "")),
                "source": "ai_matched",
                "image_result_id": image_result_id,
            },
            "ceiling": {
                "name": str(mat_info.get("ceiling", "")),
                "source": "ai_matched",
                "image_result_id": image_result_id,
            },
        }
        # 记录匹配来源
        detail["ai_matched_from"] = {
            "image_result_id": image_result_id,
            "recognized_space": img.get("recognized_space", ""),
            "matched_at": datetime.now().isoformat(),
        }

        await db.update_cad_detail_json(cad_result_id, detail)

        return ok({
            "cad_result_id": cad_result_id,
            "image_result_id": image_result_id,
            "bound": detail["surface_materials"],
            "space_name": row.get("space_name", ""),
            "ai_space": img.get("recognized_space", ""),
        }, message=f"已确认绑定: {row.get('space_name', '')} ↔ {img.get('recognized_space', '')}")

    except Exception as e:
        return err(500, f"确认匹配失败: {str(e)}")


@app.get("/api/config")
async def get_config():
    """兼容旧版配置查询"""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        ollama_ok = r.status_code == 200 and "llava" in r.text.lower()
    except Exception:
        ollama_ok = False
    return {
        "vl_engine": "Ollama/LLaVA-7B 本地模型",
        "llava_available": ollama_ok,
        "supported_cad_formats": [".dxf", ".dwg"],
        "supported_image_formats": [".jpg", ".jpeg", ".png", ".webp"],
    }


@app.get("/api/health")
async def health_check():
    """兼容旧版健康检查"""
    return {"status": "ok", "time": datetime.now().isoformat()}


# ─────────────────── 接口：报价模板 ───────────────────

@app.get("/api/pricing/templates")
async def get_pricing_templates():
    """获取所有报价模板"""
    tpls = await db.get_pricing_templates()
    return ok(tpls)


@app.post("/api/pricing/templates/switch")
async def switch_template(template_id: int = Form(...)):
    """切换默认报价模板"""
    await db.set_default_template(template_id)
    return ok({"active_template_id": template_id}, message=f"已切换至模板#{template_id}")


@app.get("/api/pricing/items")
async def get_pricing_items(template_id: int = Query(None)):
    """获取计价分项，可按模板筛选"""
    items = await db.get_pricing_items(template_id)
    return ok(items)


@app.post("/api/pricing/items")
async def add_pricing_item(
    template_id: int = Form(...),
    surface_type: str = Form(...),
    item_name: str = Form(...),
    unit: str = Form("㎡"),
    unit_price: float = Form(0.0),
    unit_price_material: float = Form(0.0),
    unit_price_labor: float = Form(0.0),
    unit_price_aux: float = Form(0.0),
    sort_order: int = Form(0),
    description: str = Form(""),
):
    """新增计价分项"""
    pid = await db.add_pricing_item(
        template_id, surface_type, item_name, unit,
        unit_price, unit_price_material, unit_price_labor,
        unit_price_aux, sort_order, description
    )
    return ok({"id": pid}, message="计价分项已添加")


@app.put("/api/pricing/items/{pid}")
async def update_pricing_item(
    pid: int,
    item_name: str = Form(None),
    surface_type: str = Form(None),
    unit: str = Form(None),
    unit_price: float = Form(None),
    unit_price_material: float = Form(None),
    unit_price_labor: float = Form(None),
    unit_price_aux: float = Form(None),
    sort_order: int = Form(None),
    description: str = Form(None),
):
    """更新计价分项"""
    kwargs = {k: v for k, v in locals().items()
              if k != "pid" and v is not None and k != "self"}
    await db.update_pricing_item(pid, **kwargs)
    return ok({"id": pid}, message="计价分项已更新")


@app.delete("/api/pricing/items/{pid}")
async def delete_pricing_item(pid: int):
    """删除计价分项"""
    await db.delete_pricing_item(pid)
    return ok({"id": pid}, message="计价分项已删除")


# ─────────────────── 接口：工序单价批量更新 ───────────────────

@app.post("/api/processes/batch_update_price")
async def batch_update_process_price(updates: str = Form(...)):
    """批量更新工序单价"""
    data = json.loads(updates)
    for item in data:
        pid = item.get("id")
        price = item.get("unit_price")
        unit = item.get("unit")
        kw = {}
        if price is not None:
            kw["unit_price"] = price
        if unit:
            kw["unit"] = unit
        if kw:
            await db.update_process(pid, **kw)
    return ok({"updated": len(data)}, message=f"已更新{len(data)}项工序单价")


# ─────────────────── 接口：新版精细化工序报价导出 ───────────────────

@app.post("/api/export/process_quote")
async def export_process_quote(
    quote_id: int = Form(...),
):
    """新版精细化工序报价单导出"""
    from excel_export import export_process_quote_excel

    quote = await db.get_quote(quote_id)
    if not quote:
        return err(422, "报价记录不存在")

    tid = ""
    try:
        ok_flag, tid = await task_state.acquire("export")
        if not ok_flag:
            return err(409, f"系统当前有任务正在执行（{task_state.state}），请等待完成后再操作")

        cad_rows = await db.get_cad_results(quote.get("cad_result_id", 0))

        # 读取默认模板计价项
        default_tid = await db.get_default_template_id()
        pricing_items = await db.get_pricing_items(default_tid)

        # 读取工序
        processes = await db.get_processes()
        process_map = {p["work_type"]: p for p in processes}

        # 读取材质数据
        img_ids = quote.get("image_result_ids", [])
        material_data = []
        if img_ids:
            img_rows = await db.get_image_results(img_ids)
            material_data = [
                {
                    "space_name": r.get("recognized_space", ""),
                    "material_info": r.get("material_info", {}),
                }
                for r in img_rows
            ]

        # 读取分层明细
        try:
            from surface_breakdown import compute_surface_breakdown
            bd = compute_surface_breakdown(cad_rows)
        except Exception:
            bd = []

        excel_data = {
            "project_name": quote.get("project_name", "精细化工序报价单"),
            "create_time": quote.get("create_time", ""),
            "base_price": quote.get("base_price", 0),
            "material_diff_price": quote.get("material_diff_price", 0),
            "process_add_price": quote.get("process_add_price", 0),
            "loss_price": quote.get("loss_price", 0),
            "manage_fee": quote.get("manage_fee", 0),
            "tax_fee": quote.get("tax_fee", 0),
            "final_price": quote.get("final_price", 0),
            "cad_data": cad_rows,
            "material_data": material_data,
            "pricing_items": pricing_items,
            "processes": processes,
            "process_map": process_map,
            "breakdown_data": bd,
            "items": quote.get("quote_detail_json", []),
        }

        filepath = export_process_quote_excel(excel_data)
        await db.update_quote_export(quote_id, filepath)

        fname = os.path.basename(filepath)
        return ok({
            "export_path": filepath,
            "filename": fname,
            "url": f"/api/exports/{fname}",
        }, message="精细化工序报价单已生成", task_status=STATE_IDLE, trace_id=tid)

    except Exception as e:
        return err(500, f"导出失败: {str(e)}", task_status=STATE_IDLE, trace_id=tid)
    finally:
        await task_state.release()


# ─────────────────── 接口：双源数据核对表 ───────────────────

@app.get("/api/spaces/{drawing_id}/comparison")
async def get_comparison_table(drawing_id: int):
    """
    返回CAD与AI双源数据比对表。
    每行包含：空间名、面积、各表面材质(AI识别)、比对状态、异常标记。
    """
    try:
        cad_rows = await db.get_cad_results(drawing_id)
        if not cad_rows:
            return err(404, f"图纸 {drawing_id} 没有CAD分析结果")

        # 取所有AI识别结果
        image_rows = await db.get_image_results()
        ai_by_space = {}
        for img in image_rows:
            space = img.get("recognized_space", "").strip()
            if not space:
                continue
            mat = img.get("material_info", {})
            if isinstance(mat, str):
                try:
                    mat = json.loads(mat)
                except Exception:
                    mat = {}
            conf = img.get("confidence", 0)
            if space not in ai_by_space or img["id"] > ai_by_space[space].get("image_id", 0):
                ai_by_space[space] = {"materials": mat, "confidence": conf, "image_id": img["id"]}

        import space_synonyms

        rows = []
        anomaly_count = 0
        for r in cad_rows:
            cad_name = r.get("space_name", "未命名空间")
            area = r.get("area", 0)
            detail = r.get("detail_json", {})
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except Exception:
                    detail = {}

            # 匹配AI材质
            matched_ai = None
            matched_space = ""
            for ai_space, ai_data in ai_by_space.items():
                if space_synonyms.match_space_name(cad_name, ai_space):
                    matched_ai = ai_data
                    matched_space = ai_space
                    break

            wall_mat = ""
            floor_mat = ""
            ceiling_mat = ""
            ai_conf = 0
            if matched_ai:
                mat = matched_ai.get("materials", {})
                wall_mat = str(mat.get("wall", mat.get("墙面材质", "")))
                floor_mat = str(mat.get("floor", mat.get("地面材质", "")))
                ceiling_mat = str(mat.get("ceiling", mat.get("吊顶材质", "")))
                ai_conf = matched_ai.get("confidence", 0)

            # 异常判定
            anomalies = []
            if cad_name in ("未命名空间", "") or cad_name.startswith("未命名"):
                anomalies.append("空间名称未识别")
            if area <= 0:
                anomalies.append("面积为0或负数")
            if not matched_ai:
                anomalies.append("AI材质未匹配")
            elif ai_conf < 0.5:
                anomalies.append(f"AI置信度偏低({ai_conf:.0%})")
            else:
                if not wall_mat:
                    anomalies.append("墙面材质未识别")
                if not floor_mat:
                    anomalies.append("地面材质未识别")
                if not ceiling_mat:
                    anomalies.append("顶面材质未识别")

            status = "正常"
            if anomalies:
                status = "异常"
                anomaly_count += 1

            rows.append({
                "space_id": r.get("id", 0),
                "space_name": cad_name,
                "area_sqm": round(area, 2) if area else 0,
                "wall_material": wall_mat,
                "floor_material": floor_mat,
                "ceiling_material": ceiling_mat,
                "ai_confidence": round(ai_conf, 2),
                "ai_matched_space": matched_space,
                "status": status,
                "anomalies": anomalies,
                "surface_materials": detail.get("surface_materials", {}),
            })

        # 统计
        total = len(rows)
        normal = total - anomaly_count

        return ok({
            "drawing_id": drawing_id,
            "total_spaces": total,
            "normal_count": normal,
            "anomaly_count": anomaly_count,
            "rows": rows,
        })

    except Exception as e:
        return err(500, f"比对失败: {str(e)}")


# ─────────────────── 接口：标准报价表（综合/分项/工序） ───────────────────

@app.get("/api/quote/{quote_id}/standard_report")
async def get_standard_report(quote_id: int):
    """
    返回标准报价表的三个视图数据：
    1. 综合报价总表（项目概况+工种汇总）
    2. 空间分项明细表（每个空间逐项）
    3. 工序费用明细表（按工序聚合）
    """
    try:
        quote = await db.get_quote(quote_id)
        if not quote:
            return err(404, "报价记录不存在")

        items = quote.get("quote_detail_json", [])
        if isinstance(items, str):
            items = json.loads(items)

        # ─── 1. 综合报价总表 ───
        summary = {
            "project_name": quote.get("project_name", "装修工程"),
            "total_area": sum(i.get("quantity", 0) for i in items if "面积" not in i.get("project_name", "")) or 0,
            "total_price": quote.get("final_price", 0),
            "base_price": quote.get("base_price", 0),
            "material_diff": quote.get("material_diff_price", 0),
            "loss_price": quote.get("loss_price", 0),
            "manage_fee": quote.get("manage_fee", 0),
            "tax_fee": quote.get("tax_fee", 0),
            "create_time": quote.get("create_time", ""),
            "quote_id": quote_id,
        }

        # 工种汇总
        process_totals = {}
        for item in items:
            proc = item.get("process_name", "其他")
            if proc not in process_totals:
                process_totals[proc] = {"subtotal": 0, "count": 0, "spaces": set()}
            process_totals[proc]["subtotal"] += float(item.get("subtotal", 0))
            process_totals[proc]["count"] += 1
            if item.get("space_name"):
                process_totals[proc]["spaces"].add(item["space_name"])
        summary["process_summary"] = [
            {
                "process_name": k,
                "subtotal": round(v["subtotal"], 2),
                "item_count": v["count"],
                "space_count": len(v["spaces"]),
            }
            for k, v in sorted(process_totals.items(), key=lambda x: -x[1]["subtotal"])
        ]

        # ─── 2. 空间分项明细表 ───
        space_detail = {}
        for item in items:
            sn = item.get("space_name", "其他")
            if sn not in space_detail:
                space_detail[sn] = {"items": [], "space_subtotal": 0}
            space_detail[sn]["items"].append(item)
            space_detail[sn]["space_subtotal"] += float(item.get("subtotal", 0))
        summary["space_details"] = [
            {
                "space_name": k,
                "space_subtotal": round(v["space_subtotal"], 2),
                "items": v["items"],
            }
            for k, v in sorted(space_detail.items(), key=lambda x: -x[1]["space_subtotal"])
        ]

        # ─── 3. 工序费用明细表 ───
        cad_result_id = quote.get("cad_result_id", 0)
        cad_rows = await db.get_cad_results(cad_result_id) if cad_result_id else []
        # 获取工序列表
        sys_procs = await db.get_processes()
        proc_details = []
        for proc in sys_procs:
            pname = proc["name"]
            related = [i for i in items if i.get("process_name") == pname]
            if not related:
                continue
            space_set = set()
            labor_cost = 0
            material_cost = 0
            for i in related:
                space_set.add(i.get("space_name", ""))
                qty = float(i.get("quantity", 0))
                mat_p = float(i.get("material_unit_price", 0) or 0)
                lab_p = float(i.get("labor_unit_price", 0) or 0)
                material_cost += qty * mat_p
                labor_cost += qty * lab_p
            proc_details.append({
                "process_name": pname,
                "sort_order": proc.get("sort_order", proc.get("id", 0)),
                "spaces": sorted([s for s in space_set if s]),
                "space_count": len(space_set),
                "material_cost": round(material_cost, 2),
                "labor_cost": round(labor_cost, 2),
                "subtotal": round(material_cost + labor_cost, 2),
            })
        proc_details.sort(key=lambda x: x["sort_order"])
        summary["process_details"] = proc_details

        return ok(summary)

    except Exception as e:
        return err(500, f"获取报价表失败: {str(e)}")


# ─────────────────── 前端静态文件 ───────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="frontend_assets")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_frontend_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        fp = FRONTEND_DIR / "index.html"
        if fp.exists():
            return FileResponse(str(fp))
        return JSONResponse({"detail": "Not Found"}, status_code=404)


# ─────────────────── 启动 ───────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=False, workers=1)
