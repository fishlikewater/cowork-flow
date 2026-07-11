# P1 收敛运行时状态权威

## Goal

审计并收敛 cowork-flow 的运行时状态读写入口，确保 DB `runtime_context`、`runtime_session` 和 task 状态继续作为当前权威，历史文件态只保留为明确兼容/诊断路径。

## Scope

- 审计 active task、runtime context、runtime session、task lifecycle、archive、journal、dashboard 的读写入口。
- 补充状态权威回归测试。
- 删除或隔离最安全的旧文件态兼容路径。
- 更新 spec、skills、agent assets 和 template 镜像中的状态权威表述。

## Non-Goals

- 不做 DB schema 大迁移；如发现必须迁移，拆出新任务。
- 不改变 fixed agent 叶子执行者边界。
- 不重写宿主插件，只修正状态权威相关路径和文案。

## Acceptance Criteria

1. 状态权威矩阵中的每个写入口都有测试或明确保留理由。
2. 新增回归测试证明 missing/closed/invalid runtime context 会 fail-closed。
3. 文档和宿主资产不再把废弃 `.runtime` 文件态描述为当前权威。
4. 保留的兼容路径在代码或文档中标注用途。
5. root/template 同步完成。
6. 相关 Python/Node 测试通过。

## Relevant Files

- `.cowork-flow/scripts/common/active_task.py`
- `.cowork-flow/scripts/common/execution_context.py`
- `.cowork-flow/scripts/common/inject_workflow_state.py`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/spec/core/dispatch.md`
- `.cowork-flow/spec/core/lifecycle.md`
- `.codex/agents/`
- `.claude/skills/`
- `.opencode/plugins/cowork-flow.js`
- `template/`

## Verification

- `.cowork-flow/run.cmd python -m pytest tests/test_active_task_runtime.py tests/test_subagent_dispatch.py tests/test_host_adapters.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q`
- `npm test -- test/opencode-plugin.test.js`
- `.cowork-flow/run.cmd doctor --subagent-safety`
- `npm run test:template`
- `git diff --check`