# Human-loop pattern

`human_loop` 用于需要人工决策的阻塞流程。它保留 Generic 的主生命周期，但要求从 `blocked` 恢复时记录 decision。

## Required metadata

```json
{
  "decision_points": [
    {"question": "Choose implementation direction"}
  ],
  "current_decision": 0
}
```

- `decision_points` 必须是非空 list。
- decision point 推荐使用 object，并提供 `question`。
- `current_decision` 是 zero-based integer，缺省为 `0`。
- 当前问题由 `min(current_decision, len(decision_points) - 1)` 选择。

## Valid transitions

| From | To | Gate |
| --- | --- | --- |
| `planning` | `in_progress` | `decision_points` 有效。 |
| `in_progress` | `blocked` | 常规阻塞。 |
| `blocked` | `in_progress` | active block 已记录 decision。 |
| `in_progress` | `review` | 常规 review。 |
| `review` | `completed` | 常规完成。 |
| `completed` | `archived` | 常规归档。 |

## Validation

`validate(ctx)` 返回以下错误：

- `Human-loop task must define decision_points`

## Block and unblock

- `task block <task> --reason <text>` 进入 `blocked` 并创建 active block。
- `task unblock <task> --decision <text>` 对 `human_loop` 是正常恢复路径，会记录 decision 并回到 `in_progress`。
- `task unblock <task>` 不带 `--decision` 会失败。
- 非 `human_loop` task 使用 `task unblock` 时必须显式传 `--force`。

`--force` 是人工逃生口，会直接把任务状态写回 `in_progress`。使用它时应在任务日志中说明原因，因为它不表达业务 decision。

## Next action

当任务处于 `blocked` 且 metadata 有 decision point 时，`next_action(ctx)` 返回 `StepKind.HUMAN_DECISION`，description 为当前问题。

`task next` 只展示问题，不写入 decision。
