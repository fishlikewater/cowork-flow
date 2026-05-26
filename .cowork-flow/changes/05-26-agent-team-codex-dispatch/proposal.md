# 05-26-agent-team-codex-dispatch Proposal

## 背景

真实 Codex 中执行 agent-team 时，计划标题使用 `## Task N:` 会导致 parser 无法识别任务，因为当前解析器只接受 `### Task N:`。同一流程中，`agent-team-execution` skill 对 Codex 子 agent 调度描述过于宽松，已配置 `[features] multi_agent = true` 时仍可能退化为主 agent 自行执行 assignment prompt。

## 目标

- 让 agent-team plan parser 接受 `## Task N:` 和 `### Task N:` 两种 writing-plans 标题层级。
- 明确 Codex 环境中 agent-team 的真实调度协议：Python 脚本生成 assignments，主 agent 使用 `spawn_agent`、`wait_agent`、`close_agent` 执行和回收子 agent。

## 非目标

- 不让 Python CLI 直接调用 Codex 子 agent 工具。
- 不改变 assignment 状态机、依赖图算法或 review 链路。
- 不新增外部依赖。
