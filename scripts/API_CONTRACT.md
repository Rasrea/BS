# 家装智能自动报价系统 — API 接口契约

> 版本: v2.1.0  
> 最后更新: 2025-07-01  
> 用途: 前后端对齐契约，杜绝接口不匹配

---

## 目录

1. [系统状态与健康](#1-系统状态与健康)
2. [CAD 解析与报价](#2-cad-解析与报价)
3. [效果图识别](#3-效果图识别)
4. [PDF 识别](#4-pdf-识别)
5. [视觉模型诊断](#5-视觉模型诊断)
6. [数据融合](#6-数据融合)
7. [报价编辑与模板](#7-报价编辑与模板)
8. [Excel 导出与下载](#8-excel-导出与下载)
9. [历史记录](#9-历史记录)
10. [操作日志](#10-操作日志)
11. [定价配置](#11-定价配置)
12. [视觉模型管理](#12-视觉模型管理)
13. [施工工序管理](#13-施工工序管理)
14. [分层工程量](#14-分层工程量)
15. [空间编辑](#15-空间编辑)
16. [自动匹配建议与确认](#16-自动匹配建议与确认)
17. [图纸与识别结果查询](#17-图纸与识别结果查询)
18. [双源数据核对](#18-双源数据核对)
19. [标准报价表](#19-标准报价表)
20. [兼容旧版接口](#20-兼容旧版接口)
21. [通用错误码总表](#21-通用错误码总表)
22. [通用成功响应格式](#22-通用成功响应格式)

---

## 1. 系统状态与健康

### GET /api/system/status
- **描述**: 实时查询系统任务锁状态、服务连通性
- **入参**: 无
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "message": "操作成功",
    "data": {
      "task_state": "idle",
      "trace_id": "",
      "llava_available": true,
      "db_path": "/path/to/db",
      "db_connected": true,
      "upload_dir": "/path/to/uploads",
      "export_dir": "/path/to/exports"
    },
    "task_status": "idle",
    "trace_id": ""
  }
  ```
- **状态锁**: 不需要（常驻接口）
- **调用方**: App.vue → `API.getStatus()` (定时轮询)
- **错误码**: 无

---

### GET /api/system/health
- **描述**: 检测模型、数据库、文件服务健康状态
- **入参**: 无
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "status": "healthy|degraded",
      "llava": true|false,
      "db": true|false,
      "upload_dir": true,
      "free_disk_gb": 42.5,
      "issues": []
    }
  }
  ```
- **状态锁**: 不需要（常驻接口）
- **调用方**: 系统监控面板（内部健康检查）
- **错误码**: 无

---

## 2. CAD 解析与报价

### POST /api/analyze_full
- **描述**: CAD 文件解析 + 工程量计算 + 自动报价（核心接口1）
- **入参** (multipart/form-data):
  | 字段 | 类型 | 必填 | 默认值 | 说明 |
  |------|------|------|--------|------|
  | cad_file | UploadFile | 是 | — | .dxf / .dwg / .pdf, ≤120MB |
  | project_name | str (Form) | 否 | "装修工程" | 项目名称 |
  | quote_db | str (Form) | 否 | null | 未使用，保留参数 |
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "message": "操作成功",
    "data": {
      "drawing_id": 1,
      "spaces": [
        {
          "name": "客厅",
          "area": 35.5,
          "area_sqm": 35.5,
          "length": 7.0,
          "width": 5.0,
          "dimensions": { "width_m": 5.0, "height_m": 7.0 }
        }
      ],
      "space_count": 5,
      "total_area": 120.33,
      "unit_price": 9374,
      "base_price": 1128289.42,
      "manage_fee": 56414.47,
      "tax_fee": 33848.68,
      "final_price": 1218552.57,
      "project_name": "装修工程"
    },
    "task_status": "idle",
    "trace_id": "20250701123045abc123"
  }
  ```
- **状态锁**: 需要，占用 `cad_running`（仅 `idle` 可调用）
- **调用方**: CadUploader.vue, CadBatchUploader.vue → `API.analyzeCad(file, projectName)`
- **错误码**:
  | 状态码 | 说明 |
  |--------|------|
  | 400 | 未上传文件 |
  | 415 | 不支持的文件格式 |
  | 413 | 文件过大（>120MB） |
  | 409 | 系统忙（有任务正在执行） |
  | 504 | CAD 解析超时或失败（矢量+视觉回退均失败） |
  | 500 | 解析无结果返回 |

---

### POST /api/upload/clear
- **描述**: 清空前端未提交的临时上传文件
- **入参**: 无
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": { "deleted_count": 5 }
  }
  ```
- **状态锁**: 检查但不需要锁——仅当系统非 `idle` 时返回 409
- **调用方**: App.vue 页面卸载/切换时 → `API.post('/upload/clear')`
- **错误码**: 409(系统忙)

---

## 3. 效果图识别

### POST /api/analyze
- **描述**: 单张效果图材质/空间同步识别（核心接口2）
- **入参** (multipart/form-data):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | image_file | UploadFile | 是 | jpg/png/webp/bmp/pdf, ≤10MB |
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "image_result_id": 1,
      "filename": "客厅效果图.jpg",
      "recognized_space": "客厅",
      "wall_material": "乳胶漆",
      "floor_material": "地砖",
      "ceiling_material": "石膏板吊顶",
      "decor_style": "现代简约",
      "remark": "",
      "confidence": 0.85,
      "model_used": "llava:7b",
      "structured": {
        "space_type": "客厅",
        "wall_material": "乳胶漆",
        "floor_material": "地砖",
        "ceiling_material": "石膏板吊顶",
        "decor_style": "现代简约",
        "remark": ""
      },
      "warning": ""  // 仅识别失败时出现
    },
    "task_status": "idle",
    "trace_id": "20250701123045def456"
  }
  ```
- **状态锁**: 需要，占用 `ai_running`（仅 `idle` 可调用）
- **调用方**: ImageUploader.vue, ImageQueue.vue → `API.analyzeImage(file)`
- **错误码**:
  | 状态码 | 说明 |
  |--------|------|
  | 400 | 未上传图片 |
  | 415 | 不支持的图片格式 |
  | 413 | 图片过大（>10MB） |
  | 409 | 系统忙 |
  | 504 | AI 识别超时或失败 |
  | 500 | AI 识别无结果 |

---

## 4. PDF 识别

### POST /api/analyze_pdf
- **描述**: PDF 施工图识别——PDF→图片→复用 LLaVA 逐页识别
- **入参** (multipart/form-data):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | pdf_file | UploadFile | 是 | .pdf, ≤50MB |
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "filename": "施工图.pdf",
      "total_pages": 5,
      "results": [
        {
          "page": 1,
          "total_pages": 5,
          "recognized_space": "客厅",
          "wall_material": "乳胶漆",
          "floor_material": "地砖",
          "ceiling_material": "石膏板",
          "confidence": true
        }
      ]
    },
    "task_status": "idle",
    "trace_id": "abc123"
  }
  ```
- **状态锁**: 需要，占用 `ai_running`
- **调用方**: App.vue → `API.post('/analyze_pdf', fd)`
- **错误码**: 400(无文件/PDF为空), 415(格式不支持), 413(文件过大), 409(系统忙), 504(识别超时)

---

## 5. 视觉模型诊断

### POST /api/vision_test
- **描述**: 独立视觉模型测试接口（诊断用），无锁、无数据库写、无30s超时
- **入参** (multipart/form-data):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | image_file | UploadFile | 是 | jpg/png/webp, ≤10MB |
  | model | str (Form) | 否 | 留空用默认，或传具体模型名 |
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "timings": { "preprocess": 0.3, "inference": 2.1, "total": 2.5 },
      "model_used": "qwen2.5:7b",
      "available_models": [{"key": "llava:7b", "label": "...", "installed": true, "active": false}],
      "image_info": { "filename": "test.jpg", "original_size_kb": 512.0, "processed_size_kb": 128.0 },
      "raw_result": { ... }
    }
  }
  ```
- **状态锁**: **不需要**
- **调用方**: VisionTestPanel.vue → `API.post('/vision_test', fd)`
- **错误码**: 400(无图片), 415(格式不支持), 413(文件过大)

---

## 6. 数据融合

### POST /api/data_merge
- **描述**: CAD 工程量 + 已确认材质数据融合，生成最终报价（核心接口3）
- **入参** (multipart/form-data):
  | 字段 | 类型 | 必填 | 默认值 | 说明 |
  |------|------|------|--------|------|
  | cad_result_id | int (Form) | 是 | — | 图纸ID（drawing_id） |
  | image_result_ids | str (Form) | 否 | "[]" | JSON数组，效果图结果ID列表 |
  | manual_bindings | str (Form) | 否 | "[]" | JSON数组，人工绑定 {cad_name, material_info} |
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "quote_id": 1,
      "base_price": 1128289.42,
      "material_diff_price": 12500.00,
      "process_add_price": 601.65,
      "loss_price": 33848.68,
      "manage_fee": 56414.47,
      "tax_fee": 41176.55,
      "final_price": 1280830.77,
      "items": [
        {
          "space_name": "客厅",
          "category": "墙面工程",
          "project_name": "乳胶漆墙面",
          "quantity": 88.75,
          "unit": "㎡",
          "material_unit_price": 18,
          "labor_unit_price": 22,
          "subtotal": 3550.00,
          "source": "CAD工程量 + AI材质识别",
          "material_name": "乳胶漆",
          "material_source": "ai",
          "process_name": "油漆工程",
          "process_id": 1
        }
      ],
      "space_count": 5,
      "total_area": 120.33
    },
    "task_status": "idle",
    "trace_id": "abc456"
  }
  ```
- **状态锁**: 需要，占用 `merge_running`（仅 `idle` 可调用）
- **调用方**: MergePanel.vue → `API.dataMerge(cadResultId, imageResultIds, bindings)`
- **错误码**:
  | 状态码 | 说明 |
  |--------|------|
  | 422 | CAD 数据为空或不完整 |
  | 409 | 系统忙 |
  | 500 | 融合失败 |

---

## 7. 报价编辑与模板

### PUT /api/quote/{quote_id}/items
- **描述**: 更新报价明细项并自动重算汇总金额
- **入参** (JSON body):
  ```json
  {
    "items": [
      {
        "quantity": 100.0,
        "material_unit_price": 18,
        "labor_unit_price": 22,
        "material_name": "乳胶漆",
        "project_name": "乳胶漆墙面",
        "category": "墙面工程"
      }
    ]
  }
  ```
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "quote_id": 1,
      "base_price": 8800.00,
      "material_diff_price": 0,
      "process_add_price": 0,
      "loss_price": 264.00,
      "manage_fee": 440.00,
      "tax_fee": 285.12,
      "final_price": 9789.12,
      "items": [ ... ]
    }
  }
  ```
- **状态锁**: 需要，占用 `merge_running`
- **调用方**: QuoteDisplay.vue → `API.put('/quote/{id}/items', {items})`
- **错误码**: 404(报价不存在), 422(缺items参数), 409(系统忙), 500(编辑失败)

---

### GET /api/pricing/templates
- **描述**: 获取所有报价模板
- **入参**: 无
- **出参**: `{success, data: [{id, name, is_default, ...}]}`
- **状态锁**: 不需要
- **调用方**: PricingPanel.vue → `API.get('/pricing/templates')`
- **错误码**: 无

### POST /api/pricing/templates/switch
- **描述**: 切换默认报价模板
- **入参** (Form): `template_id: int(...)`
- **出参**: `{success, data: {active_template_id}}`
- **状态锁**: 不需要（仅读操作本身）
- **调用方**: PricingPanel.vue → `API.post('/pricing/templates/switch', fd)`
- **错误码**: 无

### GET /api/pricing/items
- **描述**: 获取计价分项，可按模板筛选
- **入参** (Query): `template_id: int (可选)`
- **出参**: `{success, data: [{id, template_id, surface_type, item_name, unit, unit_price_material, unit_price_labor, ...}]}`
- **状态锁**: 不需要
- **调用方**: PricingPanel.vue → `API.get('/pricing/items?template_id=...')`
- **错误码**: 无

### POST /api/pricing/items
- **描述**: 新增计价分项
- **入参** (Form): `template_id, surface_type, item_name, unit, unit_price, unit_price_material, unit_price_labor, unit_price_aux, sort_order, description`
- **出参**: `{success, data: {id}}`
- **状态锁**: 不需要
- **调用方**: PricingPanel.vue → `API.post('/pricing/items', fd)`
- **错误码**: 无

### PUT /api/pricing/items/{pid}
- **描述**: 更新计价分项
- **入参** (Form): `item_name, surface_type, unit, unit_price, unit_price_material, unit_price_labor, unit_price_aux, sort_order, description` (均为可选)
- **出参**: `{success, data: {id}}`
- **状态锁**: 不需要
- **调用方**: PricingPanel.vue → `API.put('/pricing/items/{pid}', fd)`
- **错误码**: 无

### DELETE /api/pricing/items/{pid}
- **描述**: 删除计价分项
- **入参**: 无
- **出参**: `{success, data: {id}}`
- **状态锁**: 不需要
- **调用方**: PricingPanel.vue → `API.delete('/pricing/items/{pid}')`
- **错误码**: 无

---

## 8. Excel 导出与下载

### POST /api/export_excel
- **描述**: 生成 4Sheet 报价 Excel（报价总表/分项明细/工程量清单/材质清单）
- **入参** (Form): `quote_id: int(...)`
- **出参**:
  ```json
  {
    "success": true,
    "code": 200,
    "data": {
      "quote_id": 1,
      "export_path": "/home/user/exports/报价单_xxx.xlsx",
      "filename": "报价单_xxx.xlsx",
      "sheets": ["报价总表", "分项明细", "工程量清单", "材质清单"]
    }
  }
  ```
- **状态锁**: 需要，占用 `export_running`（仅 `idle` 可调用）
- **调用方**: HistoryPanel.vue, QuoteDisplay.vue → `API.exportExcel(quoteId)`
- **错误码**: 422(报价不存在), 409(系统忙), 500(导出失败)

---

### GET /api/download_excel/{quote_id}
- **描述**: 直接返回 Excel 文件二进制流供前端下载
- **入参**: `quote_id` (path param)
- **出参**: `FileResponse` — 二进制 xlsx 文件流，Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- **状态锁**: 文件已存在时不需要；重新生成时需 `export_running` 锁
- **调用方**: HistoryPanel.vue, QuoteDisplay.vue → `API.downloadExcelBlob(quoteId)` (responseType: 'blob')
- **错误码**: 422(报价不存在), 409(系统忙), 500(生成失败/文件不存在)

---

### POST /api/export/process_quote
- **描述**: 新版精细化工序报价单导出
- **入参** (Form): `quote_id: int(...)`
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "export_path": "/path/to/file.xlsx",
      "filename": "file.xlsx",
      "url": "/api/exports/file.xlsx"
    }
  }
  ```
- **状态锁**: 需要，占用 `export_running`
- **调用方**: 导出按钮 → `API.post('/export/process_quote', fd)`
- **错误码**: 422(报价不存在), 409(系统忙), 500(导出失败)

---

## 9. 历史记录

### GET /api/history
- **描述**: 分页查询所有历史任务列表
- **入参** (Query):
  | 字段 | 类型 | 必填 | 默认值 | 说明 |
  |------|------|------|--------|------|
  | page | int | 否 | 1 | 页码，≥1 |
  | page_size | int | 否 | 20 | 每页条数，1-100 |
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "quotes": { "items": [...], "total": 50, "page": 1, "page_size": 20 },
      "logs": { "items": [...], "total": 200, "page": 1, "page_size": 20 }
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: HistoryPanel.vue, MergePanel.vue, StandardReport.vue → `API.getHistory(page, pageSize)`
- **错误码**: 无

### GET /api/history/{task_id}
- **描述**: 查询单条报价详情
- **入参**: `task_id` (path param, int)
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "quote": { ... },
      "cad_data": [{ "id": 1, "space_name": "客厅", "area": 35.5, ... }],
      "image_data": [{ "id": 1, "recognized_space": "客厅", "material_info": {...}, ... }]
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: HistoryPanel.vue → `API.getHistoryDetail(quoteId)`
- **错误码**: 404(报价记录不存在)

### DELETE /api/history/{task_id}
- **描述**: 删除历史记录（逻辑删除）
- **入参**: `task_id` (path param, int)
- **出参**: `{success, data: {deleted_id: task_id}}`
- **状态锁**: 检查，仅 `idle` 可执行
- **调用方**: HistoryPanel.vue → `API.deleteHistory(quoteId)`
- **错误码**: 409(系统忙)

---

## 10. 操作日志

### GET /api/logs
- **描述**: 分页查询操作日志
- **入参** (Query):
  | 字段 | 类型 | 必填 | 默认值 |
  |------|------|------|--------|
  | page | int | 否 | 1 |
  | page_size | int | 否 | 50 (≤200) |
- **出参**: `{success, data: {logs: {items, total, page, page_size}}}`
- **状态锁**: 不需要（只读）
- **调用方**: LogViewer.vue → `API.getLogs(page, pageSize)`
- **错误码**: 无

---

## 11. 定价配置

### GET /api/settings/pricing
- **描述**: 查询当前所有定价配置
- **入参**: 无
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "base_unit_price": 9374,
      "manage_fee_rate": 0.05,
      "tax_rate": 0.03,
      "loss_rate": 0.03,
      "deduct_door": 1.8,
      "deduct_window": 1.5,
      "deduct_sliding_door": 3.0,
      "deduct_bg_wall": 5.0,
      "wall_area_factor": 2.5,
      "ceiling_factor": 1.0,
      "active_vl_model": "llava:7b",
      "available_vl_models": [...]
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: PricingPanel.vue → `API.getPricing()`
- **错误码**: 无

### POST /api/settings/pricing
- **描述**: 修改定价配置（操作留痕）
- **入参** (Form):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | key | str | 是 | 有效key: base_unit_price, manage_fee_rate, tax_rate, loss_rate, deduct_door, deduct_window, deduct_sliding_door, deduct_bg_wall, wall_area_factor, ceiling_factor |
  | value | str | 是 | 值（字符串） |
- **出参**: `{success, data: {所有配置项}}`
- **状态锁**: 检查，仅 `idle` 可执行
- **调用方**: PricingPanel.vue → `API.updatePricing(key, value)`
- **错误码**: 409(系统忙), 400(无效配置项)

---

## 12. 视觉模型管理

### GET /api/settings/vl_model
- **描述**: 查询当前视觉模型配置 + 可用模型列表
- **入参**: 无
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "active_model": "llava:7b",
      "available_models": [
        { "key": "llava:7b", "label": "LLaVA 7B（默认，稳定）", "installed": true, "active": true },
        { "key": "qwen2.5:7b", "label": "Qwen2.5 7B（精度升级，中文优化）", "installed": false, "active": false }
      ]
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: App.vue, VisionTestPanel.vue → `API.get('/settings/vl_model')`
- **错误码**: 无

### POST /api/settings/vl_model
- **描述**: 切换视觉模型
- **入参** (Form): `model: str(...)`
- **出参**: `{success, data: {previous_model, active_model}}`
- **状态锁**: 检查，仅 `idle` 可执行
- **调用方**: App.vue → `API.post('/settings/vl_model', fd)`
- **错误码**: 409(系统忙), 400(模型不可用)

### GET /api/settings/vl_model/test
- **描述**: 测试当前视觉模型连通性（无图片，只检测API响应）
- **入参**: 无
- **出参**: `{success, data: {status: "ok"|"error", model: "...", detail: "..."}}`
- **状态锁**: 不需要
- **调用方**: 视觉模型管理面板
- **错误码**: 无

---

## 13. 施工工序管理

### GET /api/processes
- **描述**: 查询所有工序（按排序顺序）
- **入参**: 无
- **出参**: `{success, data: {processes: [{id, name, sort_order, work_type, standard_days, description, applicable_spaces, color, unit_price, unit}, ...]}}`
- **状态锁**: 不需要（只读）
- **调用方**: ProcessPanel.vue, PricingPanel.vue → `API.get('/processes')`
- **错误码**: 无

### GET /api/processes/{pid}
- **描述**: 查询单个工序
- **入参**: `pid` (path param, int)
- **出参**: `{success, data: {id, name, ...}}`
- **状态锁**: 不需要（只读）
- **调用方**: ProcessPanel.vue (编辑弹窗)
- **错误码**: 404(工序不存在)

### POST /api/processes
- **描述**: 新增工序
- **入参** (Form): `name, sort_order(0), work_type(""), standard_days(1.0), description(""), applicable_spaces(""), color("#6366f1")`
- **出参**: `{success, data: {id}}`
- **状态锁**: 检查，仅 `idle` 可执行
- **调用方**: ProcessPanel.vue → `API.post('/processes', fd)`
- **错误码**: 409(系统忙)

### PUT /api/processes/{pid}
- **描述**: 修改工序（所有字段可选）
- **入参** (Form): 同 POST，全部可选
- **出参**: `{success}`
- **状态锁**: 检查，仅 `idle` 可执行
- **调用方**: ProcessPanel.vue → `API.put('/processes/{id}', fd)`
- **错误码**: 409(系统忙)

### DELETE /api/processes/{pid}
- **描述**: 删除工序（软删除）
- **入参**: `pid` (path param)
- **出参**: `{success}`
- **状态锁**: 检查，仅 `idle` 可执行
- **调用方**: ProcessPanel.vue → `API.delete('/processes/{id}')`
- **错误码**: 409(系统忙)

### GET /api/processes/quotes/summary
- **描述**: 按工序汇总报价分项
- **入参** (Query): `quote_id: int (可选，不传则取最新报价)`
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "process_summary": [
        {
          "process_id": 1,
          "process_name": "油漆工程",
          "sort_order": 1,
          "work_type": "墙面",
          "standard_days": 3.0,
          "color": "#6366f1",
          "spaces": ["客厅", "卧室"],
          "space_count": 2,
          "total_quantity": 88.75,
          "total_amount": 3550.00,
          "item_count": 2
        }
      ],
      "total_quote": 1280830.77
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: ProcessPanel.vue 汇总视图
- **错误码**: 404(报价不存在/无报价记录)

### POST /api/processes/batch_update_price
- **描述**: 批量更新工序单价
- **入参** (Form): `updates: str(...)` — JSON数组，每项 `{id, unit_price, unit}`
- **出参**: `{success, data: {updated: n}}`
- **状态锁**: 不需要
- **调用方**: ProcessPanel.vue 批量编辑
- **错误码**: 无

---

## 14. 分层工程量

### GET /api/drawings
- **描述**: 列出所有图纸记录
- **入参**: 无
- **出参**: `{success, data: [{id, filename, file_size, upload_time, parse_status, cad_result_json}]}`
- **状态锁**: 不需要（只读）
- **调用方**: SurfaceBreakdown.vue, ComparisonPanel.vue, MergePanel.vue → `API.get('/drawings')`
- **错误码**: 500(查询失败)

### GET /api/image-results
- **描述**: 获取所有效果图识别结果
- **入参**: 无
- **出参**: `{success, data: [{id, image_result_id, recognized_space, original_filename, filename, confidence}]}`
- **状态锁**: 不需要（只读）
- **调用方**: MergePanel.vue → `API.getImageResults()`
- **错误码**: 500(查询失败)

### POST /api/spaces/{drawing_id}/compute_breakdown
- **描述**: 为指定图纸的所有空间计算分层工程量（墙面/地面/顶面）
- **入参**: `drawing_id` (path param)
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "drawing_id": 1,
      "space_count": 5,
      "breakdown_count": 5,
      "sample": { "12": {"surfaces": {"wall": {...}, "floor": {...}, "ceiling": {...}}} }
    }
  }
  ```
- **状态锁**: 不需要
- **调用方**: SurfaceBreakdown.vue → `API.computeBreakdown(drawingId)`
- **错误码**: 404(图纸无CAD结果), 500(计算失败)

### GET /api/spaces/{drawing_id}/breakdown
- **描述**: 获取图纸所有空间的分层工程量 + 关联材质信息
- **入参**: `drawing_id` (path param)
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "drawing_id": 1,
      "space_count": 5,
      "summary": {
        "total_floor_area": 120.33,
        "total_wall_net_area": 300.83,
        "total_ceiling_area": 120.33,
        "matched_spaces": 3,
        "unmatched_spaces": 2
      },
      "spaces": [
        {
          "id": 12,
          "space_name": "客厅",
          "area": 35.5,
          "surface_breakdown": { "surfaces": { "wall": {...}, "floor": {...}, "ceiling": {...} } },
          "material_source": 1,
          "material_confidence": 0.85
        }
      ]
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: SurfaceBreakdown.vue, MergePanel.vue → `API.getBreakdown(drawingId)`
- **错误码**: 404(图纸无CAD结果), 500(查询失败)

### POST /api/spaces/breakdown/bind_material
- **描述**: 手动绑定某空间某表面的材质
- **入参** (Form):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | cad_id | int | 是 | CAD分析结果ID |
  | surface | str | 是 | floor / wall / ceiling |
  | material_name | str | 否 | 材质名称 |
  | material_code | str | 否 | 材质编号 |
- **出参**: `{success, data: {cad_id, surface, material_name, detail_preview}}`
- **状态锁**: 不需要
- **调用方**: SurfaceBreakdown.vue → `API.bindSurfaceMaterial(cadId, surface, materialName, materialCode)`
- **错误码**: 404(CAD结果不存在), 500(绑定失败)

---

## 15. 空间编辑

### PUT /api/spaces/{cad_id}/rename
- **描述**: 编辑 CAD 空间名称
- **入参**: `cad_id` (path param), JSON body: `{"space_name": "新名称"}`
- **出参**: `{success, data: {cad_id, old_name, new_name}}`
- **状态锁**: 不需要
- **调用方**: SurfaceBreakdown.vue → `API.put('/spaces/{cadId}/rename', {space_name: newName})`
- **错误码**: 404(CAD结果不存在), 422(新名称为空), 500(重命名失败)

---

## 16. 自动匹配建议与确认

### POST /api/spaces/auto_suggest_match
- **描述**: 自动建议匹配——根据效果图识别空间，推荐匹配的 CAD 空间
- **入参** (Form):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | drawing_id | int | 是 | 图纸ID |
  | image_result_ids | str | 否 | "[]"—JSON数组，效果图结果ID列表 |
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "matches": [
        {
          "image_id": 1,
          "recognized_space": "客厅",
          "cad_ids": [12, 15],
          "matched_cad_spaces": [{"cad_id": 12, "cad_name": "客厅", "area": 35.5}],
          "material_info": {"wall": "乳胶漆", "floor": "地砖", "ceiling": "石膏板"},
          "confidence": 0.85,
          "original_filename": "客厅.jpg"
        }
      ]
    }
  }
  ```
- **状态锁**: 不需要
- **调用方**: MergePanel.vue → `API.autoSuggestMatch(drawingId, imageResultIds)`
- **错误码**: 404(图纸无CAD结果)

### POST /api/spaces/auto_confirm_match
- **描述**: 确认匹配——将效果图材质绑定到 CAD 空间
- **入参** (Form):
  | 字段 | 类型 | 必填 | 说明 |
  |------|------|------|------|
  | cad_result_id | int | 是 | CAD空间ID (cad_analysis_results.id) |
  | image_result_id | int | 是 | 效果图结果ID |
  | surface_materials | str | 否 | JSON，覆盖材质信息 |
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "cad_result_id": 12,
      "image_result_id": 1,
      "bound": {
        "wall": {"name": "乳胶漆", "source": "ai_matched", "image_result_id": 1},
        "floor": {"name": "地砖", ...},
        "ceiling": {"name": "石膏板", ...}
      },
      "space_name": "客厅",
      "ai_space": "客厅"
    }
  }
  ```
- **状态锁**: 不需要
- **调用方**: MergePanel.vue → `API.autoConfirmMatch(cadId, imageId)`
- **错误码**: 404(图片结果或CAD空间不存在), 500(确认失败)

---

## 17. 图纸与识别结果查询

### GET /api/drawings
- （同14节，已覆盖）

### GET /api/image-results
- （同14节，已覆盖）

---

## 18. 双源数据核对

### GET /api/spaces/{drawing_id}/comparison
- **描述**: 返回 CAD 与 AI 双源数据比对表
- **入参**: `drawing_id` (path param)
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "drawing_id": 1,
      "total_spaces": 5,
      "normal_count": 3,
      "anomaly_count": 2,
      "rows": [
        {
          "space_id": 12,
          "space_name": "客厅",
          "area_sqm": 35.5,
          "wall_material": "乳胶漆",
          "floor_material": "地砖",
          "ceiling_material": "石膏板",
          "ai_confidence": 0.85,
          "ai_matched_space": "客厅",
          "status": "正常|异常",
          "anomalies": [],
          "surface_materials": {}
        }
      ]
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: ComparisonPanel.vue → `API.get('/spaces/{id}/comparison')`
- **错误码**: 404(图纸无CAD结果), 500(比对失败)

---

## 19. 标准报价表

### GET /api/quote/{quote_id}/standard_report
- **描述**: 返回标准报价表的三个视图数据：综合报价总表、空间分项明细表、工序费用明细表
- **入参**: `quote_id` (path param)
- **出参**:
  ```json
  {
    "success": true,
    "data": {
      "project_name": "装修工程",
      "total_area": 120.33,
      "total_price": 1280830.77,
      "base_price": 1128289.42,
      "material_diff": 12500.00,
      "loss_price": 33848.68,
      "manage_fee": 56414.47,
      "tax_fee": 41176.55,
      "create_time": "2025-07-01T12:30:45",
      "quote_id": 1,
      "process_summary": [
        {"process_name": "油漆工程", "subtotal": 3550.00, "item_count": 2, "space_count": 2}
      ],
      "space_details": [
        {"space_name": "客厅", "space_subtotal": 5000.00, "items": [...]}
      ],
      "process_details": [
        {"process_name": "油漆工程", "sort_order": 1, "spaces": ["客厅"], "space_count": 1, "material_cost": 1597.5, "labor_cost": 1952.5, "subtotal": 3550.0}
      ]
    }
  }
  ```
- **状态锁**: 不需要（只读）
- **调用方**: StandardReport.vue → `API.get('/quote/{quote_id}/standard_report')`
- **错误码**: 404(报价不存在), 500(获取失败)

---

## 20. 兼容旧版接口

### GET /api/config
- **描述**: 兼容旧版配置查询
- **入参**: 无
- **出参**:
  ```json
  {
    "vl_engine": "Ollama/LLaVA-7B 本地模型",
    "llava_available": true,
    "supported_cad_formats": [".dxf", ".dwg"],
    "supported_image_formats": [".jpg", ".jpeg", ".png", ".webp"]
  }
  ```
- **状态锁**: 不需要
- **调用方**: 旧版前端兼容
- **注意**: 响应**未包装**在 `{success, code, data}` 中，直接返回裸 JSON

### GET /api/health
- **描述**: 兼容旧版健康检查
- **入参**: 无
- **出参**: `{"status": "ok", "time": "2025-07-01T12:30:45"}`
- **状态锁**: 不需要
- **调用方**: 旧版前端/负载均衡器
- **注意**: 响应**未包装**，直接返回裸 JSON

---

## 21. 通用错误码总表

| 状态码 | 含义 | 常见场景 |
|--------|------|---------|
| 200 | 成功 | 所有正常返回 |
| 400 | 请求无效 | 未上传文件、无效配置项 |
| 404 | 资源不存在 | 报价/工序/CAD结果不存在 |
| 409 | 冲突/系统忙 | 非idle状态下调用需锁接口 |
| 413 | 文件过大 | CAD>120MB, 图片>10MB, PDF>50MB |
| 415 | 格式不支持 | 上传了不允许的文件类型 |
| 422 | 参数错误/数据不完整 | CAD数据为空、缺少必填参数 |
| 500 | 服务器内部错误 | 异常未捕获 |
| 504 | 超时/第三方失败 | CAD解析超时、AI识别失败 |

**统一错误响应格式**:
```json
{
  "success": false,
  "code": 409,
  "message": "系统当前有任务正在执行（cad_running），请等待完成后再操作",
  "data": null,
  "task_status": "cad_running",
  "trace_id": ""
}
```

---

## 22. 统一成功响应格式

```json
{
  "success": true,
  "code": 200,
  "message": "操作成功",
  "data": { ... },
  "task_status": "idle|cad_running|ai_running|merge_running|export_running",
  "trace_id": ""
}
```

**注意**: 兼容旧版接口(`GET /api/config`, `GET /api/health`) 不遵循此格式，直接返回裸 JSON。

---

## 附录：前端 API 调用映射

| API 方法 | 后端路径 | 前端函数 | 调用组件 |
|----------|---------|---------|---------|
| `getStatus` | `GET /system/status` | `API.getStatus()` | App.vue |
| `getHealth` | `GET /system/health` | `API.getHealth()` | 系统监控 |
| `analyzeCad` | `POST /analyze_full` | `API.analyzeCad(file, projectName)` | CadUploader.vue, CadBatchUploader.vue |
| `analyzeImage` | `POST /analyze` | `API.analyzeImage(file)` | ImageUploader.vue, ImageQueue.vue |
| `dataMerge` | `POST /data_merge` | `API.dataMerge(cadResultId, imgIds, bindings)` | MergePanel.vue |
| `exportExcel` | `POST /export_excel` | `API.exportExcel(quoteId)` | HistoryPanel.vue, QuoteDisplay.vue |
| `downloadExcelBlob` | `GET /download_excel/{id}` | `API.downloadExcelBlob(quoteId)` | HistoryPanel.vue, QuoteDisplay.vue |
| `getHistory` | `GET /history` | `API.getHistory(page, pageSize)` | HistoryPanel.vue, MergePanel.vue, StandardReport.vue |
| `getHistoryDetail` | `GET /history/{id}` | `API.getHistoryDetail(quoteId)` | HistoryPanel.vue |
| `deleteHistory` | `DELETE /history/{id}` | `API.deleteHistory(quoteId)` | HistoryPanel.vue |
| `getLogs` | `GET /logs` | `API.getLogs(page, pageSize)` | LogViewer.vue |
| `getPricing` | `GET /settings/pricing` | `API.getPricing()` | PricingPanel.vue |
| `updatePricing` | `POST /settings/pricing` | `API.updatePricing(key, value)` | PricingPanel.vue |
| `computeBreakdown` | `POST /spaces/{id}/compute_breakdown` | `API.computeBreakdown(drawingId)` | SurfaceBreakdown.vue |
| `getBreakdown` | `GET /spaces/{id}/breakdown` | `API.getBreakdown(drawingId)` | SurfaceBreakdown.vue, MergePanel.vue |
| `bindSurfaceMaterial` | `POST /spaces/breakdown/bind_material` | `API.bindSurfaceMaterial(cadId, surface, name, code)` | SurfaceBreakdown.vue |
| `autoSuggestMatch` | `POST /spaces/auto_suggest_match` | `API.autoSuggestMatch(drawingId, imgIds)` | MergePanel.vue |
| `autoConfirmMatch` | `POST /spaces/auto_confirm_match` | `API.autoConfirmMatch(cadId, imgId)` | MergePanel.vue |
| `getImageResults` | `GET /image-results` | `API.getImageResults()` | MergePanel.vue |
| `get` (通用) | `GET /{path}` | `API.get(path)` | 多处使用 |
| `post` (通用) | `POST /{path}` | `API.post(path, body)` | 多处使用 |
| `put` (通用) | `PUT /{path}` | `API.put(path, body)` | 多处使用 |
| `delete` (通用) | `DELETE /{path}` | `API.delete(path)` | 多处使用 |

### 通用 HTTP 方法调用的具体路径

| 路径 | 方法 | 调用组件 |
|------|------|---------|
| `/drawings` | GET | SurfaceBreakdown.vue, ComparisonPanel.vue, MergePanel.vue |
| `/spaces/{id}/comparison` | GET | ComparisonPanel.vue |
| `/spaces/{id}/rename` | PUT | SurfaceBreakdown.vue |
| `/quote/{id}/items` | PUT | QuoteDisplay.vue |
| `/quote/{id}/standard_report` | GET | StandardReport.vue |
| `/settings/vl_model` | GET | App.vue, VisionTestPanel.vue |
| `/settings/vl_model` | POST | App.vue |
| `/vision_test` | POST | VisionTestPanel.vue |
| `/upload/clear` | POST | App.vue |
| `/analyze_pdf` | POST | App.vue |
| `/pricing/templates` | GET | PricingPanel.vue |
| `/pricing/templates/switch` | POST | PricingPanel.vue |
| `/pricing/items` | GET | PricingPanel.vue |
| `/pricing/items` | POST | PricingPanel.vue |
| `/pricing/items/{pid}` | PUT | PricingPanel.vue |
| `/pricing/items/{pid}` | DELETE | PricingPanel.vue |
| `/processes` | GET | ProcessPanel.vue, PricingPanel.vue |
| `/processes` | POST | ProcessPanel.vue |
| `/processes/{pid}` | PUT | ProcessPanel.vue |
| `/processes/{pid}` | DELETE | ProcessPanel.vue |

---

## 附录：任务状态机锁规则

| 任务类型 | 目标锁状态 | 超时(秒) | 释放机制 |
|---------|-----------|---------|---------|
| cad | `cad_running` | 0（不限时） | safe_run finally |
| ai | `ai_running` | 0（不限时） | safe_run finally |
| merge | `merge_running` | 10 | safe_run finally 或手动 release |
| export | `export_running` | 15 | safe_run finally 或手动 release |
| manual_edit | 不占用锁 | — | — |
| config | 不占用锁 | — | — |

锁规则要点:
1. 仅 `idle` 状态可获取锁，否则返回 409
2. `safe_run()` 自动获取锁、释放锁
3. 部分接口（data_merge, export）自行管理锁（try/finally release）
4. 只读接口完全不检查锁
5. 写操作（delete_history, update_pricing, switch_vl_model, crud_processes）仅检查 `state != idle` 时返回 409，不占用锁
