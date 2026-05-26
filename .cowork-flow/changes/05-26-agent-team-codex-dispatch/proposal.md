# 05-26-agent-team-codex-dispatch Proposal

## 背景

真实 Codex 中执行 agent-team 时，计划标题使用 `## Task N:` 会导致 parser 无法识别任务，因为当前解析器只接受 `### Task N:`。同一流程中，`agent-team-execution` skill 对 Codex 子 agent 调度描述过于宽松，已配置 `[features] multi_agent = true` 时仍可能退化为主 agent 自行执行 assignment prompt。

## 目标

- 让 agent-team plan parser 接受 `## Task N:` 和 `### Task N:` 两种 writing-plans 标题层级。
- 明确 Codex 环境中 agent-team 的真实调度协议：Python 脚本生成 assignments，主 agent 使用官方自然语言 orchestration prompt 请求 Codex 调度子 agent。
- 为 agent-team 增加运行时证据门禁：只有看到真实 child thread / agent job 证据时，才允许把 assignment 记为已由 subagent 执行。

## 非目标

- 不让 Python CLI 直接调用 Codex 子 agent 工具。
- 不改变 assignment 状态机、依赖图算法或 review 链路。
- 不新增外部依赖。
- 不假装解决当前宿主或 provider 本身不暴露 subagent 编排能力的问题。
