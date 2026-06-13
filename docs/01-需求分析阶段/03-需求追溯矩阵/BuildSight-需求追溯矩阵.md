# BuildSight 家装智能自动报价系统 — 需求追溯矩阵

> **版本：** v0.8.10 → v0.9.0  
> **更新日期：** 2026-06-13  
> **覆盖范围：** 首期（P0 已完成 + P1 待完成）+ 二期规划  
> **文档状态：** ✅ 完整覆盖

---

## 一、矩阵说明

### 1.1 需求标识规则

| 前缀 | 类型 | 说明 |
|------|------|------|
| FR- | 功能需求 | 已实现 / 首期核心 |
| FR-P1- | 功能需求 | 首期待完成（P1 优先级） |
| FR-P2- | 功能需求 | 二期规划 |
| NFR- | 非功能需求 | 性能/质量/约束类 |
| BR- | 业务规则 | 算量/报价/匹配规则 |

### 1.2 状态说明

| 状态 | 含义 |
|------|------|
| ✅ 已实现 | v0.8.10 中已完成实现并验证 |
| 🔶 进行中 | 开发中，即将合入 v0.9.0 |
| 📋 待开发 | P1 待完成项 |
| 📅 二期 | 二期规划，首期不开发 |
| — | 不适用 |

---

## 二、需求追溯矩阵总表

### 2.1 核心功能需求（首期已实现）

