# BuildSight 家装智能自动报价系统 — 文档索引

**v0.8.0**

---

## 演示材料

| 文件 | 说明 |
|------|------|
| 📊 `BuildSight_从0到1.pptx` | 项目演示PPT（6页，面向管理层/客户） |

## 01-需求

| 文件 | 说明 |
|------|------|
| 📄 `功能规格.md` | 功能需求定义（8项已实现 + 待完成 + 二期规划） |

## 02-设计

| 文件 | 说明 |
|------|------|
| 📄 `系统架构.md` | 整体架构图 + 双线数据流 + 三层门禁 |
| 📄 `数据库设计.md` | 9张表结构详解 + detail_json/material_info v2.0 |
| 📄 `API设计.md` | 全部10个接口规范 + 统一响应格式 |
| 📄 `视觉识别Harness架构.md` | BuildSight Harness：5阶段流水线 + 重试闭环 |

## 03-规范

| 文件/目录 | 说明 |
|-----------|------|
| 📄 `门禁规范.md` | 任务状态机 + 文件门禁 + 超时熔断 + 前端互斥 |
| 📄 `模型调用规范.md` | Ollama结构化Prompt + 三层模型策略 |
| 📄 `模型视觉识别Benchmark基准规范.md` | 标准化评测流程 + 4项门禁 + 归档规范 |
| 📄 `基准测试说明与原始凭证.md` | 核心指标定义 + Ground Truth + 准确率演进(16.7%→92%) |
| 📄 `benchmark_runner.py` | 自动化基准评测脚本（476行，可复跑） |
| 📁 `benchmark_reports/` | 评测报告归档（保留最新2-3份） |

## 04-方案

| 文件 | 说明 |
|------|------|
| 📄 `整体方案.md` | 推进方案（P0/P1/P2 + 四阶段排期） |
| 📄 `首期任务书.md` | 完整首期工程化任务书（437行，最完整） |
| 📄 `规范化开发拆分方案.md` | 7智能体分工 + 三环境隔离 + 管控规则 |

---

## 代码结构

```
cad/
├── backend/             # FastAPI + SQLite 后端
│   ├── main.py              # 主服务（10组API端点）
│   ├── db.py                # 数据库层
│   ├── cad_parser.py        # DXF矢量解析
│   ├── image_recognizer.py  # 视觉识别兼容层
│   ├── surface_breakdown.py # 分层工程量
│   ├── quantity_estimator.py# 报价引擎
│   ├── fusion_validator.py  # 数据融合
│   ├── excel_export.py      # Excel导出
│   ├── auth_proxy.py        # 公网Basic Auth代理
│   ├── vision_harness/      # Harness架构(8模块)
│   └── start.sh             # 启动脚本
├── frontend/            # Vue3 + Vite
│   └── src/components/     # 14个组件
└── docs/                # 本文档目录
```
