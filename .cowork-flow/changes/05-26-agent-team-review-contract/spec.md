# Agent-team review contract spec

## 行为要求

### 1. Assignment prompt 必须按 role 区分职责

`agent-team prepare` 生成的 `agent-team/assignments/<assignment-id>.md` 必须继续包含通用 worker 护栏：

- 文件开头必须包含 `<COWORK-FLOW-WORKER>` 标记，供 agent 和 start 技能快速识别这是 assignment-scoped worker prompt。
- assignment id、role、recommended agent、agent type、task title。
- `You are already the dispatched worker for this assignment.`
- 明确 `.agent/skills/start` 的 `<SUBAGENT-STOP>` guard 适用于该子线程，看到 start-session 指令时必须跳过主会话入口。
- 不运行主会话 start/resume、不重新派发 worker、不运行未带 context 的 workflow 命令。
- 可通过 assignment `.context.json` 做 worker-scoped resume。

同时，`## Your job` 和 `## Report format` 必须按 role 区分：

- `implementer`：执行计划步骤，修改限定文件，报告 changed files 与验证命令。
- `spec-reviewer`：只审查 PRD/proposal/spec/design/plan 与 implementer 结果是否一致，不实现代码，不声称 changed files。
- `quality-reviewer`：只审查代码质量、测试和验证证据，不实现代码，不替代 spec review。
- `## Completion protocol` 必须说明最终聊天文本不完成 assignment，worker 需要通过 scoped context 运行 `agent-team worker-report` 写 outbox，由 coordinator 运行 `agent-team collect`。

### 1.1 内建执行链 host type 必须是 worker

`implementer`、`spec-reviewer`、`quality-reviewer` assignment 的 `agent_type` 必须是 `worker`。

`agents.yaml` 仍可影响 `recommended_agent` 和 `prompt`，但不得把这些内建 assignment 的 host type 改成 `default`、`reviewer` 或其他 coordinator-like 类型。

### 2. record-spawn 必须暴露已派发状态

当主 agent 执行：

```bash
./.cowork-flow/run agent-team record-spawn <task-dir> --assignment <id> --task-name <returned-task-name> [--nickname <nickname>]
```

目标 assignment 必须从 `ready` 变为 `in_progress`，并保存 `spawn_task_name` 与可选 `spawn_nickname`。

`agent-team next` 只能输出 `ready` assignment，不得重复输出已 `in_progress` 的 assignment。

### 3. result/review status 必须按命令校验

`record-result` 只接受：

- `done`
- `done_with_concerns`
- `blocked`
- `needs_context`

`record-review` 只接受：

- `approved`
- `changes_requested`
- `blocked`
- `needs_context`

其他 status 必须失败并输出允许值。

### 4. approved review 必须有有效 payload

`record-review --status approved` 必须带 `--file <json>`，且 JSON payload 至少满足其一：

- `decision: "approved"`
- `status: "approved"`

缺少 payload、payload 不是 JSON、或 approved payload 不含 approved decision/status 时，命令必须失败，且不得修改 assignment 状态、attempts 或 metrics。

非 approved review status 可带 payload，但不强制。

### 5. 非终态不得解锁后续 assignment

只有以下 status 可解锁依赖：

- implementer `done`
- spec/quality reviewer `approved`

`done_with_concerns`、`changes_requested`、`blocked`、`needs_context`、`in_progress` 均不得解锁后续 assignment。

### 6. 子线程停止但无有效报告必须进入 retry

`agent-team-execution` 技能必须明确：

- `wait_agent` 返回后，主 agent 先检查 worker 报告是否符合 assignment 的 role-specific report format。
- 主 agent 不得无限等待；子线程进入 start/resume 主会话流程或 bounded wait 后仍没有 assignment 进展时，应关闭子线程。
- 如果子线程结束但没有有效 report，不能记录 `done` 或 `approved`。
- 主 agent 应记录 `retry --reason adapter_failed`，并在下一次派发前补充更明确上下文或拆分 assignment。

### 7. worker-report 只能写 worker outbox

worker-scoped 命令：

```bash
./.cowork-flow/run --context-file <assignment.context.json> agent-team worker-report --status <status> --file <payload.json>
```

必须满足：

- 只能在 worker execution context 下运行。
- 默认 assignment 来自 context；如果显式传入 `--assignment`，必须与 context assignment 一致。
- 只能写入当前 assignment 的 `agent-team/outbox/<assignment-id>.json`。
- 不得修改 `status.json`、`metrics.json`、`results/` 或 `reviews/`。
- status 必须按 assignment role 校验：implementer 使用 result status，reviewer 使用 review status。
- approved reviewer report 必须带 JSON payload，且 payload 中有 `decision: "approved"` 或 `status: "approved"`。

### 8. collect 只能由 coordinator 推进状态

coordinator 命令：

```bash
./.cowork-flow/run agent-team collect <task-dir> --assignment <id>
```

必须满足：

- 没有 `agent-team/outbox/<assignment-id>.json` 时失败，不得修改状态。
- 当前 assignment 必须是 `ready` 或 `in_progress`；pending assignment 的 outbox 不得越过依赖链。
- outbox 中的 assignment、role、status 必须与 runtime status 中的 assignment 匹配。
- approved reviewer payload 必须再次校验。
- 校验通过后才可复用现有 result/review 记录逻辑推进状态、attempts、metrics 和依赖解锁。
- 子线程最终聊天答案不能替代 outbox。

## 兼容性

- 保留现有 `record-result --status done` 与 `record-review --status approved` 成功路径。
- 保留现有 payload copy 目录：`results/` 和 `reviews/`。
- 不改变 `status.json` 顶层结构，不改变 `dispatch-plan.yaml` 格式。
- 新增 `outbox/` 目录作为 worker -> coordinator 的持久边界。
- root 与 `template/` 的脚本和技能文档必须保持一致。