| 需求ID | 需求名称 | 需求描述 | 来源文档 | 设计规格映射 | 代码模块/接口映射 | 测试/验证方式 | 状态 |
|--------|---------|---------|---------|-------------|-----------------|--------------|------|
| **FR-001** | **DXF图纸矢量解析** | 支持 DXF/DWG 图纸上传、自动格式转换 (DWG→DXF)、矢量解析、空间轮廓提取 | 功能规格说明书 §首期核心功能 / 整体技术方案 §二 | 系统架构.md §主流程 / 数据库设计.md §cad_analysis_results 表 | `backend/cad_parser.py` → POST `/api/analyze_full` | 标准DXF测试集验证，尺寸精度≥90% | ✅ 已实现 |
| **FR-002** | **106空间识别与面积计算** | 从CAD矢量数据解析出全屋空间边界，计算每个空间的面积(㎡)、周长(m)、长宽尺寸 | 功能规格说明书 §首期核心功能 / 整体技术方案 §二 | 数据库设计.md §cad_analysis_results 字段(area/length/width/perimeter) | `backend/cad_parser.py` → detail_json.surface_breakdown | 测试集验证空间识别率、面积误差 | ✅ 已实现 |
| **FR-003** | **工程量计算** | 基于CAD空间尺寸计算基础工程量（墙面净面积、地面面积、顶面面积），含标准洞口扣减规则 | 整体技术方案 §4.1 / 首期任务书 §4.1 | 数据库设计.md §detail_json.deduct_ratio / 系统架构.md §cad_parser→quantity_estimator | `backend/quantity_estimator.py` → 联动 CAD 解析结果 | 验证扣减系数正确性、计算结果可反向溯源 | ✅ 已实现 |
| **FR-004** | **效果图材质识别（完整Harness）** | 上传效果图→Vision Harness 5阶段流水线（预处理→推理→校验→重试→输出）→6字段结构化JSON | 功能规格说明书 §首期核心功能 / 视觉识别Harness.md §三 | 视觉识别Harness.md §3.7 pipeline.py / 模型调用规范 §二 | `backend/vision_harness/` (8模块) → `image_recognizer.py` 兼容层 | Benchmark 测试集验证字段完整率≥90%、准确率≥80% | ✅ 已实现 |
| **FR-005** | **墙/地/顶三面材质识别** | 识别效果图中墙面(wall_material)、地面(floor_material)、顶面(ceiling_material)三种材质，透视裁剪分区识别 | 视觉识别Harness.md §3.3 / 模型调用规范 §二 | 视觉识别Harness.md §3.3 CROP_RATIOS(ceiling 0-30%, wall 25-75%, floor 60-100%) | `backend/vision_harness/stages/preprocessor.py` → `stages/inferrer.py` | 单图测试验证三面材质准确性 | ✅ 已实现 |
| **FR-006** | **装饰风格判断** | 识别效果图的装饰风格(decor_style)，作为报价参考维度 | 模型调用规范 §二 / 视觉识别Harness.md §四 | 模型调用规范 §二 structured JSON 含 decor_style 字段 | `backend/vision_harness/stages/inferrer.py` → Prompt 构建 | 测试集验证风格识别一致性 | ✅ 已实现 |
| **FR-007** | **数据自动融合** | CAD精准工程量 + AI材质识别结果按"空间名+部位"自动匹配融合，同义词引擎模糊匹配 | 系统架构.md §双线数据流 / 整体技术方案 §2(三级匹配) | 系统架构.md §数据流 / 整体技术方案 §4.3 匹配逻辑 | `backend/fusion_validator.py` → POST `/api/data_merge` | 融合结果验证：工程量+材质正确绑定，报价项完整可溯源 | ✅ 已实现 |
| **FR-008** | **自动报价计算** | 四层报价公式：基础工程量报价 + 材质联动差价 + 管理费 + 税费，含工艺损耗费 | 首期任务书 §4.2 / 数据库设计.md §quote_records 表 | 首期任务书 §4.2 报价公式 / 数据库设计.md §quote_records 7个价格字段 | `backend/quantity_estimator.py` → 联动 fusion_validator | 验证最终价格 = 各分项之和，分项可溯源 | ✅ 已实现 |
| **FR-009** | **Excel报价导出（4Sheet）** | 生成 4Sheet 结构报价 Excel：报价汇总、分层明细、工序对照、材质清单，本地缓存返回下载链接 | 功能规格说明书 §首期核心功能 / API接口规范 §核心业务 | 首期任务书 §7.3 接口清单 / 数据库设计.md §quote_records | `backend/excel_export.py` → POST `/api/export_excel` | 验证 Excel 4Sheet 内容完整、数据与系统一致 | ✅ 已实现 |
| **FR-010** | **施工工序模板（10项）** | 内置10项标准施工工序：拆除/水电/防水/瓦工/木工/油漆/安装/保洁/竣工/软装，可增删改查 | 功能规格说明书 §首期核心功能 / 数据库设计.md §construction_processes | 数据库设计.md §construction_processes 表(10项内置) / API接口规范 §施工工序 | `construction_processes` 表 → CRUD: GET/POST/PUT/DELETE `/api/processes` | 验证10项工序全量存在，增删改查正常 | ✅ 已实现 |
| **FR-011** | **工序×空间映射** | 工序与空间对照汇总，生成工序×报价汇总表 | 功能规格说明书 §首期核心功能 / API接口规范 §施工工序 | API接口规范 §施工工序 GET `/api/processes/quotes/summary` | `backend/` 工序汇总逻辑 → GET `/api/processes/quotes/summary` | 验证汇总表数据完整、工序覆盖所有空间 | ✅ 已实现 |
| **FR-012** | **视觉模型切换** | 支持在 qwen2.5:7b（默认，92%准确率）与 llava:7b 之间切换，前端下拉选择 | 功能规格说明书 §首期核心功能 / 模型调用规范 §三 | 模型调用规范 §三层模型策略 / 数据库设计.md §system_settings(active_vl_model) | `backend/vision_harness/config.py` DEFAULT_MODEL → POST/GET `/api/settings/vl_model` | 切换后调用验证模型变更生效，切换记录写入 operation_logs | ✅ 已实现 |
| **FR-013** | **分层工程量明细** | 106 空间 × 10 分项，墙/地/顶三面独立计算（面积、净面积、扣减比例、材质绑定） | 系统架构.md §数据流 / 功能规格说明书 §首期核心功能 | 数据库设计.md §cad_analysis_results.detail_json(surface_breakdown + surface_materials) | `backend/surface_breakdown.py` → POST/GET `/api/spaces/{drawing_id}/breakdown` | 验证每空间三面数据完整、材质绑定正确 | ✅ 已实现 |
| **FR-014** | **PDF施工图识别** | PDF 施工图渲染为图片后复用 LLaVA 视觉识别流水线 | 功能规格说明书（任务上下文） | 视觉识别Harness架构 §四（同效图流程复用） | `backend/vision_harness/` (可复用流水线) | PDF→图片渲染→视觉识别链路验证 | ✅ 已实现 |
| **FR-015** | **三层门禁管控** | ① 文件门禁（格式+大小校验）② 混装门禁（禁止CAD+图片同请求）③ 状态机互斥（5种状态 asyncio.Lock）+ 超时熔断（CAD 30s/AI 120s/融合 10s/导出 15s） | 门禁规范 §1-5 / 系统架构.md §三层门禁 | 门禁规范 §1 任务状态机(idle/cad_running/ai_running/merge_running/export_running) / 门禁规范 §4 超时熔断阈值 | `backend/main.py` 任务状态机 / `auth_proxy.py` 前端互斥 | 并发请求测试、超时熔断测试、混合请求拦截测试 | ✅ 已实现 |
| **FR-016** | **识别测试诊断** | 独立诊断端点 + 前端测试 tab，验证模型连通性和识别效果 | （任务上下文） | API接口规范 §配置管理 GET/POST `/api/settings/vl_model/test` | `backend/vision_harness/stages/inferrer.py` health_check() → `/api/settings/vl_model/test` | 诊断端点响应正常，模型连通性检测通过 | ✅ 已实现 |

