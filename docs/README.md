# 家装智能自动报价系统 — 文档索引

```
docs/
├── 01-需求/
│   └── 功能规格.md          # 功能需求定义
├── 02-设计/
│   ├── 系统架构.md          # 整体架构 + 数据流
│   ├── 数据库设计.md         # 7张表结构
│   └── API设计.md           # 全部接口规范
├── 03-规范/
│   ├── 门禁规范.md          # 任务锁/并发/文件校验
│   └── 模型调用规范.md       # LLaVA结构化调用 + 三层模型策略
├── 04-方案/
│   └── 整体方案.md          # 完整推进方案（核心里程碑）
└── README.md                # 本索引
```

代码结构：
```
cad/
├── backend/             # FastAPI + SQLite 后端
│   ├── main.py              # 主服务（~1170行，8组API端点）
│   ├── db.py                # 数据库层
│   ├── cad_parser.py        # DXF矢量解析
│   ├── image_recognizer.py  # LLaVA结构化识别
│   ├── surface_breakdown.py # 分层工程量
│   ├── quantity_estimator.py# 报价引擎
│   ├── fusion_validator.py  # 数据融合
│   ├── excel_export.py      # Excel导出
│   └── start.sh             # 启动脚本
├── frontend/            # Vue3 + Vite
│   └── src/components/     # 14个组件
└── docs/                # 本文档目录
```
