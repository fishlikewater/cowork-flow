# Fix subagent runtime-context dispatch prompts

## 背景

固定 `cowork-*` 子代理已经切换到 runtime-context 派发协议：主会话先创建 runtime context，再把 `cowork_runtime_context_id` 与 `cowork_host_context_key` 传给子代理，子代理首步执行 bind。若缺失或不匹配，子代理应 fail-closed 并报告 `needs_context`。

当前仍存在遗留 `Active task: <task-dir>` 派发入口或描述，可能诱导主会话绕过 runtime context，导致安装到其他项目后按固定 agent 执行时触发 `needs_context`。

## 目标

- 清除会诱导固定 agent 使用 `Active task` 作为正式派发凭据的文档或元数据。
- Codex 固定 agent 的可见描述要表达 runtime-context 要求，避免父会话按旧语义构造 prompt。
- `doctor --subagent-safety` 与测试应能发现这类遗留入口。

## 非目标

- 不改变 runtime-context 协议本身。
- 不新增第三方 CLI 框架或 host primitive。
- 不改变任务归档、提交或 release 流程。

## 验收标准

- `README.md` 不再给出 `message="Active task: <task-dir>\n\n<assignment>"` 固定 agent 派发示例。
- root 与 template 下 `.codex/agents/cowork-*.toml` 的 description 不再描述为从 Active task 自加载上下文。
- `doctor --subagent-safety` 能捕获 README 或 Codex 固定 agent description 中的旧派发标记。
- 相关测试覆盖上述回归点并通过。
