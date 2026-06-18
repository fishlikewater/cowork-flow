# P1-A Runtime/Agent Run Convergence

## Goal

消除 `runtime_context` 与 `agent_run` 的字段重叠，使 `runtime_context` 成为一次派发运行记录的唯一权威。`agent_run` 表标记 deprecated，读路径只查 `runtime_context`。

## Background

当前 `list_agent_runs_for_parent` / `list_agent_runs_for_task` 分别从 `runtime_context` 和 `agent_run` 两张表查询，合并去重后返回。两张表有大量重叠字段（id, task_id, agent_type, status, host_context_key/bound_context_key, error_message, created_at, closed_at）。`_runtime_context_to_agent_run` 投影逻辑硬编码 `retry_count: 0`，实际无用。

`subagent.py` 是唯一还在写 `agent_run` 的调用方（`create_agent_run` + `get_active_agent_run`）。Dashboard server 通过 `list_agent_runs_for_task` 间接读取。

根据 spec P1-A 方案 1（推荐）：`runtime_context` 是唯一权威，`agent_run` 保留但停止写入，下个大版本删除。

## Scope

### 代码改动

1. **`subagent.py`**：
   - `_record_agent_run_for_task`：停止调用 `store.create_agent_run`（正式派发只写 `runtime_context`）。
   - `cmd_spawn_family`：去掉 `store.create_agent_run` 调用；用 `runtime_context` 查询代替 `get_active_agent_run`。
2. **`store.py`**：
   - `list_agent_runs_for_parent` / `list_agent_runs_for_task`：只查 `runtime_context`，去掉 `agent_run` 合并逻辑。
   - `get_active_agent_run`：查 `runtime_context` 代替 `agent_run`。
   - `create_agent_run` / `update_agent_run_status`：标记 deprecated，保留但加注释。
   - 删除 `_runtime_context_to_agent_run` 投影方法（不再需要）。
3. **`dashboard/server.py`**：
   - `list_agent_runs_for_task` 调用不变（store 内部已改为只查 runtime_context）。
4. **`schema.sql` / `0001_initial.sql`**：不删除 `agent_run` 表（deprecated 保留）。
5. **模板同步**：root ↔ template 一致性。

### 不改动

- 不删除 `agent_run` 表（deprecated 保留）。
- 不修改 `RUNTIME_CONTEXT_DISPATCH_V2` 协议。
- 不改动 advisory dispatch 不创建正式 run 的语义。

## Non-Goals

- 不实现方案 2（两表分工，不重叠）。
- 不删除 `agent_run` 表。
- 不改 dashboard 视图逻辑。

## Acceptance Criteria

1. `list_agent_runs_for_parent` / `list_agent_runs_for_task` 只查询 `runtime_context`，不查 `agent_run`。
2. `get_active_agent_run` 只查询 `runtime_context`。
3. `subagent.py` 不再调用 `store.create_agent_run`。
4. `_runtime_context_to_agent_run` 方法已删除。
5. 现有测试通过：`test_flow_store.py`、`test_subagent_dispatch.py`、`test_dashboard.py`。
6. root/template 一致性通过。

## Verification

- `python -m pytest tests/test_flow_store.py tests/test_subagent_dispatch.py tests/test_dashboard.py -v`
- `npm run test:template`
- `git diff --check`

## 关联

- Change: `06-15-workflow-maturity-roadmap`（P1-A）
- Plan: `2026-06-15-workflow-maturity-roadmap.md` P1-A Phase
- 上游依赖：P0-B（schema 版本化）