### 2.2 业务规则需求

| 需求ID | 需求名称 | 需求描述 | 来源文档 | 设计规格映射 | 代码模块/接口映射 | 测试/验证方式 | 状态 |
|--------|---------|---------|---------|-------------|-----------------|--------------|------|
| **BR-001** | **洞口扣减规则** | 墙面施工面积 = 原始墙面面积 - 洞口面积×扣减系数（木门85%/铝合金窗70%/推拉门50%/壁龛0%+增量） | 首期任务书 §4.1 | 首期任务书 §4.1 扣减公式 + 系数表 | `backend/quantity_estimator.py` + system_settings 可配置 | 验证各洞口类型扣减计算正确，配置修改生效 | ✅ 已实现 |
| **BR-002** | **四层报价公式** | 最终报价 = 基础工程量报价 + 材质联动工序差价 + 特殊工艺增项 + 工艺损耗费 + 管理费 + 税费 | 首期任务书 §4.2 | 首期任务书 §4.2 公式 / 数据库设计.md §quote_records 字段 | `backend/quantity_estimator.py` | 验证所有分项可溯源、无漏项、计算一致 | ✅ 已实现 |
| **BR-003** | **空间-材质匹配规则** | 三级匹配：①精准名称匹配 ②同义词模糊匹配 ③人工手动绑定兜底；匹配失败保留基础报价+标红预警 | 整体技术方案 §4.3 / 首期任务书 §4.3 | 整体技术方案 §4.3 三级匹配机制 / 视觉识别Harness.md §material_library.py SYNONYM_GROUPS | `backend/fusion_validator.py` + `material_library.py` SPACE_MATERIAL_RULES | 测试各类匹配场景：完全匹配/同义词/无匹配 | ✅ 已实现 |
| **BR-004** | **CAD数据不可篡改** | CAD矢量数据作为报价核心工程量依据，不可篡改；AI材质数据仅辅助调价，不覆盖CAD工程量 | 首期任务书 §三-3(能力拆分约束) | 首期任务书 §三-3 能力拆分约束 | `backend/fusion_validator.py` 融合逻辑 | 验证融合后CAD原始工程量不变 | ✅ 已实现 |
| **BR-005** | **任务强制串行** | CAD解析、AI识别、数据融合、报价导出四类任务全程互斥，仅允许单任务运行 | 首期任务书 §三-2(任务串行约束) | 门禁规范 §1 状态机 / 系统架构.md §任务状态机 | `backend/main.py` asyncio.Lock + 任务状态机 5种状态 | 并发请求测试，验证非法状态拦截 | ✅ 已实现 |
| **BR-006** | **容错兜底** | AI识别异常/匹配失败/材质不匹配时，不破坏CAD基础报价，仅标记待人工复核 | 首期任务书 §三-4(容错兜底约束) | 首期任务书 §三-4 容错策略 | 全局异常处理 + `fusion_validator.py` 标记逻辑 | 模拟AI失败场景验证报价不中断 | ✅ 已实现 |
| **BR-007** | **规则优先** | 所有报价计算优先遵循固化算量规则/工序计价规则，人工修改仅临时微调，全程留痕 | 首期任务书 §三-5(规则优先约束) | 首期任务书 §三-5 | 全程 trace_json 记录 + operation_logs | 验证规则计算优先、人工修改留痕 | ✅ 已实现 |

