# BuildSight 视觉识别 Harness 架构文档

> 版本: v1.0 · 更新: 2026-06-13
> 设计思想: 借鉴 OpenHarness 分层调度 + 可插拔模块 + 全局 Hook + 异常重试闭环 + 中心化配置
> 技术底座: Hermes (零切换，纯粹增量)

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Vision Harness                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Preproc  │ →│  Infer   │ →│ Validate │ →│  Retry   │ →│ Output │ │
│  │ 裁剪/预处 │  │ Ollama   │  │ 枚举+规则  │  │ 裁剪重推  │  │ 结构化  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│                          ↑ 全局 Hook 拦截 (日志/指标)                 │
│                     ↑ 中心化配置 (config.py)                          │
└─────────────────────────────────────────────────────────────────────┘
         ↑ 兼容层: image_recognizer.py (零改动存量代码)
         ↑ Hermes 基座 (main.py / benchmark_runner.py)
```

### 核心理念

| 原则 | 实现 |
|------|------|
| **分层调度** | 每阶段职责单一，通过标准 dict 接口通信 |
| **可插拔模块** | 替换任何 stage 只需实现同一接口签名 |
| **全局 Hook** | 各阶段插入日志/指标拦截点 |
| **异常重试闭环** | 检测→裁剪→重推→校验→兜底，完整闭环 |
| **中心化配置** | 所有阈值/比例/策略集中在 config.py |

---

## 二、目录结构与职责

```
backend/
├── image_recognizer.py              ← 兼容层（5行代码委托给 Harness）
└── vision_harness/
    ├── __init__.py                   ← 导出 + 全局单例
    ├── config.py                     ← 中心化配置（一键调参）
    ├── material_library.py           ← 材料库枚举 + 空间规则 + 同义词映射
    ├── pipeline.py                   ← 主流水线编排
    ├── hooks.py                      ← 全局 Hook 拦截器
    └── stages/
        ├── preprocessor.py           ← Stage 1: 图像加载/裁剪/预处理
        ├── inferrer.py               ← Stage 2: 模型调用 + Prompt构建 + JSON提取
        ├── validator.py              ← Stage 3: 枚举校验 + 规则引擎 + 模糊修正
        └── retry_harness.py          ← Stage 4: 重试调度闭环
```

---

## 三、各模块详细说明

### 3.1 config.py — 中心化配置

**职责：** 所有可调参数集中管理，不散落在各模块中。

| 配置项 | 默认值 | 说明 |
|--------|:------:|------|
| `CROP_RATIOS` | `ceiling(0-0.3), wall(0.25-0.75), floor(0.6-1.0)` | 透视裁剪比例 |
| `MAX_IMAGE_DIM` | 1024 | 模型输入最长边像素 |
| `JPEG_QUALITY` | 85 | JPEG压缩质量 |
| `DEFAULT_MODEL` | qwen2.5:7b | 默认推理模型 |
| `OLLAMA_TIMEOUT` | 120s | 单次推理超时 |
| `OLLAMA_TEMPERATURE` | 0.1 | 推理温度（低=更确定） |
| `MAX_RETRY_ATTEMPTS` | 2 | 每字段最大重试次数 |
| `GATE_FILL_RATE` | 90% | 门禁填充率阈值 |
| `GATE_ACCURACY` | 80% | 门禁准确率阈值 |

---

### 3.2 material_library.py — 材料库与规则

**职责：** 维护材料库枚举、空间-材质规则、同义词映射。**单一数据源**。

**核心数据：**

| 数据 | 条目数 | 用途 |
|------|:------:|------|
| `SPACE_TYPES` | 14种 | Prompt枚举 + 校验 |
| `WALL_MATERIALS` | 21种 | Prompt枚举 + 校验 |
| `FLOOR_MATERIALS` | 13种 | Prompt枚举 + 校验 |
| `CEILING_MATERIALS` | 11种 | Prompt枚举 + 校验 |
| `SPACE_MATERIAL_RULES` | 15个空间 | 每个空间的合理材质范围 |
| `SYNONYM_GROUPS` | 26组 | 准确率判定用 |

**修改流程：** 只改这个文件 → Prompt自动同步 → 校验自动同步 → 基准测试自动更新。

---

### 3.3 stages/preprocessor.py — 图像预处理

**职责：** 图片加载 → 透视裁剪 → 缩放压缩 → base64编码。

**方法：**

| 方法 | 输入 | 输出 |
|------|------|------|
| `load_image(path)` | 图片路径 | PIL Image |
| `preprocess_image(img)` | PIL Image | JPEG bytes (1024×缩放) |
| `crop_regions(path)` | 图片路径 | `{ceiling, wall, floor} → base64` |
| `full_image_base64(path)` | 图片路径 | 全图 base64 |

**裁剪策略（针对透视效果图）：**
```
┌───────────────────┐
│    CEILING 0-30%  │  ← ceiling区域：顶面/吊顶
├───────────────────┤
│    WALL 25-75%    │  ← wall区域：墙面（含重叠确保完整）
├───────────────────┤
│    FLOOR 60-100%  │  ← floor区域：地面
└───────────────────┘
```
区域有重叠，保证过渡材质不被切丢。

---

### 3.4 stages/inferrer.py — 模型推理层

**职责：** Prompt构建 + Ollama通信 + JSON提取。

**核心类 `ModelInferrer`：**

| 方法 | 说明 |
|------|------|
| `infer(prompt, img_b64, model)` | 调用 Ollama /api/chat |
| `full_prompt` (property) | 全图结构化 Prompt（惰性初始化） |
| `health_check()` | 检查 Ollama 服务 |

**工具函数：**

| 函数 | 说明 |
|------|------|
| `build_full_prompt()` | 构建全图 Prompt（含枚举约束） |
| `build_crop_prompt(field)` | 构建裁剪区域 Prompt（单字段） |
| `extract_json(raw_text)` | 5层降级解析：直接→正则→修复逗号→单引号→组合 |
| `parse_single_field(raw, field)` | 从模型输出中提取单字段值 |
| `normalize_result(parsed)` | 归一化确保6个字段存在 |

**Prompt结构：** 枚举列表直接嵌入 Prompt，模型只能从列表中选词。

---

### 3.5 stages/validator.py — 校验层

**职责：** 枚举存在性检查 → 枚举模糊修正 → 空间-材质规则检查 → 规则模糊修正。

**核心类 `OutputValidator`：**

| 方法 | 说明 |
|------|------|
| `check_in_enum(value, field)` | 值是否在枚举列表内 |
| `fuzzy_match_in_enum(value, field)` | 枚举中模糊匹配（阈值0.8） |
| `check_space_rules(space, field, value)` | 值是否满足空间规则 |
| `fuzzy_match_in_rules(space, field, value)` | 规则中模糊匹配（阈值0.8） |
| `is_valid(value, field, space)` | 综合校验（枚举+规则） |
| `validate_and_fix(structured)` | 全量后验校验+修正，含告警记录 |

**校验链：**
```
字段值 → 枚举存在性 → 枚举模糊匹配 → 空间规则 → 规则模糊匹配 → 通过
  失败      失败         仍失败         失败       仍失败        跳过
  ↓         ↓            ↓              ↓          ↓            ↓
  触发重试  fuzzy修正    触发重试        fuzzy修正  规则最接近    最终通过
