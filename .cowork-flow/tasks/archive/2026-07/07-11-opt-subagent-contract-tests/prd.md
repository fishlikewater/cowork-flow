# P2 强化正式子代理宿主契约测试

## Goal

把正式子代理的 runtime context 绑定、fail-closed、安全禁止事项和三宿主适配差异固化为回归测试，避免后续重构破坏安全链。

## Scope

- 补充 Codex、Claude Code、OpenCode 相关契约测试。
- 覆盖 runtime context missing、closed、invalid、mismatched、duplicate bind。
- 覆盖 fixed agent 禁止 start/resume/archive/commit/spawn 的资产文本。
- 覆盖主会话 dispatch/check/close 的验收边界。
- 必要时修复测试暴露的宿主资产漂移。

## Non-Goals

- 不新增宿主。
- 不改变 formal dispatch 协议。
- 不让 generic worker 满足 formal Implement/Check。

## Acceptance Criteria

1. 缺失、关闭、无效、错配 runtime context 均进入 fail-closed 输出。
2. 相同 runtime/context key 重复 bind 幂等，不同 key bind 被拒绝。
3. host adapter payload 包含必要 runtime context 与 host context key 信息。
4. fixed agent 资产文本明确禁止 start/resume/archive/commit/spawn。
5. 子代理输出不能绕过主会话 check/bind/close 验收。
6. Python 与 Node 宿主测试通过。

## Relevant Files

- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/common/entry_classifier.py`
- `.cowork-flow/scripts/common/inject_workflow_state.py`
- `.codex/agents/cowork-implement.toml`
- `.codex/agents/cowork-check.toml`
- `.claude/skills/`
- `.opencode/plugins/cowork-flow.js`
- `tests/test_subagent_dispatch.py`
- `tests/test_host_adapters.py`
- `tests/test_codex_hooks.py`
- `tests/test_claude_hooks.py`
- `test/opencode-plugin.test.js`
- `template/`

## Verification

- `.cowork-flow/run.cmd python -m pytest tests/test_subagent_dispatch.py tests/test_host_adapters.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q`
- `npm test -- test/opencode-plugin.test.js`
- `.cowork-flow/run.cmd doctor --subagent-safety`
- `git diff --check`