### 2.3 非功能需求

| 需求ID | 需求名称 | 需求描述 | 来源文档 | 设计规格映射 | 代码模块/接口映射 | 测试/验证方式 | 状态 |
|--------|---------|---------|---------|-------------|-----------------|--------------|------|
| **NFR-001** | **全流程响应≤90s** | 完整业务流程（图纸解析+AI识别+数据融合+报价生成）总耗时≤90秒 | 首期任务书 §1.3 | 门禁规范 §4 超时阈值：CAD 30s / AI 120s / 融合 10s / 导出 15s | 各模块 + ProcessPoolExecutor/ThreadPoolExecutor | 全链路计时验证 ≤90s | ✅ 已实现 |
| **NFR-002** | **识别字段完整率≥90%** | 效果图材质识别字段完整率≥90%，支持人工修正 | 首期任务书 §1.3 / 门禁规范 §六 | 视觉识别Harness.md §六 Gate FILL_RATE ≥90% | `benchmark_runner.py` 自动化评测 | Benchmark 测试集验证：当前 100% (qwen2.5:7b) | ✅ 已实现 |
| **NFR-003** | **CAD尺寸精度≥90%** | CAD尺寸提取精度≥90%（限定标准DXF测试图纸） | 首期任务书 §1.3 | 首期任务书 §1.3 验收指标 | `backend/cad_parser.py` | 标准DXF测试集验证 | ✅ 已实现 |
| **NFR-004** | **报价可溯源** | 所有报价分项可反向溯源、计算逻辑无断链、无漏项错项；计算结果与系统配置规则完全一致 | 首期任务书 §1.3 | 数据库设计.md §quote_records.trace_json | `backend/quantity_estimator.py` + trace_json | 逐项验证追溯路径完整 | ✅ 已实现 |
| **NFR-005** | **识别准确率≥80%** | AI识别字段准确率≥80%（门禁阈值） | 视觉识别Harness.md §六 | 视觉识别Harness.md §六 Gate ACCURACY ≥80% | `benchmark_runner.py` → material_library.py SYNONYM_GROUPS | Benchmark 测试集验证：当前 92% (qwen2.5:7b) | ✅ 已实现 |
| **NFR-006** | **单图耗时≤10s** | 单张效果图识别耗时≤10s | 视觉识别Harness.md §六 | 视觉识别Harness.md §六 门禁规则：单图耗时≤10s | `backend/vision_harness/` 流水线 | Benchmark 测试集验证：当前 0.5s | ✅ 已实现 |
| **NFR-007** | **统一接口响应格式** | 所有后端接口强制统一响应结构 {success, code, message, data, task_status, trace_id} | API接口规范 §一 | API接口规范 §统一响应格式 / 首期任务书 §7.1-7.2 | `backend/main.py` 全局响应处理 | 全部接口响应格式一致性检查 | ✅ 已实现 |
| **NFR-008** | **统一的HTTP状态码** | 全系统统一状态码：200/400/409/413/415/422/500/504 | 首期任务书 §7.2 | 首期任务书 §7.2 状态码规范表 | `backend/main.py` 异常处理 | 模拟各异常场景验证状态码正确 | ✅ 已实现 |

### 2.4 首期待完成（P1）

