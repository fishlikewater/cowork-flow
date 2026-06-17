# Flow pattern contracts

本目录定义当前 task pattern 契约。Pattern 是纯决策层，只接收 `TaskContext`，返回校验结果、状态流转许可和只读 next action。Pattern 不读取文件、不访问 `FlowStore`、不派发 agent、不修改任务状态。

## Pattern boundary

- `FlowStore` 是 task 状态、metadata、block、child 关系的唯一写入口。
- `task.py` 负责从 `FlowStore` 读取 task、children、active block，组装 `TaskContext`。
- `patterns/` 只实现 `validate(ctx)`、`next_action(ctx)`、`transition_allowed(from, to)` 和 `can_transition(ctx, to)`。
- `task next` 只展示 pattern action，不改变数据库。

## Shared status model

| Status | Meaning |
| --- | --- |
| `planning` | 任务已创建, 尚未启动。 |
| `in_progress` | 实现阶段。 |
| `blocked` | 等待阻塞解除或人工决策。 |
| `review` | 等待检查或阶段验收。 |
| `completed` | 任务完成, 可归档。 |
| `archived` | 归档状态。 |

## Shared context shape

```python
TaskContext(
    task=TaskView(...),
    children=list[TaskView],
    active_block=BlockView | None,
)
```

`TaskView.meta` 承载 pattern 专用字段。字段必须保持 JSON 可序列化，并通过 `FlowStore.update_meta()` 写回。

## Implemented patterns

| Pattern | Purpose | Spec |
| --- | --- | --- |
| `generic` | 默认基线生命周期。 | 本文件 |
| `fan_out` | 父任务等待多个 generic 子任务完成。 | [fan-out.md](./fan-out.md) |
| `pipeline` | 单任务按阶段 review/redo/complete。 | [pipeline.md](./pipeline.md) |
| `human_loop` | 阻塞状态必须记录人工决策后恢复。 | [human-loop.md](./human-loop.md) |

## Generic

Generic 不要求 metadata，不产生 pattern action。

| From | To |
| --- | --- |
| `planning` | `in_progress` |
| `in_progress` | `blocked`, `review` |
| `blocked` | `in_progress` |
| `review` | `completed` |
| `completed` | `archived` |

重复执行同一状态迁移会被拒绝。例如已经是 `in_progress` 的任务再次 `task start` 会失败，因为 `in_progress -> in_progress` 不在 Generic 白名单内。

## Registry

`PatternRegistry.resolve(task)` 以 `task.pattern` 为准，未知 pattern 回退到 `generic`。

`PatternRegistry.select(task)` 是 advisory selection:

- 有 children 时建议 `fan_out`。
- `meta.stages` 存在时建议 `pipeline`。
- `meta.decision_points` 存在时建议 `human_loop`。
- 其它情况建议 `generic`。

## Pattern Boundary

- Fan-out 不负责创建、派发或检查子任务。
- Pipeline 不派发 stage worker，只约束当前任务状态和 `current_stage`。
- Human-loop 不决定业务答案，只要求 unblock 时记录 decision。
- 跨任务并发、`spawn-family`、`check-family` 不属于 pattern 决策层，由 subagent dispatch/runtime 负责。
