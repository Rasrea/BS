# BuildSight — 家装智能自动报价系统

> **版本**：V2.3.0
> **项目地址**：`E:\ruanjian\PyCharm 2025.3.4\projects\BS`
> **启动端口**：8100

---

## 一、项目概述

BuildSight 是一套面向家装行业的**端到端智能报价系统**。它能够自动解析 CAD 施工图纸（DXF/DWG/PDF），提取房间空间、面积、尺寸等工程量数据；同时通过本地 AI 视觉模型识别效果图中的墙面/地面/顶面材质；最后将 CAD 精准数据与 AI 识别结果融合，自动生成包含人工费、材料费、管理费、税费的完整报价单，并支持 Excel 导出。

系统核心设计理念是**低成本、高可用、全本地推理**——不依赖任何商业 API，所有 AI 推理均在本地 Ollama 完成。

---

## 二、核心工作流

```
┌──────────────────────────────────────────────────────────────┐
│                        BuildSight 工作流                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ① 图纸分析                                                   │
│     ├─ CAD上传 → DXF/PDF 矢量解析 → 空间列表(名称+面积)            │
│     └─ 效果图上传 → AI视觉识别 → 材质信息(墙/地/顶)                 │
│                                                              │
│  ② 分层明细 (工程量清单)                                     │
│     空间 × 面(墙/地/顶) × 面积 × 材质                        │
│                                                              │
│  ③ 融合报价                                                  │
│     CAD工程量 + AI材质 → 同义词智能匹配 → 面积×单价 = 总价   │
│     (含材质差价/损耗率/管理费/税费)                          │
│                                                              │
│  ④ 施工工序                                                  │
│     按工种分组：拆除/水电/防水/瓦工/油漆/木工/保洁            │
│                                                              │
│  ⑤ 标准报价 & 导出                                           │
│     4 Sheet Excel：报价总表 / 分项明细 / 工程量清单 / 材质清单│
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、系统架构

### 3.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Vue 3 + Vite + TailwindCSS + Three.js | 18 个功能组件，SPA 单页应用 |
| **后端** | Python 3.10+ + FastAPI + Uvicorn | 40+ REST API 端点 |
| **数据库** | SQLite (aiosqlite) | 9 张业务表，自动 JSON 字段解析 |
| **CAD 解析** | ezdxf + PyMuPDF | DXF/DWG 矢量解析，PDF 矢量/视觉双路径 |
| **AI 视觉** | Ollama 本地模型 | qwen2.5:7b（默认）/ llava:7b（备用）/ qwen2.5vl（视觉专用） |
| **Excel 导出** | openpyxl | 4 Sheet 标准报价单 + 精细化工序报价 |

### 3.2 文件结构

```
BS/
├── backend/                      # FastAPI 后端
│   ├── main.py                   # 主入口 (40+ API 端点)
│   ├── cad_parser.py             # DXF/DWG 矢量解析
│   ├── pdf_parser.py             # PDF 施工图解析
│   ├── image_recognizer.py       # 视觉模型调用 (Vision Harness)
│   ├── image_preprocessor.py     # 图片预处理 (缩放/压缩/去EXIF)
│   ├── quantity_estimator.py     # 工程量计算
│   ├── fusion_validator.py       # CAD + AI 数据融合
│   ├── deduct_rule.py            # 门窗洞口扣减规则
│   ├── surface_breakdown.py      # 分层工程量(墙/地/顶)
│   ├── space_synonyms.py         # 空间名同义词匹配引擎 (698行)
│   ├── excel_export.py           # Excel 导出 (4Sheet + 工序报价)
│   ├── db.py                     # SQLite 数据库操作
│   ├── auth_proxy.py             # 认证代理
│   ├── benchmark.py              # 模型基准测试
│   ├── data/
│   │   └── cad_quote.db          # 运行时数据库
│   └── uploads/                  # 临时上传文件
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── App.vue               # 主入口 + Tab 导航
│   │   ├── components/           # 18 个功能组件
│   │   │   ├── CadUploader.vue           # CAD 图纸上传
│   │   │   ├── CadViewer.vue             # DXF 三维查看器
│   │   │   ├── ImageUploader.vue         # 效果图上传
│   │   │   ├── ImageQueue.vue            # 多图串行队列
│   │   │   ├── MergePanel.vue            # 数据融合面板
│   │   │   ├── QuoteDisplay.vue          # 报价展示
│   │   │   ├── SurfaceBreakdown.vue      # 分层明细
│   │   │   ├── PricingPanel.vue          # 定价配置 & 模板
│   │   │   ├── ProcessPanel.vue          # 施工工序管理
│   │   │   ├── StandardReport.vue        # 标准报价三表
│   │   │   ├── ComparisonPanel.vue       # CAD-AI 双源核对
│   │   │   ├── HistoryPanel.vue          # 历史记录
│   │   │   ├── VisionTestPanel.vue       # 视觉模型测试
│   │   │   └── LogViewer.vue             # 操作日志
│   │   └── services/api.js         # API 封装 (axios)
│   └── dist/                     # 构建产物
├── docs/                         # 项目文档库
├── scripts/                      # 自动化脚本
├── start.sh                      # 一键启动脚本
└── stop.sh                       # 一键停止脚本
```

### 3.3 三层任务门禁

系统在并发控制上采用三层防护机制：

| 层级 | 规则 | 实现 |
|------|------|------|
| **文件门禁** | 格式校验 + 大小限制 | CAD ≤120MB / 图片 ≤10MB / PDF ≤50MB |
| **混装门禁** | 禁止同一请求同时上传 CAD + 图片 | 接口级校验 |
| **状态机锁** | 全局任务串行，5 种状态互斥 | `idle` / `cad_running` / `ai_running` / `merge_running` / `export_running` |

### 3.4 安全执行器

- 超时熔断：融合操作 10s 超时、导出 15s 超时（CAD/AI 无超时）
- 子进程隔离：CAD 解析在 `ProcessPoolExecutor` 中运行，可强杀
- 操作留痕：所有关键操作记录到 `operation_logs` 表

---

## 四、核心功能详解

### 4.1 CAD 图纸解析

支持 **DXF / DWG / PDF** 三种格式：
- **DXF/DWG**：通过 `ezdxf` 进行矢量解析，提取房间名称、面积、周长、长宽尺寸
- **PDF**：优先走 PyMuPDF 矢量路径解析；若矢量为 0 则回退为视觉识别
- 支持超大图纸（已验证 104MB DXF 正常解析）
- CAD 房间智能命名：多行文字合并、多边形内优先匹配、短 CJK 文本回退

### 4.2 AI 效果图识别

通过 Ollama 本地视觉模型识别效果图中的材质信息：
- **识别内容**：空间类型、墙面材质、地面材质、顶面材质、装饰风格
- **Vision Harness 架构**：枚举约束 + 裁剪重试 + 规则引擎，识别准确率 92%
- **图片预处理**：最长边 1024px / JPEG 85% 质量 / 去 EXIF / RGBA→RGB，文件缩小约 80%
- **模型切换**：前端下拉支持 LLaVA / Qwen2.5 / Qwen2.5-VL 三模型切换
- **多图串行队列**：支持多选效果图逐张调用识别

### 4.3 智能数据融合

CAD 工程量与 AI 材质识别结果的自动关联：

| 匹配策略 | 说明 |
|----------|------|
| 精确匹配 | 空间名完全一致直接绑定 |
| 子串匹配 | 部分名称匹配 |
| 同义词匹配 | 698 行同义词库（客厅=大厅=起居室等，6 层匹配策略） |
| 拼音匹配 | 中文拼音近似匹配 |
| 手动绑定 | 前端可视化面板人工兜底 |
| 一键确认 | `auto_confirm_match` 接口全链路绑定 |

### 4.4 分层工程量计算

对每个空间独立计算三个表面的工程量：
- **墙面**：净面积（扣除门窗洞口）
- **地面**：实际铺贴面积
- **顶面**：吊顶面积

### 4.5 融合报价计算

```
总价 = 基础价 + 材质差价 + 造型费 + 损耗 + 管理费 + 税费
```

- **基础价**：总面积 × 基础单价
- **材质差价**：按空间 × 表面类型 × 材质溢价系数计算
- **损耗**：基础价 × 损耗率（默认 3%）
- **管理费**：基础价 × 管理费率（默认 5%）
- **税费**：(基础价 + 损耗 + 管理费) × 税率（默认 3%）

### 4.6 报价模板体系

- **标准型模板**：15 项计价分项（墙面 4 + 地面 4 + 顶面 4 + 通用 3）
- **经济型模板**：6 项计价分项（价格为标准型的 70-80%）
- 支持前端一键切换模板
- 费率配置分组展示，支持滑块调整面积系数/扣减系数

### 4.7 施工工序管理

- 10 项标准工序：拆除、水电、防水、瓦工、油漆、木工、安装、保洁等
- 每项工序含：单价、单位、标准工期、适用空间
- 支持工序 × 空间映射汇总
- 工序单价批量更新

### 4.8 Excel 导出

**标准报价导出**（4 Sheet）：
| Sheet | 内容 |
|-------|------|
| 报价总表 | 项目概况 + 工种汇总金额 |
| 分项明细 | 空间 × 类别 × 数量 × 单价 = 小计 |
| 工程量清单 | 106 空间 × 10 列（墙/地/顶分层） |
| 材质清单 | 空间 ↔ 材质对照表 |

**精细化工序报价导出**（4 Sheet）：
| Sheet | 内容 |
|-------|------|
| 工序报价总表 | 按工序汇总人工/材料/辅料 |
| 空间→工序明细 | 按空间分墙/顶/地 |
| 分层工程量 | 10 列表格 |
| 材质与计价项对照 | 材质 ↔ 标准计价项映射 |

---

## 五、数据库设计

系统使用 SQLite 存储，共 9 张核心表：

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `drawing_records` | 图纸上传记录 | filename, parse_status, cad_result_json |
| `cad_analysis_results` | CAD 解析结果 | space_name, area, detail_json(分层工程量) |
| `image_analysis_results` | AI 识别结果 | recognized_space, material_info, confidence |
| `quote_records` | 报价记录 | base_price, final_price, quote_detail_json |
| `operation_logs` | 操作日志 | task_type, action, trace_id, status |
| `system_settings` | 系统配置 | key-value 定价参数 |
| `pricing_templates` | 报价模板 | name(type), is_default |
| `pricing_items` | 计价分项 | surface_type, item_name, unit_price_* |
| `construction_processes` | 施工工序 | name, work_type, unit_price, standard_days |

---

## 六、API 接口概览

系统提供 **40+ REST API 端点**，核心接口：

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/system/status` | GET | 系统状态（LLaVA 连通性、DB 连接） |
| `/api/system/health` | GET | 健康检查（模型/DB/磁盘/文件服务） |
| `/api/analyze_full` | POST | CAD 图纸解析 + 自动报价 |
| `/api/analyze` | POST | 效果图 AI 材质识别 |
| `/api/analyze_pdf` | POST | PDF 施工图识别 |
| `/api/vision_test` | POST | 视觉模型诊断测试 |
| `/api/data_merge` | POST | CAD + AI 数据融合报价 |
| `/api/quote/{id}/items` | PUT | 报价项编辑 + 自动重算 |
| `/api/export_excel` | POST | 生成 4 Sheet Excel 报价 |
| `/api/download_excel/{id}` | GET | 下载 Excel 文件 |
| `/api/export/process_quote` | POST | 精细化工序报价导出 |
| `/api/history` | GET | 报价历史分页查询 |
| `/api/history/{id}` | GET/DELETE | 报价详情 / 删除 |
| `/api/spaces/{id}/breakdown` | GET | 分层工程量 + 材质关联 |
| `/api/spaces/{id}/comparison` | GET | CAD-AI 双源数据比对 |
| `/api/quote/{id}/standard_report` | GET | 标准报价三表（综合/分项/工序） |
| `/api/pricing/templates` | GET/POST | 报价模板管理 |
| `/api/pricing/items` | GET/POST/PUT/DELETE | 计价分项 CRUD |
| `/api/processes` | GET/POST/PUT/DELETE | 施工工序 CRUD |
| `/api/settings/pricing` | GET/POST | 定价配置 |
| `/api/settings/vl_model` | GET/POST | 视觉模型管理 |
| `/api/logs` | GET | 操作日志 |