| 需求ID | 需求名称 | 需求描述 | 来源文档 | 设计规格映射 | 关联代码模块 | 验证方式 | 状态 |
|--------|---------|---------|---------|-------------|-------------|----------|------|
| **FR-P1-001** | **空间名称同义词库** | 完善空间名称同义词映射（如客厅/起居室/大厅），提升自动匹配准确率 | 功能规格说明书 §待完成(P1) / 整体技术方案 §4.3 | 视觉识别Harness.md §material_library.py SYNONYM_GROUPS（当前26组） | `material_library.py` SYNONYM_GROUPS 扩展 + `fusion_validator.py` 匹配逻辑 | 测试更多同义词场景覆盖 | 📋 待开发 |
| **FR-P1-002** | **图片预处理优化** | 图片预处理增强：统一尺寸、压缩画质、剔除水印/边框/文字叠加 | 功能规格说明书 §待完成(P1) / 模型调用规范 §五 | 视觉识别Harness.md §config.py MAX_IMAGE_DIM=1024, JPEG_QUALITY=85 | `preprocessor.py` 预处理流程优化 | 对比优化前后识别准确率差异 | 📋 待开发 |
| **FR-P1-003** | **人工复核样本积累** | AI识别结果人工修正后作为训练/验证样本积累，持续提升识别准确率 | 功能规格说明书 §待完成(P1) / 整体技术方案 §二(短期优化) | 数据库设计.md §image_analysis_results(manual_correction/confirm_status) | `backend/` 样本收集 + 导出逻辑 | 验证样本收集链路完整，修正样本可导出 | 📋 待开发 |

### 2.5 二期规划需求

| 需求ID | 需求名称 | 需求描述 | 来源文档 | 设计规格映射 | 状态 |
|--------|---------|---------|---------|-------------|------|
| **FR-P2-001** | **自定义报价模板** | 支持在线编辑报价模板 + Excel外部模板导入，零学习成本配置 | 功能规格说明书 §二期 / 整体技术方案 §三 | 整体技术方案 §三(方案A在线编辑/方案B Excel导入) | 📅 二期 |
| **FR-P2-002** | **自定义单价体系** | 按空间+部位+材质+工序设定独立单价，可视化配置 | 功能规格说明书 §二期 / 整体技术方案 §三 | 整体技术方案 §三(单价体系模块) | 📅 二期 |
| **FR-P2-003** | **PDF报价导出** | 除Excel外支持PDF格式报价单导出，打印适配 | 功能规格说明书 §二期 / 整体技术方案 §四 | 整体技术方案 §四(阶段4体验优化) | 📅 二期 |
| **FR-P2-004** | **多图纸批量处理** | 支持多张DXF/效果图批量上传、批量解析、批量出单 | 功能规格说明书 §二期 | 首期任务书 §一(明确不做批量AI并行推理) | 📅 二期 |
| **FR-P2-005** | **云端视觉模型兜底** | 本地Ollama故障时自动切换云端视觉模型，保证服务不中断 | 功能规格说明书 §二期 / 模型调用规范 §三 | 模型调用规范 §三层模型策略(🔴兜底/云端) | 📅 二期 |
| **FR-P2-006** | **公网部署** | 系统可部署至公网环境，支持远程访问（含Basic Auth） | 功能规格说明书 §二期 | `backend/auth_proxy.py`（预留） | 📅 二期 |
| **FR-P2-007** | **多用户/权限管理** | 用户登录、角色权限、账号管理 | 首期任务书 §1.5(明确不做) | — | 📅 二期 |
| **FR-P2-008** | **多版本报价对比** | 报价版本树、多方案对比、版本复刻能力 | 首期任务书 §4.5(明确不做) | — | 📅 二期 |
| **FR-P2-009** | **RAG工艺知识库** | 家装工艺知识库检索增强，智能工序适配 | 首期任务书 §1.5(明确不做) | — | 📅 二期 |
| **FR-P2-010** | **分布式锁** | 多进程/多Worker部署时替换 asyncio.Lock 为分布式锁 | 首期任务书 §5.2(预留扩展点) | 首期任务书 §5.2(预留通过配置文件切换锁模式) | 📅 二期 |

