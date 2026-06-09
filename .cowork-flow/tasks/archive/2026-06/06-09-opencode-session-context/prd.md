# 修复 OpenCode task start 会话上下文

## 目标

OpenCode 会话中通过 shell 执行 `.\.cowork-flow\run.cmd task start <task-dir>` 时，能够获得稳定的 main-session context key，不再因缺少 Codex-only 环境变量而报 `Missing session context`。

## 范围

- OpenCode plugin 为 shell 命令注入 `COWORK_FLOW_CONTEXT_ID` 和 `OPENCODE_SESSION_ID`。
- Python context 解析兼容 OpenCode `sessionID` / `session_id` 输入形态。
- `task start/current` 的缺失上下文错误提示改为 host-neutral。
- 同步 root/template 中对应 OpenCode plugin 与 runtime helper。

## 非目标

- 不改变 formal `cowork-*` runtime-context dispatch/bind 协议。
- 不新增第二套任务状态。
- 不改变 Codex 或 Claude 的 session key 优先级。

## 验收标准

- `resolve_context_key` 能从 OpenCode `sessionID` 输入得到 `opencode_<id>`。
- OpenCode plugin 声明 `shell.env` hook，并从 `sessionID` 注入 `COWORK_FLOW_CONTEXT_ID` / `OPENCODE_SESSION_ID`。
- 缺失上下文错误提示不再限定为 Codex session。
- 相关 Python 单测、host adapter/OpenCode 资产测试通过。

## 验证

- `python -m unittest discover -s tests -p "test_active_task_runtime.py" -v`
- `python -m unittest discover -s tests -p "test_host_adapters.py" -v`
- `python -m unittest discover -s tests -p "test_flow_script_paths.py" -v`
- `node --test test/opencode-plugin.test.js`
- `git diff --check`
