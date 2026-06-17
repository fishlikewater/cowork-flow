# Fan-out pattern

`fan_out` 用于父任务等待一组子任务完成。父任务本身不派发子任务；pattern 层只提供校验、状态门禁和只读 next action。

## Required shape

- 父任务 `pattern` 必须为 `fan_out`。
- 父任务必须有 child tasks。
- 每个 child 的 `pattern` 必须为 `generic`。
- child 完成条件为 `status in {"completed", "archived"}`。

Fan-out 不要求专用 metadata。子任务关系来自 `FlowStore.list_children(task_id)`。

## Valid transitions

| From | To | Gate |
| --- | --- | --- |
| `planning` | `in_progress` | 父任务有 children, 且 children 均为 `generic`。 |
| `in_progress` | `review` | 所有 children 已 `completed` 或 `archived`。 |
| `review` | `completed` | 常规 review 通过。 |
| `completed` | `archived` | 常规归档。 |

`fan_out` 不支持 `blocked` 状态。需要人工决策的父任务应使用 `human_loop` 或拆分为单独任务。

## Validation

`validate(ctx)` 返回以下错误：

- `Fan-out task must have child tasks`
- `Child '<child-id>' pattern must be 'generic'`

## Next action

当父任务处于 `in_progress`：

- 若仍有 pending children，`next_action(ctx)` 返回 `StepKind.WAIT_CHILDREN`，`children` 列出未完成 child ids。
- 若所有 children 完成或归档，返回 `StepKind.COMPLETE`，提示父任务可进入 review/complete 路径。

`task next` 会打印 pattern action 和 pending children，但不会修改数据库。

## Lifecycle behavior

- `task review <parent>` 在任一 child 未完成时失败。
- child 状态改变后，重新运行 `task review <parent>` 即可重新计算 gate。
- `fan_out` 不自动推进父任务到 `review` 或 `completed`。