---

## 七、启动与部署

### 前置条件

| 项目 | 要求 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+（仅前端构建需要） |
| Ollama | 已安装并运行（http://localhost:11434） |
| 视觉模型 | `qwen2.5:7b`（推荐）或 `llava:7b` |
| 内存 | 8GB+（CPU 推理）/ 4GB+（GPU 推理） |
| 磁盘 | 5GB+ |

### 启动步骤

```powershell
# 1. 安装 Ollama: https://ollama.com
# 2. 拉取视觉模型
ollama pull qwen2.5:7b
ollama pull llava:7b

# 3. 构建前端
cd frontend
npm install --legacy-peer-deps
npm run build

# 4. 启动后端
cd ../backend
python main.py

# 5. 浏览器访问 http://localhost:8100
```

或直接使用一键启动脚本（Linux/macOS/WSL）：

```bash
bash start.sh
```

### 停止服务

```powershell
# Windows PowerShell
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
```

或使用脚本：

```bash
bash stop.sh
```

---

## 八、关键指标

| 指标 | 数值 |
|------|------|
| 单图最大解析空间 | 106 个空间 |
| 单图最大解析面积 | 997.29 ㎡ |
| 支持 CAD 格式 | DXF / DWG / PDF |
| 支持图片格式 | JPG / PNG / WebP / BMP |
| 视觉模型准确率 | 92%（宽松匹配） |
| 同义词匹配库 | 698 行，6 层策略 |
| API 端点总数 | 40+ |
| 前端组件数 | 18 个 |
| 后端 Python 文件 | 26 个 |
