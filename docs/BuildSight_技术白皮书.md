# BuildSight 家装智能报价系统 · 技术白皮书

> **版本 V1.1.0** · 2026-06-18  
> CAD解析 · AI视觉识别 · 数据融合 · 自动报价 · Excel导出

---

## 一、概述

BuildSight 是一套面向家装行业的智能自动报价系统，实现从 CAD 施工图纸和室内效果图到完整报价单的端到端自动化流程。系统以低成本、高可用、可演示为核心设计目标，不依赖昂贵的商业 API，全部推理在本地完成。

### 核心能力

| 能力 | 说明 |
|------|------|
| CAD 图纸解析 | DXF/DWG 矢量解析，提取空间、面积、周长、尺寸 |
| PDF 施工图识别 | PyMuPDF 矢量路径提取，无矢量时回退视觉识别 |
| 效果图 AI 识别 | 本地视觉模型（qwen2.5vl / LLaVA）识别墙面/地面/吊顶材质 |
| 数据智能融合 | CAD 空间名与 AI 材质识别结果同义词匹配，自动关联 |
| 融合报价计算 | 基础价 + 材质差价 + 损耗 + 管理费 + 税费，支持多模板 |
| Excel 报价导出 | 4 Sheet 完整报价单：总表、分项明细、工程量清单、材质清单 |
| 精细化工序报价 | 按空间→墙/顶/地→施工工序三级分层报价 |

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 (Vue 3)                        │
│  CadUploader · ImageUploader · MergePanel           │
│  PricingPanel · StandardReport · HistoryPanel        │
│  ... 共 20 个组件                                    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST (axios)
┌──────────────────────▼──────────────────────────────┐
│                后端 (FastAPI + Uvicorn)               │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ cad_     │  │ pdf_     │  │ space_           │   │
│  │ parser.py│  │ parser.py│  │ synonyms.py      │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ db.py    │  │excel_    │  │ main.py          │   │
│  │ (SQLite) │  │export.py │  │ (40 API 端点)    │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│                                                      │
│  三层任务门禁: 混装门禁 · 文件门禁 · 状态机锁         │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              本地推理层 (Ollama)                      │
│  ┌─────────────────┐  ┌──────────────────────────┐  │
│  │ qwen2.5vl:latest │  │ LLaVA 7B (fallback)      │  │
│  │ 视觉模型 (首选)   │  │                         │  │
│  └─────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 前端 | Vue 3 + Vite + TailwindCSS | — |
| 后端 | Python 3.11 + FastAPI + Uvicorn | — |
| 数据库 | SQLite (通过 aiosqlite) | — |
| CAD 解析 | ezdxf (DXF) + PyMuPDF (PDF) | — |
| 视觉模型 | Ollama + qwen2.5vl:latest | — |
| Excel 导出 | openpyxl | — |
| 代码质量 | Pre-commit Quality Gate (9 项检查) | — |

### 文件结构（后端 26 Python 文件，前端 20 Vue 组件，总计 8,228 行）

```
cad/
├── backend/
│   ├── main.py              # FastAPI 主入口 (40 API)
│   ├── cad_parser.py        # DXF 矢量解析
│   ├── pdf_parser.py        # PDF 矢量+视觉解析
│   ├── space_synonyms.py    # 空间名同义词匹配引擎
│   ├── excel_export.py      # Excel 导出 (4 Sheet + 工序报价)
│   ├── db.py                # SQLite 数据库操作
│   └── data/cad_quote.db    # 运行时数据库
├── frontend/
│   └── src/
│       ├── App.vue          # 主入口 + Tab 导航
│       ├── services/api.js  # API 封装
│       └── components/      # 20 个功能组件
├── scripts/
│   ├── quality_gate.sh      # 5 阶段门禁脚本
│   ├── regression_test.py   # 62 项回归测试
│   └── API_CONTRACT.md      # 46 API 端点契约文档
└── docs/
    ├── 01-需求/             # 需求文档
    ├── 02-设计/             # 设计文档
    ├── 03-规范/             # 编码规范
    ├── 04-方案/             # 技术方案
    └── 05-运维/             # 运维手册
```

---

## 三、核心工作流

### 3.1 完整业务流程

```
上传CAD图纸 ──→ CAD解析 ──→ 空间/面积/工程量
     +                              │
上传效果图 ──→ AI视觉识别 ──→ 材质信息
                                    │
                               ┌────▼────┐
                               │ 数据融合 │ ← 同义词匹配
                               └────┬────┘
                                    │
                          ┌─────────▼─────────┐
                          │    报价计算        │
                          │ 基础价+材质差价    │
                          │ +损耗+管理费+税费  │
                          └─────────┬─────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │         Excel 导出           │
                     │ 报价总表·分项明细·工程量·材质 │
                     └─────────────────────────────┘
```

### 3.2 空间名同义词匹配

系统内置智能空间名同义词库，解决 CAD 图纸命名与 AI 识别命名不一致的问题：

| 标准名 | 同义词 |
|--------|--------|
| 客厅 | 大厅、起居室、living room |
| 主卧 | 主人房、主卧室、master bedroom |
| 次卧 | 卧室、客房、小孩房、bedroom |
| 厨房 | 中厨、西厨、kitchen |
| 卫生间 | 厕所、洗手间、浴室、bathroom |
| 阳台 | 露台、生活阳台、休闲阳台 |

### 3.3 三层任务门禁

