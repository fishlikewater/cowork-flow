# Specification: Clean-room Trellis-like Rewrite

## 许可边界

- 实现必须是 clean-room 重写。
- 可以借鉴 Trellis 的架构思想和公开行为模式。
- 不复制 Trellis 源码、模板正文、脚本实现或 agent 配置文本。
- 保留当前项目目录命名风格：`.cowork-flow/`、`.agent/skills/`、`template/.cowork-flow/`。

## 工作流主线

系统必须使用以下默认主线：

```text
task create -> brainstorm/prd -> curate jsonl -> task start -> cowork-implement -> cowork-check -> update spec -> commit -> archive/session
```

默认主线不得依赖 `agent-team prepare/next/collect/retry/complete`。

## 当前任务状态

- 当前任务必须存储在 `.cowork-flow/.runtime/sessions/<context-key>.json`。
- `context-key` 由明确输入提供，优先支持 `COWORK_FLOW_CONTEXT_ID`、`CODEX_SESSION_ID`、`CODEX_THREAD_ID`。
- 没有 context key 时，`task start`、`task current`、`task finish` 必须失败并给出明确提示。
- 系统不得读取或写入 `.cowork-flow/.current-task`。
- 系统不得在多个 session 文件之间猜测当前任务。
- `task archive` 必须清理所有指向被归档任务的 session pointer。

## Task 文件契约

任务目录仍位于 `.cowork-flow/tasks/<task>/`。

任务上下文必须以文件表达：

- `task.json`：任务状态与元信息
- `prd.md`：需求事实源
- `info.md`：可选技术设计
- `research/*.md`：可选研究产物
- `implement.jsonl`：实现 agent 需要预读的 spec/research
- `check.jsonl`：检查 agent 需要预读的 spec/research
- `debug.jsonl`：调试与复盘上下文，可保留

JSONL 条目必须使用 repo-root 相对路径。

## 子 Agent 契约

系统只定义默认三类子 agent：

- `cowork-research`
- `cowork-implement`
- `cowork-check`

主会话派发子 agent 时，消息第一行必须是：

```text
Active task: .cowork-flow/tasks/<task>
```

子 agent 必须从该路径加载上下文，不依赖父会话历史。

### cowork-research

- 只写当前任务的 `research/*.md`
- 不修改代码、spec、workflow、task 状态或 git
- 输出必须包含写入文件列表和关键结论

### cowork-implement

- 读取 `prd.md`、可选 `info.md`、`implement.jsonl`
- 修改代码与测试
- 不提交、不归档、不派发其他 agent
- 不运行主会话 start/resume 流程

### cowork-check

- 读取 `prd.md`、`check.jsonl`、当前 diff
- 审查实现，可直接自修
- 运行必要验证
- 不提交、不归档、不派发其他 agent

## Agent-team 删除规则

旧 `agent-team` 相关实现如果只服务于通用 assignment/outbox/review-chain 状态机，并且不再被新主线使用，必须删除。

不得为了兼容旧流程保留额外分支、fallback 或双轨文档。

## 验收标准

- 新测试证明 `.current-task` 不再生成。
- 新测试证明无 context key 时 current/start/finish 失败。
- 新测试证明 session pointer 可设置、读取、清理。
- 新测试证明 workflow 默认路径不再推荐 agent-team。
- 新测试证明子 agent 文档要求 `Active task:` 与 leaf executor 边界。
- `npm run test:all` 必须通过，或明确记录无法运行的原因。
