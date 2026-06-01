# Make post_ack_execution_grace_ms Runtime Effective

## Goal

让 `.cowork-flow/config.yaml` 中的 `codex.post_ack_execution_grace_ms` 从文档说明变成运行时可见配置。主会话每轮收到 workflow-state 时，应看到解析后的具体 grace 毫秒值，并据此计算每个 dispatch 的 post-ACK execution deadline。

## Scope

- 读取 `.cowork-flow/config.yaml` 的 `codex.post_ack_execution_grace_ms`。
- 缺省、缺文件、缺字段或非法值时安全回退到 `300000`。
- 在 Codex hook 注入的上下文中暴露解析后的值。
- root 与 `template/` 副本保持一致。
- 增加测试证明修改配置会改变 hook 注入的运行时值。

## Out of Scope

- 不重写 subagent 派发协议。
- 不引入新的集中式状态机。
- 不改变 `dispatch_mode` 的现有行为。
- 不改已归档任务/change 的历史内容。

## Acceptance Criteria

- `common.config` 提供 `get_codex_post_ack_execution_grace_ms()`，返回正整数毫秒值。
- 配置缺失、`codex` 缺失、字段缺失、非数字、非正数时返回默认值 `300000`。
- `.codex/hooks/inject-workflow-state.py` 读取该 getter，并在 `additionalContext` 中注入具体 `post_ack_execution_grace_ms`。
- hook 测试覆盖自定义值和非法值回退。
- root 与 template 的相关脚本同步。

## Relevant Files

- `.cowork-flow/scripts/common/config.py`
- `template/.cowork-flow/scripts/common/config.py`
- `.codex/hooks/inject-workflow-state.py`
- `template/.codex/hooks/inject-workflow-state.py`
- `tests/test_codex_hooks.py`
- `tests/test_workflow_parallel_sessions.py`

## Verification

- `python -m unittest tests.test_codex_hooks`
- `python -m unittest tests.test_workflow_parallel_sessions`
- `npm run test:all`
