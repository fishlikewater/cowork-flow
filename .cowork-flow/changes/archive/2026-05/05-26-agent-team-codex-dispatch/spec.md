# 05-26-agent-team-codex-dispatch Spec

## Plan 解析

当 `agent-team prepare <task-dir> --plan <plan-file>` 读取 implementation plan 时，必须识别以下两种任务标题：

- `## Task N: <title>`
- `### Task N: <title>`

两种标题生成的 task id、assignment id、文件边界、步骤、命令和显式依赖行为应保持一致。无法识别任何 task 时，仍必须返回非 0 并输出 `unable to parse`。

## Codex 子 Agent 调度说明

`agent-team-execution` skill 必须明确说明：

- 在 Codex 环境中，主 agent 必须使用官方自然语言 orchestration prompt 明确要求为 ready assignments 生成子 agent，并等待汇总结果。
- assignment 的 `agent_type` 必须作为 Codex spawn target 使用；`recommended_agent` 只代表 agent-team registry 匹配结果，除非它本身也是一个真实 Codex custom agent 名称。
- assignment 以 Markdown prompt 存在不是降级 manual 的理由。
- 只有看到真实 child thread、agent job、`/agent` 子线程可见，或 `spawn_agents_on_csv` 成功产出等宿主证据时，才允许把该 assignment 记录为 subagent 已执行。
- 如果最终回答只有“worker reported”之类措辞、但没有运行时证据，skill 必须停止在记录前并报告当前 Codex runtime 未实际启动 subagent。

## 验收标准

- 使用 `## Task N:` 的 plan 可以生成 `T001-implementer` 等 assignments。
- 现有 `### Task N:` plan 解析行为不回退。
- 根目录与 template 中的 `agent-team-execution` skill 都包含官方 Codex orchestration wording、`agent_type` / `recommended_agent` 边界，以及 subagent 运行时证据门禁。
