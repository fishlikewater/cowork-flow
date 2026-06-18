# P3-A: Runtime Coordination Sink

## Goal

将主会话的机械协调步骤下沉到 runtime。主会话只需"派发 + 验收"，不再手动管理 init → dispatch → wait → verify → close 的完整生命周期。

## Background

### 现状

当前单任务派发流程（workflow.md §3.1 + §3.3.4）：

1. 主会话调用 `subagent init` → 创建 runtime context
2. 主会话调用 `subagent dispatch-codex` → 准备 spawn payload
3. 主会话调用宿主适配器 spawn_agent → 子代理启动
4. 子代理调用 `subagent bind` → 绑定 runtime context
5. 子代理执行工作
6. 子代理调用 `subagent close` → 关闭 runtime context
7. 主会话手动验证结果

步骤 1-2 是机械重复，步骤 7 依赖主会话"自觉"执行。`spawn-family`/`check-family` 已对 fan-out 父任务迈出下沉第一步。

### 方案

- 新增 `subagent dispatch` 命令：合并 `init` + `dispatch-codex` 为一步，输出 spawn payload + runtime_context_id。
- 新增 `subagent check` 命令：检查指定 runtime context 的完成状态（替代主会话手动 list/wait）。
- 更新 workflow.md §3.1 和 §3.3.4：简化协调模型描述。
- 适配器取消原语保留，但由 runtime 在收口时调用（通过 `subagent close`），不由主会话逐个调用。

## Scope

### 代码改动

1. **`subagent.py` 新增命令**（root + template）：
   - `subagent dispatch`：合并 `init` + `dispatch-codex`，输出完整 spawn payload。
   - `subagent check`：检查 runtime context 状态，输出 `{status, closed_at, ...}`。

2. **`workflow.md` 更新**（root + template）：
   - §3.1 简化：主会话通过 `subagent dispatch` 派发，通过 `subagent check` 验收。
   - §3.3.4 简化：主会话只发起 + 验收结果，runtime 负责协调。

3. **测试更新**：
   - 新增 `test_subagent_dispatch_merges_init_and_dispatch_codex`。
   - 新增 `test_subagent_check_reports_status`。

### Non-Goals

- 不改变子代理的 bind/close 行为（仍由子代理在 prompt 中执行）。
- 不引入阻塞等待（主会话仍是非阻塞的）。
- 不改变适配器契约。

## Acceptance Criteria

1. `subagent dispatch` 命令存在且输出正确的 spawn payload。
2. `subagent check` 命令存在且能报告 runtime context 状态。
3. `workflow.md` §3.1 和 §3.3.4 反映简化后的协调模型。
4. root ↔ template 一致性。
5. `python -m pytest tests/test_subagent_dispatch.py -v` 通过。

## Verification

- `python -m pytest tests/test_subagent_dispatch.py -v`
- `rtk npm run test:template`
