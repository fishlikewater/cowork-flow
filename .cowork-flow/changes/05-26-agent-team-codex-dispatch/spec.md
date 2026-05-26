# 05-26-agent-team-codex-dispatch Spec

## Plan 解析

当 `agent-team prepare <task-dir> --plan <plan-file>` 读取 implementation plan 时，必须识别以下两种任务标题：

- `## Task N: <title>`
- `### Task N: <title>`

两种标题生成的 task id、assignment id、文件边界、步骤、命令和显式依赖行为应保持一致。无法识别任何 task 时，仍必须返回非 0 并输出 `unable to parse`。

## Codex 子 Agent 调度说明

`agent-team-execution` skill 必须明确说明：

- 在 Codex 且 `[features] multi_agent = true` 可用时，主 agent 必须使用 `spawn_agent` 调度 ready assignment。
- 主 agent 必须使用 `wait_agent` 收集子 agent 结果，并使用 `close_agent` 释放 worker slot。
- 只有当前宿主不暴露 `spawn_agent`、`wait_agent` 或 `close_agent` 时，才允许降级到 manual prompt 执行。
- assignment 以 Markdown prompt 存在不是降级 manual 的理由。

## 验收标准

- 使用 `## Task N:` 的 plan 可以生成 `T001-implementer` 等 assignments。
- 现有 `### Task N:` plan 解析行为不回退。
- 根目录与 template 中的 `agent-team-execution` skill 都包含 Codex `spawn_agent` / `wait_agent` / `close_agent` 协议。