```

---

### 3.6 stages/retry_harness.py — 重试调度

**职责：** 发现异常输出 → 裁剪对应区域 → 针对性重推理 → 校验闭环。

**核心类 `RetryHarness`：**

| 方法 | 说明 |
|------|------|
| `_get_triggered_fields(structured)` | 检测触发重试的字段 |
| `execute(image_path, result, model)` | 执行重试闭环，返回修正结果+日志 |

**重试触发条件（任一满足即触发）：**
1. 字段值为 "未知" / "(空)"
2. 字段值不在枚举列表内
3. 字段值不满足空间-材质规则

**重试流程：**
```
全图推理 → 逐字段校验
  └── 发现问题字段
        └── 裁剪对应区域（ceiling/wall/floor）
              └── 区域推理（针对性 Prompt）
                    └── 替换字段值
                          └── 再次校验
                                └── 仍失败 → 最多2次 → 模糊兜底
```

---

### 3.7 pipeline.py — 主流水线

**职责：** 编排所有阶段。

**核心类 `VisionHarnessPipeline`：**

```
recognize(image_path, model)
  │
  ├── Stage 1: 全图推理 (Inferrer)
  │     └── 加载图片 → base64 → Ollama推理 → JSON提取 → 归一化
  │
  ├── Stage 2: 重试调度 (RetryHarness)
  │     └── 枚举校验 → 空间规则校验 → 发现问题 → 裁剪重试 → 模糊兜底
  │
  ├── Stage 3: 后验校验 (Validator)
  │     └── 枚举模糊修正 → 规则模糊修正 → 告警记录
  │
  └── 返回: {success, structured, raw_response, model_used, error, timing}
```

---

### 3.8 hooks.py — 全局拦截器

**职责：** 在各阶段插入日志、指标收集。

**Hook 点：**

| Hook | 时机 | 记录内容 |
|------|------|----------|
| `before_infer` | 推理前 | 模型名、图片路径、阶段 |
| `after_infer` | 推理后 | 耗时、输出长度 |
| `before_retry` | 重试前 | 字段名、当前值、触发原因 |
| `after_retry` | 重试后 | 新旧值、成功/失败 |
| `on_error` | 异常时 | 阶段名、异常详情 |
| `report_metrics` | 完成时 | 空间/材质/耗时/重试次数 |

---

## 四、数据流（完整链路）

```
用户上传效果图
       ↓
