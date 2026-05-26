# 05-26-agent-team-subagent-recursion Spec

## Codex 派发分层

在 Codex 环境中执行 `agent-team` 时，协调器层指令与 worker 层 assignment brief 必须分离：

- 主 agent 必须使用结构化 subagent 调用来派发 worker。
- worker 的初始消息必须只包含 `agent-team/assignments/<assignment-id>.md` 的内容，不得在消息前拼接 `Spawn one ... agent` 之类的协调器指令。
- `agent_type` 必须作为 Codex spawn target 使用。
- `recommended_agent` 只表示 agent-team registry 的匹配结果，不得被当作 worker 初始消息，也不得默认当作 Codex spawn target，除非它本身就是一个真实 Codex custom agent 名称。

## Codex Adapter 元数据

`agent-team prepare <task-dir> --plan <plan-file>` 生成 `adapters/codex.json` 时，必须包含足够的结构化信息，让主 agent 不需要自行拼接混合 dispatch prompt：

- adapter 模式仍为 `coordinator-dispatched`
- 全局默认值至少包括：
  - `spawnAgent: true`
  - `forkTurns: "none"`
  - `promptSource: "assignment-file"`
- 每个 assignment 至少包括：
  - `assignmentId`
  - `agentType`
  - `recommendedAgent`
  - `suggestedTaskName`
  - `promptFile`
  - `contextFile`

## Worker Context 子协议

`agent-team prepare` 必须为每个 assignment 生成一个 worker context 文件，例如：

- `agent-team/assignments/T001-implementer.context.json`

该文件至少包含：

- `mode: "worker"`
- `taskDir`
- `assignment`
- `promptFile`

主 agent 派发给 worker 后，如果 worker 需要 cowork-flow 恢复能力，必须通过：

- `./.cowork-flow/run --context-file <assignment-context.json> resume`

进入 assignment-scoped 子协议，而不是执行普通 `resume` 或 `task start`。

## Assignment Worker Brief

每个 assignment Markdown prompt 必须在开头明确说明：

- 使用自然语言任务标题作为 heading，而不是直接把 assignment id 放在第一行。
- 在开头单独保留 `Assignment ID: ...`，避免丢失状态机追踪锚点。
- 这是已经派发到 worker 的 brief。
- 如果 worker 能看到任何外层“Spawn one ... agent”或“继续派发”的运输文本，必须将其视为协调器层指令并忽略。
- worker 不得重新运行 `start-session` / `resume` / `agent-team-execution` / `subagent-driven-development` 一类协调器工作流。
- 如果 worker 确实需要 cowork-flow 恢复，只能通过 assignment 对应的 `--context-file` scoped command 进入 worker 模式。
- worker 只能执行 assignment 本身，并在缺少关键事实时返回 `NEEDS_CONTEXT`。

## Script-Level Worker Guard

当脚本收到 worker context 时：

- `resume` 必须输出 worker-local 恢复信息，而不是 coordinator 的 resume checklist。
- `task start`、`task finish`、`task archive` 等 task 生命周期命令必须拒绝执行。
- `agent-team next`、`agent-team prepare`、`record-result`、`record-review`、`retry`、`complete` 等 coordinator 命令必须拒绝执行。
- 未带 worker context 的普通命令行为保持不变。

## Skill 文档

根目录与 template 中的 `agent-team-execution` skill 必须明确说明：

- 在 Codex 中优先使用真实 `spawn_agent`、`wait_agent`、`close_agent` 工具，而不是把协调器指令和 worker brief 拼成一段自然语言。
- `spawn_agent` 应显式使用 assignment 的 `agent_type` 和 `fork_turns: none`。
- 当 `codex.json` 提供 `suggestedTaskName` 时，skill 应优先把它传给 child `task_name`，避免宿主首帧只显示原始 assignment id。
- child `message` 必须直接使用 assignment prompt 文件正文，不得在前后附加会让 worker误判自身角色的 dispatch 文案。
- 如果 worker 需要 cowork-flow 恢复，skill 必须引导其使用 assignment 的 `.context.json` scoped command，而不是普通 `resume`。
- 只有在宿主完全不暴露真实 subagent 工具时，才允许退回人工或其他宿主调度。

## 验收标准

- `agent-team prepare` 生成的 `adapters/codex.json` 包含结构化 spawn 元数据。
- `agent-team prepare` 为每个 Codex assignment 生成自然语言风格的 `suggestedTaskName`，避免主 agent 默认使用 `T001-implementer` 这类原始 id 作为 child `task_name`。
- `agent-team prepare` 生成 assignment `.context.json` 文件，且其内容是 repo-relative 的 worker scope 描述。
- assignment prompt 包含“忽略外层 Spawn one ... 运输文本”和“不要重新运行协调器工作流”的明确说明。
- worker-scoped `resume` 输出 assignment-local 恢复信息，并阻止 `task start` / `agent-team next` 这类 coordinator 命令。
- 根目录与 template 中的 `agent-team-execution` skill 同时覆盖 `spawn_agent` / `wait_agent` / `close_agent`、`fork_turns: none`、assignment 文件正文作为 child message，以及 manual fallback 条件。
