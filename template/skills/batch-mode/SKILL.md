---
name: batch-mode
description: 用户批准完整计划并要求按任务图连续执行时使用；每个任务仍独立经过 Gate、实现、检查、完成和提交。
---

# Batch Mode

## 核心契约

Batch Scheduler 是持久化状态机，不在 CLI 内模拟实现或检查完成。

- 任务顺序只来自 change/task graph 的叶子任务拓扑序。
- `implement.jsonl` 和 `check.jsonl` 只作为当前任务上下文与 Gate 证据，
  不能作为 Batch 任务列表。
- 每次只发布一个 host-neutral `next_action`。
- Host 执行真实动作后，必须回写结果；状态机验证仓库状态后才推进。
- 任何 Gate、绑定、实现、检查、测试、完成或提交失败都会暂停。
- 已完成的任务、阶段和提交不会在恢复时重复执行。

## 启动条件

仅在以下条件全部满足时启动：

1. 用户明确批准计划并要求自动连续执行。
2. parent task 与所有叶子任务已建立有效 task graph。
3. 当前会话是 main/coordinator，不是 worker 或 delegated subagent。
4. Host 能执行 task、subagent 和 Git 动作。

启动命令：

```bash
./.cowork-flow/run task start <parent-task> --auto --approved
```

命令返回完整 Batch 状态，其中 `next_action` 是唯一允许执行的下一步。

## Host Action 循环

每次按以下顺序处理：

1. 读取 `next_action`，核对 `action_id`、`type`、`task` 和 `task_dir`。
2. 只执行该动作，不提前执行后续阶段。
3. 将结果写入 UTF-8 JSON 文件。
4. 回写结果：

```bash
./.cowork-flow/run task batch-record-result <batch-id> --file <result.json>
```

5. 读取新状态；若为 `awaiting_host`，继续新的 `next_action`；若为 `paused`，
   停止后续任务。

## Action 类型

### `start_task`

运行真实任务启动命令并通过 readiness/spec/TDD Gate：

```bash
./.cowork-flow/run task start <task_dir>
```

成功结果必须包含：

```json
{
  "action_id": "<action-id>",
  "type": "start_task",
  "outcome": "success",
  "task_status": "in_progress"
}
```

状态机同时读取 `task.json`，仅相信真实的 `in_progress` 状态。

### `init_implement_context` / `init_check_context`

按 action 中的 `role`、`agent_type`、`task_dir` 和 `title` 运行：

```bash
./.cowork-flow/run subagent init \
  --role <role> \
  --agent-type <agent_type> \
  --execution-task-dir <task_dir> \
  --title "<title>"
```

Host 必须使用返回的 `cowork_runtime_context_id` 与
`cowork_host_context_key` 派发对应 worker，并让 worker 首步执行
`subagent bind`。

初始化结果必须回写：

```json
{
  "action_id": "<action-id>",
  "type": "init_implement_context",
  "outcome": "success",
  "runtime_context_id": "<runtime-context-id>",
  "host_context_key": "<host-context-key>"
}
```

检查阶段将 `type` 改为 `init_check_context`。

### `await_implement_result` / `await_check_result`

等待对应 worker 完成，验证输出属于当前任务且 runtime context 已绑定到预期 Host。

成功结果必须包含 action 中相同的 `runtime_context_id` 和
`host_context_key`。状态机验证 `status=bound` 后关闭 runtime context；
如果关闭成功但 Batch checkpoint 尚未落盘，重复回写仍可恢复。

### `review_task`

运行：

```bash
./.cowork-flow/run task review <task_dir>
```

成功结果的 `task_status` 必须为 `review`，状态机还会读取真实 `task.json`。

### `complete_task`

运行：

```bash
./.cowork-flow/run task complete <task_dir>
```

成功结果的 `task_status` 必须为 `completed`，状态机还会读取真实 `task.json`。

### `commit_task`

只提交当前任务已验证的改动，并回写真实 commit id：

```json
{
  "action_id": "<action-id>",
  "type": "commit_task",
  "outcome": "success",
  "commit_id": "<git-commit-id>"
}
```

状态机使用 Git 验证该对象确实是 commit；空值、占位字符串或不存在的 commit
都会暂停。

## 失败与恢复

Host 不可用或任一动作失败时，回写非 success 结果：

```json
{
  "action_id": "<action-id>",
  "type": "<action-type>",
  "outcome": "failure",
  "detail": "<specific cause>"
}
```

状态会变为 `paused`，失败任务与所有后续任务不会被标记 completed。

修复原因后运行：

```bash
./.cowork-flow/run task batch-resume <batch-id>
```

恢复会生成新的 `action_id`，但保留已完成任务、阶段、runtime 证据和 commit。
不要跳过失败任务，不要手工修改 Batch 状态文件。

## 完成验证

Batch 状态变为 `completed` 后：

1. 运行项目完整测试与构建命令。
2. 核对 `completed_tasks`、`task_phases` 与 `commits` 一一对应。
3. 核对每个叶子任务都有独立 commit。
4. 运行 spec sync、doctor 和发布前检查。
