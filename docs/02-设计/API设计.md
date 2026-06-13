# API 接口规范

## 统一响应格式

```json
{
  "success": true/false,
  "code": 200,
  "message": "操作成功",
  "data": {},
  "task_status": "idle",
  "trace_id": ""
}
```

## 接口列表

### 核心业务

| 方法 | 端点 | 说明 | 锁 |
|------|------|------|----|
| POST | `/api/analyze_full` | DXF解析+报价 | cad |
| POST | `/api/analyze` | 效果图结构化识别 | ai |
| POST | `/api/data_merge` | CAD+材质数据融合 | merge |
| POST | `/api/export_excel` | 导出报价Excel | export |

### 分层工程量

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/spaces/{drawing_id}/compute_breakdown` | 计算墙/地/顶分层 |
| GET | `/api/spaces/{drawing_id}/breakdown` | 查询分层+材质 |
| POST | `/api/spaces/breakdown/bind_material` | 手动绑定材质 |

### 施工工序

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/processes` | 列表 |
| GET | `/api/processes/{id}` | 详情 |
| POST | `/api/processes` | 新建 |
| PUT | `/api/processes/{id}` | 修改 |
| DELETE | `/api/processes/{id}` | 删除 |
| GET | `/api/processes/quotes/summary` | 工序×报价汇总 |

### 配置管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/settings/pricing` | 查询定价配置 |
| POST | `/api/settings/pricing` | 修改定价配置 |
| GET | `/api/settings/vl_model` | 查询视觉模型 |
| POST | `/api/settings/vl_model` | 切换视觉模型 |
| GET | `/api/settings/vl_model/test` | 测试模型连通性 |

### 系统

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/system/status` | 任务锁+服务状态 |
| GET | `/api/system/health` | 健康检查 |
| GET | `/api/history` | 历史报价列表 |
| GET | `/api/history/{id}` | 报价详情 |
| GET | `/api/logs` | 操作日志 |
| GET | `/api/drawings` | 图纸列表 |

### 兼容

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/health` | 旧版健康检查 |
| GET | `/api/config` | 旧版配置查询 |