---

## 三、需求-设计-实现 追溯对照表

### 3.1 需求 → 设计文档 映射

| 需求ID | 功能规格说明书 | 系统架构设计 | 数据库设计 | API设计 | 视觉识别Harness | 门禁规范 | 模型调用规范 | 整体技术方案 | 首期任务书 |
|--------|:------------:|:----------:|:--------:|:------:|:--------------:|:------:|:----------:|:----------:|:--------:|
| FR-001 | ✅ | ✅ | ✅ | ✅ | — | — | — | ✅ | ✅ |
| FR-002 | ✅ | ✅ | ✅ | — | — | — | — | ✅ | ✅ |
| FR-003 | — | ✅ | ✅ | — | — | — | — | ✅ | ✅ |
| FR-004 | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| FR-005 | — | — | ✅ | — | ✅ | — | ✅ | ✅ | — |
| FR-006 | — | — | ✅ | — | ✅ | — | ✅ | — | — |
| FR-007 | ✅ | ✅ | ✅ | ✅ | — | — | — | ✅ | ✅ |
| FR-008 | — | — | ✅ | ✅ | — | — | — | ✅ | ✅ |
| FR-009 | ✅ | — | ✅ | ✅ | — | — | — | — | ✅ |
| FR-010 | ✅ | — | ✅ | ✅ | — | — | — | — | ✅ |
| FR-011 | ✅ | ✅ | — | ✅ | — | — | — | — | — |
| FR-012 | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — |
| FR-013 | ✅ | ✅ | ✅ | ✅ | — | — | — | — | ✅ |
| FR-014 | — | ✅ | — | — | ✅ | — | — | — | — |
| FR-015 | — | ✅ | — | — | — | ✅ | — | — | ✅ |
| FR-016 | — | — | — | ✅ | ✅ | — | ✅ | — | — |
| BR-001~007 | — | — | ✅ | — | — | ✅ | — | ✅ | ✅ |
| NFR-001 | — | — | — | — | — | ✅ | — | — | ✅ |
| NFR-002 | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| NFR-003 | — | — | — | — | — | — | — | — | ✅ |
| NFR-004 | — | — | ✅ | — | — | — | — | — | ✅ |
| NFR-005 | — | — | — | — | ✅ | ✅ | — | — | — |
| NFR-006 | — | — | — | — | ✅ | ✅ | — | — | — |
| NFR-007 | — | — | — | ✅ | — | — | — | — | ✅ |
| NFR-008 | — | — | — | ✅ | — | — | — | — | ✅ |
| FR-P1-001 | ✅ | — | — | — | ✅ | — | — | ✅ | — |
| FR-P1-002 | ✅ | — | — | — | ✅ | — | ✅ | ✅ | — |
| FR-P1-003 | ✅ | — | ✅ | — | — | — | — | ✅ | — |
| FR-P2-001~006 | ✅ | — | — | — | — | — | — | ✅ | ✅ |

### 3.2 需求 → 代码模块 映射