系统在并发控制上采用三层防护，杜绝状态冲突：

1. **混装门禁** — 单次请求禁止同时上传 CAD 和效果图以外的混合文件
2. **文件门禁** — 上传文件类型、大小、格式严格校验
3. **状态机锁** — 全局任务状态机（idle/running），任何操作前必须获取锁

---

## 四、API 接口概览

系统提供 **40 个 REST API 端点**，核心接口如下：

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/system/status` | GET | 系统状态（LLaVA可用性、DB连接） |
| `/api/analyze_full` | POST | CAD 图纸解析（自动分流 DXF/PDF） |
| `/api/analyze` | POST | 效果图 AI 识别 |
| `/api/analyze_pdf` | POST | PDF 施工图解析 |
| `/api/vision_test` | POST | 视觉模型诊断测试 |
| `/api/data_merge` | POST | CAD + AI 数据融合报价 |
| `/api/export_excel` | POST | 生成 4 Sheet 报价 Excel |
| `/api/download_excel/{id}` | GET | 下载 Excel 文件 |
| `/api/history` | GET | 报价历史记录 |
| `/api/settings/pricing` | GET/POST | 定价配置读取/更新 |
| `/api/processes` | GET | 施工工序列表 |
| `/api/quote/{id}/standard_report` | GET | 标准报价报表 |
| `/api/logs` | GET | 操作日志 |

---

## 五、部署说明

### 5.1 最低要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux / macOS / Windows WSL |
| Python | 3.10+ |
| Node.js | 18+（仅开发构建需要） |
| Ollama | 已安装并运行 |
| 视觉模型 | qwen2.5vl:latest（推荐）或 llava:7b |
| 内存 | 8GB+（CPU 推理） / 4GB+（GPU 推理） |
| 磁盘 | 5GB+ |

### 5.2 快速启动

```bash
# 1. 安装 Ollama 并拉取模型
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5vl:latest

# 2. 启动后端
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8100

# 3. 访问
打开浏览器访问 http://localhost:8100
```

### 5.3 一键启动脚本

```bash
bash start.sh
```

自动完成：环境检查 → 依赖安装 → Ollama 模型检查 → 端口清理 → 服务启动。

### 5.4 质量门禁

每次 `git commit` 自动触发 Quality Gate，包含 5 阶段 9 项检查：

```
阶段1: Python语法检查 + 前端构建
阶段2: LLaVA在线 + 数据库连接
阶段3: 系统空闲状态
阶段4: 62项回归测试 + 基线比对
阶段5: 接口契约完整性
```

---

## 六、数据库设计

### 核心表

| 表名 | 行数 | 用途 |
|------|------|------|
| `drawing_records` | 12 | CAD 图纸上传记录 |
| `cad_analysis_results` | 1,084 | CAD 解析结果（空间/面积/尺寸） |
| `image_analysis_results` | 26 | 效果图 AI 识别结果（材质） |
| `quote_records` | 13 | 报价记录（含融合数据） |
| `operation_logs` | 61 | 操作日志（审计溯源） |
| `system_settings` | 23 | 定价配置项 |
| `pricing_templates` | 2 | 报价模板（标准型/经济型） |
| `pricing_items` | 21 | 计价分项（按面类型分组） |
| `construction_processes` | 10 | 施工工序（含单价/工期） |

---

## 七、版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| V1.0.0 | — | 初始版本 |
| V1.0.1~V1.0.4 | — | DXF 解析、AI 识别、融合报价基础功能 |
| V1.0.5 | — | PDF 矢量路径解析模块（独立 pdf_parser.py） |
| V1.0.6 | — | 5 项问题修复：接口契约、状态刷新、UI 同步 |
| V1.0.7 | — | Quality Gate 门禁体系（pre-commit 9 项检查） |
| V1.0.8 | — | 构建产物/数据库停止追踪 |
| V1.0.9 | — | 4 项 Bug 修复：Excel 空间列/标题、融合刷新、定价同步 |
| **V1.1.0** | 2026-06-18 | 定价扣减系数步进对齐 + 融合后自动跳转标准报价 |

---

## 八、关键指标

| 指标 | 数值 |
|------|------|
| CAD 解析空间数（单图） | 106 个空间 |
| CAD 解析总面积 | 997.29 ㎡ |
| AI 识别准确率（宽松） | 67% |
| AI 识别速度 | ~1.7 秒/张（GPU） |
| API 端点总数 | 40 个 |
| 回归测试 | 62 项 |
| 前端组件 | 20 个 |
| 后端代码量 | 8,228 行 |

---

## 九、路线图

### 首期已完成 ✅
- [x] CAD 图纸解析（DXF + PDF）
- [x] AI 视觉识别材质
- [x] 数据智能融合报价
- [x] 前端可视化完整流程
- [x] Excel 报价导出
- [x] 定价配置管理
- [x] 三层任务门禁
- [x] Quality Gate 代码质量门禁

### 二期规划 🚧
- [ ] 报价模板&定价体系优化
- [ ] 多图纸批量处理
- [ ] PDF 施工图识别增强
- [ ] 公网部署与访问鉴权
- [ ] 多效果图串行队列
- [ ] CAD 房间命名解析优化

---

> **BuildSight** — 让家装报价从人工变智能  
> 项目地址：https://gitee.com/sjdliuxinfeng/buildsight  
> 本文档对应版本：V1.1.0
