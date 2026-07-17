"""
BuildSight 视觉识别 Harness — 中心化配置
============================================
所有可调参数集中管理，一键调参，不散落在各模块中。
"""
import os
from dotenv import load_dotenv#main接口使用

load_dotenv()

# ═══════════════════════════════════════════════
# 图像预处理
# ═══════════════════════════════════════════════

# 透视效果图裁剪比例 (y_start_ratio, y_end_ratio)
# 区域有重叠保证过渡材质不被切丢
CROP_RATIOS = {
    "ceiling": (0.00, 0.30),   # 顶面：顶部30%
    "wall":    (0.25, 0.75),   # 墙面：中段25%-75%
    "floor":   (0.60, 1.00),   # 地面：底部40%
}

# 模型输入预处理
MAX_IMAGE_DIM = 1024       # 最长边像素
JPEG_QUALITY = 85          # JPEG压缩质量

# ═══════════════════════════════════════════════
# 模型推理
# ═══════════════════════════════════════════════
# Ollama 本地模型
DEFAULT_MODEL = "qwen2.5:7b"# 默认本地模型
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_CHAT = "/api/chat"

#通用参数
OLLAMA_TIMEOUT = 120       # 单次推理超时（秒）
OLLAMA_TEMPERATURE = 0.1   # 推理温度（低=更确定）

# ===== 第一次修改：新增-云百炼 (DashScope) 配置 =====
# 使用 OpenAI 兼容模式
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_API_CHAT = "/chat/completions"
DASHSCOPE_MODEL = "qwen-vl-plus" # 默认云端模型
# 云百炼Token从环境变量读取
DASHSCOPE_API_TOKEN = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "qwen3-vl-plus")



# ═══════════════════════════════════════════════
# 校验 & 重试
# ═══════════════════════════════════════════════

MAX_RETRY_ATTEMPTS = 2          # 每字段最大重试次数
FUZZY_MATCH_THRESHOLD = 0.5     # 模糊匹配最低相似度
ENUM_FUZZY_THRESHOLD = 0.8      # 枚举内模糊匹配阈值
RULES_FUZZY_THRESHOLD = 0.8     # 规则允许列表模糊阈值

# ═══════════════════════════════════════════════
# 门禁阈值（与 benchmark_runner.py 保持一致）
# ═══════════════════════════════════════════════

GATE_FILL_RATE = 90        # 填充率 ≥ 90%
GATE_ACCURACY = 80         # 准确率 ≥ 80%
GATE_TIME_LIMIT = 10       # 单图耗时 ≤ 10s
GATE_SPACE_DEVIATION = 1   # 空间偏差 ≤ 1/3

# ═══════════════════════════════════════════════
# 字段定义
# ═══════════════════════════════════════════════

MATERIAL_FIELDS = ["wall_material", "floor_material", "ceiling_material"]
ALL_FIELDS = ["space_type"] + MATERIAL_FIELDS + ["decor_style", "remark"]

FIELD_DISPLAY_NAMES = {
    "space_type": "空间类型",
    "wall_material": "墙面材质",
    "floor_material": "地面材质",
    "ceiling_material": "顶面材质",
    "decor_style": "装修风格",
    "remark": "备注",
}

FIELD_TO_CROP = {
    "wall_material": "wall",
    "floor_material": "floor",
    "ceiling_material": "ceiling",
}
