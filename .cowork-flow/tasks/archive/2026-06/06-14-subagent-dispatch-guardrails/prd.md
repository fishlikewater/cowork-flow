# Harden Formal Subagent Dispatch Guardrails

## Goal

降低主会话误用裸 `spawn_agent(agent_type="cowork-*")` 的概率：正式 `cowork-*` 子代理仍必须 runtime-context bind，但父侧提供更清晰、更不容易漏步骤的调度入口和回归测试。

## Scope

- 新增 Codex formal 子代理调度封装，输出 `spawn_agent` 所需 agent type、task name、fork 策略和包含 bind 步骤的 child prompt。
- `task next` 对 formal implement/check 路径优先提示封装命令，并明确禁止裸 `spawn_agent` 满足 workflow gate。
- 同步 root/template。
- 补充测试覆盖封装输出、`task next` 文案、防回归合同。

## Non-Goals

- 不放宽 child bind。
- 不让 Python CLI 直接调用 Codex host tool。
- 不改变 advisory `worker/default/explorer` 语义。
- 不处理 dashboard UI。

## Acceptance Criteria

1. Formal `cowork-*` dispatch 仍必须 `subagent init` 生成 DB runtime context。
2. 新命令能生成包含 `cowork_runtime_context_id`、`cowork_host_context_key` 和第一步 bind 命令的 child prompt。
3. `task next` 不再只给容易误解的低层 `subagent init` 步骤；Codex 场景提示封装命令和禁止裸派发。
4. root/template 相关脚本一致。
5. 测试覆盖误用防线。

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_subagent_dispatch tests.test_flow_script_paths -v`
- `rtk npm run test:template`
- `rtk .\.cowork-flow\run.cmd doctor --subagent-safety`
- `rtk git diff --check`
