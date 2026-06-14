# BuildSight 家装智能自动报价系统

> 基于 PMBOK 6/7 + CMMI 标准体系的全生命周期项目管理教学案例

## 项目概述

| 项目 | 内容 |
|------|------|
| 项目名称 | BuildSight（家装智能自动报价系统） |
| 版本 | v0.9.0 |
| 技术栈 | Python FastAPI + Vue3 + SQLite + Ollama |
| 代码仓库 | [gitee.com/sjdliuxinfeng/buildsight.git](https://gitee.com/sjdliuxinfeng/buildsight.git) |
| 启动方式 | `bash start.sh` → http://localhost:8100/ |

## 目录结构（按软件工程阶段组织）

```
buildsight/
├── start.sh                          ← 一键启动脚本
├── backend/                          ← 后端（FastAPI）
├── frontend/                         ← 前端（Vue3）
└── docs/                             ← 项目管理文档库
    ├── 教学规范/                     ← 🆕 智能体工作规范手册
    │   └── BuildSight-智能体工作规范手册.md  ← 8个智能体的分工/代码/教学指南
    ├── 01-需求分析阶段/
    │   ├── 01-立项管理手册/
    │   │   └── BuildSight-立项管理手册.md     ← 项目章程
    │   ├── 02-需求分析报告/
    │   │   └── 功能规格说明书.md
    │   └── 03-需求追溯矩阵/
    │       └── BuildSight-需求追溯矩阵.md     ← 需求→设计→代码→测试 全追溯
    │
    ├── 02-系统设计阶段/
    │   ├── 01-系统架构设计/系统架构.md
    │   ├── 02-数据库设计/数据库设计.md
    │   ├── 03-API设计/API接口规范.md
    │   ├── 04-视觉识别架构/视觉识别Harness架构.md
    │   └── 05-模型调用规范/模型调用规范.md
    │
    ├── 03-编码实现阶段/
    │   ├── 01-模型基准测试/
    │   │   ├── 模型视觉识别Benchmark基准规范.md
    │   │   ├── 基准测试说明与原始凭证.md
    │   │   ├── benchmark_runner.py
    │   │   └── benchmark报告_*.md
    │   └── 02-门禁规范/三层门禁规范.md
    │
    ├── 04-测试验证阶段/                ← 待扩展（集成测试/性能测试）
    │   └── 01-功能测试用例/
    │
    ├── 05-项目收尾阶段/
    │   ├── 01-项目验收报告/
    │   │   └── BuildSight-项目验收报告.md     ← 验收结论：✅ 通过
    │   ├── 02-项目总结报告/
    │   │   └── BuildSight-项目总结报告.md     ← 经验教训+未来规划
    │   ├── 03-结题报告/
    │   │   └── 整体技术方案.md
    │   └── 04-项目任务书/
    │       └── 首期工程化任务书.md
    │
    └── 99-参考/
        ├── BuildSight_从0到1.pptx              ← 教学案例PPT
        └── 01-Copilot提示词库/
            └── Copilot提示词全集-项目分析指南.md  ← 92个项目管理提示词

## 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.8.0 | 2026-06 | 首期工程化完成 |
| v0.8.1~v0.8.10 | 2026-06 | 迭代优化（启动脚本/识别测试/多图/进度条/PPT入库） |
| **v0.9.0** | **2026-06** | **项目管理体系重构（PMBOK+CMMI标准）** |

## 项目管理标准

本项目的文档体系参考以下标准规范：

- **PMBOK 6** — 五大过程组、十大知识领域
- **PMBOK 7** — 八大绩效域、12条原则
- **CMMI** — 过程域与成熟度等级
- **GB/T 31102-2025** — 软件工程知识域
- **GB/T 42965-2023** — 软件组织能力域

## 快速启动

```bash
git clone https://gitee.com/sjdliuxinfeng/buildsight.git
cd buildsight
bash start.sh
# 访问 http://localhost:8100/
```