| 需求ID | 后端模块 | 前端组件 | API接口 | 数据库表 |
|--------|---------|---------|---------|---------|
| FR-001 | `cad_parser.py` | 图纸上传组件 | POST `/api/analyze_full` | drawing_records, cad_analysis_results |
| FR-002 | `cad_parser.py` | 空间列表组件 | POST `/api/analyze_full` | cad_analysis_results |
| FR-003 | `quantity_estimator.py` | — | POST `/api/analyze_full` | cad_analysis_results.base_quantity |
| FR-004 | `vision_harness/` (8模块) + `image_recognizer.py` | 效果图上传组件 | POST `/api/analyze` | image_analysis_results |
| FR-005 | `vision_harness/stages/preprocessor.py`, `inferrer.py` | — | POST `/api/analyze` | image_analysis_results.material_info |
| FR-006 | `vision_harness/stages/inferrer.py` | — | POST `/api/analyze` | image_analysis_results.material_info |
| FR-007 | `fusion_validator.py` | 融合报价页面 | POST `/api/data_merge` | quote_records |
| FR-008 | `quantity_estimator.py` | 报价预览页面 | POST `/api/data_merge` | quote_records |
| FR-009 | `excel_export.py` | 导出按钮 | POST `/api/export_excel` | quote_records.export_path |
| FR-010 | `main.py` (CRUD handlers) | 工序管理页面 | GET/POST/PUT/DELETE `/api/processes` | construction_processes |
| FR-011 | 工序汇总模块 | 工序对照页面 | GET `/api/processes/quotes/summary` | construction_processes + quote_records |
| FR-012 | `vision_harness/config.py` | 模型选择器 | POST/GET `/api/settings/vl_model` | system_settings.active_vl_model |
| FR-013 | `surface_breakdown.py` | 分层明细页面 | POST/GET `/api/spaces/{id}/breakdown` | cad_analysis_results.detail_json |
| FR-014 | `vision_harness/` (复用) | 施工图上传 | — (复用 `/api/analyze`) | — (复用 image_analysis_results) |
| FR-015 | `main.py` (任务状态机 + 门禁逻辑) | 前端按钮互斥 | GET `/api/system/status` + 各API锁校验 | operation_logs |
| FR-016 | `vision_harness/stages/inferrer.py` | 诊断测试Tab | GET `/api/settings/vl_model/test` | — |
| BR-001 | `quantity_estimator.py` + system_settings | — | POST `/api/settings/pricing` | system_settings |
| BR-002 | `quantity_estimator.py` | — | POST `/api/data_merge` | quote_records |
| BR-003 | `fusion_validator.py` + `material_library.py` | 手动绑定面板 | POST `/api/spaces/breakdown/bind_material` | cad_analysis_results.detail_json |
| BR-004~007 | `main.py` + `fusion_validator.py` | 前端约束 | 全局 | operation_logs + trace_json |

---

## 四、验证与测试覆盖矩阵

### 4.1 Benchmark 门禁验证

| 门禁指标 | 需求ID | 阈值 | 当前值 (qwen2.5:7b) | 测试集 | 结果 |
|---------|--------|:----:|:-------------------:|--------|:----:|
| 字段填充率 | NFR-002, FR-P1-001 | ≥ 90% | 100% | 3张标准效果图 | ✅ |
| 字段准确率 | NFR-005, FR-P1-001 | ≥ 80% | 92% | 3张标准效果图 | ✅ |
| 空间偏差 | FR-002, BR-003 | ≤ 1/3 | 0/3 | 3张标准效果图 | ✅ |
| 单图耗时 | NFR-006 | ≤ 10s | 0.5s | 3张标准效果图 | ✅ |
| 测试集完整性 | NFR-002 | 3张全存在 | ✅ | benchmark_images/ | ✅ |

### 4.2 接口测试覆盖

| 接口 | 需求ID | 正常流程 | 异常流程 | 门禁校验 | 数据类型 |
|------|--------|:-------:|:-------:|:-------:|:-------:|
| POST `/api/analyze_full` | FR-001~003, BR-001, NFR-003 | ✅ | ✅ | ✅ | CAD DXF/DWG |
| POST `/api/analyze` | FR-004~006, FR-016 | ✅ | ✅ | ✅ | 效果图 (jpg/png) |
| POST `/api/data_merge` | FR-007~008, BR-002~004, BR-006~007 | ✅ | ✅ | ✅ | JSON |
| POST `/api/export_excel` | FR-009 | ✅ | ✅ | ✅ | — |
| GET/POST/PUT/DELETE `/api/processes/*` | FR-010~011 | ✅ | ✅ | — | JSON |
| POST/GET `/api/settings/vl_model` | FR-012 | ✅ | ✅ | ✅ | JSON |
| POST/GET `/api/spaces/{id}/breakdown` | FR-013 | ✅ | ✅ | — | JSON |
| POST `/api/spaces/breakdown/bind_material` | FR-007, BR-003 | ✅ | ✅ | — | JSON |
| GET `/api/system/status` | FR-015, NFR-001 | ✅ | — | — | — |
| GET `/api/system/health` | FR-015, FR-016 | ✅ | ✅ | — | — |
| GET `/api/history` | NFR-004 | ✅ | ✅ | — | — |

