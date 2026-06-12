# Pipeline pattern

`pipeline` 用于一个任务按固定阶段循环 `in_progress -> review -> in_progress`，直到所有阶段通过后完成。

## Required metadata

```json
{
  "stages": [
    {"name": "implement"},
    {"name": "check"}
  ],
  "current_stage": 0
}
```

- `stages` 必须是非空 list。
- stage item 推荐使用 object，并提供 `name`。
- `current_stage` 是 zero-based integer，缺省为 `0`。
- `current_stage` 不得为负数。

## Valid transitions

| From | To | Gate |
| --- | --- | --- |
| `planning` | `in_progress` | `stages` 有效。 |
| `in_progress` | `review` | 当前阶段进入 review。 |
| `review` | `in_progress` | 当前阶段未最终完成, 可返工。 |
| `review` | `completed` | `current_stage >= len(stages)`。 |
| `completed` | `archived` | 常规归档。 |

## Validation

`validate(ctx)` 返回以下错误：

- `Pipeline task must define stages`
- `Pipeline task current_stage must be non-negative`

## Stage completion

`task complete <pipeline-task>` 在 `review` 状态有特殊处理：

1. 读取 `current_stage` 和 `len(stages)`。
2. 将 `current_stage` 加 `1` 并写回 `meta`。
3. 若新阶段索引仍小于阶段总数，任务状态写回 `in_progress`。
4. 若新阶段索引大于或等于阶段总数，任务状态写为 `completed`。

因此 pipeline 的中间阶段使用同一个 `task complete` 命令确认阶段通过。只有最后一个阶段通过后，任务才进入 `completed`。

## Next action

- `in_progress` 且当前阶段有效时，返回 `StepKind.REVIEW`，描述当前 stage。
- `review` 且当前阶段未全部完成时，返回 `StepKind.DISPATCH`，提示 redo 当前 stage。
- `review` 且 `current_stage >= len(stages)` 时，返回 `StepKind.COMPLETE`。

`task next` 只展示这些建议，不推进 `current_stage`。

## Phase 2 limits

Pipeline 不负责为每个 stage 派发不同 agent，也不维护 stage 独立产物目录。Stage 产物、验证命令和验收结论仍由当前任务 PRD、JSONL 和人工检查承载。