image_recognizer.recognize_image()  ← 兼容层，5行代码委托
       ↓
VisionHarnessPipeline.recognize()
       │
       ├── Preprocessor.full_image_base64()
       │   └── 加载 → RGBA→RGB → 缩放1024 → JPEG85 → base64
       │
       ├── Inferrer.infer(full_prompt, b64, model)
       │   └── Ollama /api/chat → raw_text
       │
       ├── extract_json(raw_text) → dict
       │
       ├── normalize_result(dict) → 6字段结构体
       │
       ├── RetryHarness.execute()
       │   ├── 逐字段 is_valid() 检查
       │   ├── 发现问题 → Preprocessor.crop_regions()
       │   ├── 裁剪区域 → Inferrer.infer(crop_prompt, crop_b64)
       │   └── 替换值 → 重复校验 → 最多2次
       │
       ├── Validator.validate_and_fix()
       │   ├── 枚举模糊匹配
       │   └── 空间-材质规则模糊匹配
       │
       └── 返回 {success, structured, timing}
            其中 structured = {
              space_type, wall_material,
              floor_material, ceiling_material,
              decor_style, remark,
              _warnings, _retry_log, _crop_retry_count, _timing
            }
```

---

## 五、配置修改指南

所有阈值集中在 `vision_harness/config.py`，改一处同步全链路：

| 需求 | 改什么 |
|------|--------|
| 裁剪比例不合适 | 改 `CROP_RATIOS` |
| 模型太慢要降分辨率 | 改 `MAX_IMAGE_DIM` |
| 模型输出太发散 | 降 `OLLAMA_TEMPERATURE` |
| 重试太激进 | 改 `MAX_RETRY_ATTEMPTS` |
| 换默认模型 | 改 `DEFAULT_MODEL` |
| 材料库要加新材料 | 改 `material_library.py` |
| 空间规则要调整 | 改 `material_library.py` 的 `SPACE_MATERIAL_RULES` |

---

## 六、门禁规则

上线/合并前必须全部满足：

| 检查项 | 阈值 | 当前 (qwen2.5:7b) |
|--------|:----:|:------------------:|
| 字段填充率 | ≥ 90% | ✅ 100% |
| 字段准确率 | ≥ 80% | ✅ 92% |
| 空间偏差 | ≤ 1/3 | ✅ 0/3 |
| 单图耗时 | ≤ 10s | ✅ 0.5s |
| 测试集完整性 | 3张全存在 | ✅ |

---

## 七、使用方式

```python
# 方式1：通过兼容层（main.py等存量代码无感知）
from backend.image_recognizer import recognize_image
result = recognize_image("path/to/image.jpg")

# 方式2：直接使用 Harness（新代码推荐）
from backend.vision_harness import VisionHarnessPipeline
pipeline = VisionHarnessPipeline()
result = pipeline.recognize("path/to/image.jpg")
# result.structured 包含6个字段 + 元数据
# result.timing 包含各阶段耗时

# 方式3：全局单例
from backend.vision_harness import get_pipeline
pipeline = get_pipeline()
result = pipeline.recognize("path/to/image.jpg")
```

---

## 八、扩展指南

### 新增一个 Stage

1. 在 `stages/` 下创建新模块，实现输入/输出标准接口
2. 在 `pipeline.py` 的 `_run()` 方法中插入新阶段
3. 在 `hooks.py` 中新增对应 Hook 点（可选）
4. 在 `config.py` 中新增相关配置项

### 替换一个 Stage

1. 实现与原 Stage 相同的接口签名
2. 在 `pipeline.py` 中替换构造参数
3. 跑 Benchmark 验证无回归

### 新增材料

1. 修改 `material_library.py` 中的枚举列表
2. 如果需要空间规则，追加到 `SPACE_MATERIAL_RULES`
3. 如果需要同义词，追加到 `SYNONYM_GROUPS`
4. Prompt 自动同步，校验自动同步

---

## 九、相关文件索引

| 文件 | 说明 |
|------|------|
| `backend/vision_harness/config.py` | 中心化配置 |
| `backend/vision_harness/material_library.py` | 材料库+规则+同义词 |
| `backend/vision_harness/pipeline.py` | 主流水线 |
| `backend/vision_harness/hooks.py` | 全局拦截器 |
| `backend/vision_harness/stages/preprocessor.py` | 图像预处理 |
| `backend/vision_harness/stages/inferrer.py` | 模型推理 |
| `backend/vision_harness/stages/validator.py` | 校验层 |
| `backend/vision_harness/stages/retry_harness.py` | 重试调度 |
| `backend/image_recognizer.py` | 兼容层（5行代码） |
| `docs/03-规范/基准测试说明与原始凭证.md` | 基准测试文档 |
| `docs/03-规范/benchmark_runner.py` | 基准测试脚本 |