---

## 五、需求覆盖率统计

### 5.1 按实现状态

| 状态 | 数量 | 占比 |
|------|:---:|:----:|
| ✅ 已实现 | 24 | 61.5% |
| 🔶 进行中 | 0 | 0% |
| 📋 待开发 | 3 | 7.7% |
| 📅 二期 | 12 | 30.8% |
| **合计** | **39** | **100%** |

### 5.2 按需求类型

| 类型 | 数量 | 已实现 | 待开发 | 二期 |
|------|:---:|:-----:|:-----:|:---:|
| FR (功能需求) | 16 | 16 | 0 | 0 |
| FR-P1 (待完成) | 3 | 0 | 3 | 0 |
| FR-P2 (二期) | 10 | 0 | 0 | 10 |
| BR (业务规则) | 7 | 7 | 0 | 0 |
| NFR (非功能) | 8 | 8 | 0 | 0 |
| **合计** | **44** | **31** | **3** | **10** |

### 5.3 按文档来源覆盖

| 来源文档 | 涵盖需求数 | 覆盖率 |
|---------|:---------:|:-----:|
| 功能规格说明书 | 19 | 100% |
| 系统架构设计 | 10 | 100% |
| 数据库设计 | 16 | 100% |
| API接口规范 | 15 | 100% |
| 视觉识别Harness架构 | 12 | 100% |
| 门禁规范 | 8 | 100% |
| 模型调用规范 | 10 | 100% |
| 整体技术方案 | 17 | 100% |
| 首期工程化任务书 | 22 | 100% |

---

## 六、附录：术语对照表

| 术语 | 完整释义 | 相关需求 |
|------|---------|---------|
| Harness | BuildSight自研视觉识别流水线架构（5阶段：预处理→推理→校验→重试→输出） | FR-004~006, FR-016 |
| 三层门禁 | 前端操作拦截 + 后端资源锁控 + 数据合规校验的容错体系 | FR-015, BR-005 |
| 任务状态机 | 5种互斥状态：idle/cad_running/ai_running/merge_running/export_running | FR-015, BR-005, NFR-001 |
| 透视裁剪 | 针对效果图透视特性，按比例裁剪 ceiling(0-30%)/wall(25-75%)/floor(60-100%) | FR-005 |
| 4Sheet导出 | 报价Excel的4个Sheet：报价汇总/分层明细/工序对照/材质清单 | FR-009 |
| 融合报价 | CAD精准工程量 + AI材质识别 按空间+部位自动匹配后的报价 | FR-007~008, BR-003 |
| 同义词引擎 | 空间名称/材质名称的同义词模糊匹配机制（当前26组） | FR-P1-001, BR-003 |
| 识别门禁 | 字段填充率≥90% + 准确率≥80% + 空间偏差≤1/3 + 单图耗时≤10s | NFR-002, NFR-005, NFR-006 |

---

> **文档维护说明**  
> 本文档应与以下文档同步更新：  
> - `01-需求分析阶段/02-需求分析报告/功能规格说明书.md`  
> - `02-系统设计阶段/01-系统架构设计/系统架构.md`  
> - `02-系统设计阶段/02-数据库设计/数据库设计.md`  
> - `02-系统设计阶段/03-API设计/API接口规范.md`  
> - `02-系统设计阶段/04-视觉识别架构/视觉识别Harness架构.md`  
> - `02-系统设计阶段/05-模型调用规范/模型调用规范.md`  
> - `03-编码实现阶段/02-门禁规范/三层门禁规范.md`  
> - `05-项目收尾阶段/03-结题报告/整体技术方案.md`  
> - `05-项目收尾阶段/04-项目任务书/首期工程化任务书.md`  
> 
> 新增/变更需求时，遵循以下流程：  
> 1. 更新对应来源文档  
> 2. 在本文档对应行添加/修改条目  
> 3. 更新覆盖率统计  
> 4. 标记变更日志
