# 修复 agent-team Codex 子 agent 调度

## 目标

修复真实 Codex 中 agent-team 执行的两个偏差：计划标题层级不兼容导致 parser 读不到任务，以及 multi-agent 已启用时 skill 没有强制主 agent 使用真实 Codex 子 agent 工具。

## 范围

- 修改 agent-team plan parser 的 Task 标题正则。
- 同步 template 中的 parser。
- 修改根目录与 template 的 `agent-team-execution` skill 文案。
- 增加针对 `## Task N:` 和 Codex `spawn_agent` 协议的回归测试。

## 验收标准

- `## Task N:` 和 `### Task N:` 都能被 `agent-team prepare` 解析。
- `agent-team-execution` 明确要求 Codex multi-agent 可用时使用 `spawn_agent`、`wait_agent`、`close_agent`。
- manual fallback 只在宿主缺少真实子 agent 工具时使用。
- agent-team 相关 Python unittest 通过。

## 验证方式

- `python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_docs -v`
- `python3 -m unittest tests.test_agent_team_state_machine tests.test_agent_team_runtime -v`
