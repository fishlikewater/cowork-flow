# 支持 Claude Code shell session id

## 目标

Claude Code shell 中执行 `.\.cowork-flow\run.cmd task start <task-dir>` 时，能直接使用 `CLAUDE_CODE_SESSION_ID` 形成会话级 context key，不再要求用户手动设置 `COWORK_FLOW_CONTEXT_ID`。

## 范围

- `resolve_context_key` 识别 `CLAUDE_CODE_SESSION_ID`。
- hook 输入解析兼容 `claude_code_session_id`。
- 同步 root/template runtime helper。
- 增加回归测试覆盖 env 与结构化输入。

## 非目标

- 不改变 Claude hook 的 runtime-context bind 协议。
- 不引入新的 Claude shell hook 或额外持久化状态。
- 不改变现有 `CLAUDE_SESSION_ID` 优先级。

## 验收标准

- `CLAUDE_CODE_SESSION_ID=abc` 时解析为 `claude_abc`。
- hook 输入 `claude_code_session_id=abc` 时解析为 `claude_abc`。
- 现有 OpenCode/Codex/Claude session 解析测试仍通过。

## 验证

- `python -m unittest discover -s tests -p "test_active_task_runtime.py" -v`
- `python -m unittest discover -s tests -p "test_claude_hooks.py" -v`
- `npm run test:template`
- `git diff --check`
