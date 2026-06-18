# P4: Dashboard Observability

## Goal

为 dashboard 新增三个只读可观测性 API：任务时间线回放、失败归因聚类、readiness gate 通过率。数据全部来自现有表，不新增表，不引入写路径。

## Background

### 现状

dashboard 有看板（board_view）和任务详情（含 audit trail），但缺少：
- 任务从 planning → archived 的完整事件流时间线
- 失败原因的聚类统计
- readiness gate 的通过/失败比

### 数据源

| 数据 | 来源表 | 用途 |
|---|---|---|
| 状态流转 | `audit` | 时间线回放 |
| 阻塞记录 | `block` | 失败归因 |
| 运行时上下文 | `runtime_context` | 时间线中的派发/binding/close 事件 |
| 任务就绪检查 | `task.meta` | readiness gate 结果 |

## Scope

### 代码改动

1. **FlowStore 新增查询方法**（root + template）：
   - `get_task_timeline(task_id)` → 返回按时间排序的事件列表（audit + runtime_context）
   - `get_failure_clusters()` → 返回按 reason 聚类的失败统计
   - `get_readiness_stats()` → 返回 readiness gate 通过/失败比

2. **Dashboard server 新增 API**（root + template）：
   - `GET /api/task/<id>/timeline` → 时间线回放
   - `GET /api/failures` → 失败归因聚类
   - `GET /api/readiness` → readiness gate 统计

3. **测试更新**：
   - 新增 `test_dashboard_timeline_api`
   - 新增 `test_dashboard_failures_api`
   - 新增 `test_dashboard_readiness_api`

### Non-Goals

- 不新增前端页面（API-only，前端后续单独做）。
- 不新增数据库表。
- 不引入写路径。

## Acceptance Criteria

1. 三个新 API 端点存在且返回正确 JSON。
2. `/api/task/<id>/timeline` 返回按时间排序的事件列表。
3. `/api/failures` 返回按 reason 聚类的统计。
4. `/api/readiness` 返回通过/失败比。
5. root ↔ template 一致性。
6. `python -m pytest tests/test_dashboard.py -v` 通过。

## Verification

- `python -m pytest tests/test_dashboard.py -v`
- `rtk npm run test:template`
