# 修复 agent-team 子 agent 递归派发

## 目标

修复 Codex 环境下 `agent-team` 派发子 agent 时，子 agent 误把自己当成主 agent、重新加载上下文并继续派发下一层子 agent 的循环问题。

## 已确认根因

- 主 agent 当前使用一段混合 prompt 进行调度：前半段是协调器级别的 `Spawn one worker agent ...` 指令，后半段才是 assignment worker brief。
- 当宿主把这段混合 prompt 直接或部分透传给子线程时，子 agent 会先读到“继续派发”语义，从而把自己当成协调器而不是被派发 worker。
- 仅靠 assignment 文件中的“不要再派发”文案不足以稳定压住这种递归，因为调度指令与 worker 指令没有被结构化分层。

## 范围

- 调整 `agent-team` 的 Codex 调度约定，要求主 agent 使用结构化 subagent spawn，而不是把协调器指令和 worker brief 拼成同一段自然语言。
- 为 `prepare` 生成更明确的 Codex adapter 元数据，给出 `agent_type`、`fork_turns`、assignment prompt 来源等结构化派发信息。
- 为 Codex assignment 生成可读的 `suggestedTaskName`，避免宿主 UI 首帧回退成 `T002-implementer` 这类机器 id 风格名称。
- 为每个 assignment 生成正式的 worker context file，并让 worker 通过 `./.cowork-flow/run --context-file <...>` 进入 assignment-scoped cowork-flow 子协议。
- 强化 assignment worker brief，使其明确忽略外层任何“继续派发”运输文本，只执行 assignment 本身。
- 更新根目录与 template 中的 `agent-team-execution` skill 文案。
- 补充针对递归派发风险的回归测试。

## 非目标

- 不改动 assignment 状态机、依赖图和 review 链路。
- 不引入新的外部依赖。
- 不让 Python runtime 直接代替主 agent 调用 Codex subagent 工具。

## 验收标准

- `agent-team prepare` 生成的 Codex adapter 元数据包含结构化 spawn 默认值，明确要求 `fork_turns: none`，并指向 assignment prompt 文件。
- `agent-team prepare` 生成的 Codex assignment 元数据包含 `suggestedTaskName`，且 assignment prompt 标题优先使用自然任务名而不是原始 assignment id。
- `agent-team prepare` 为每个 assignment 生成 `.context.json`，其中包含 `mode=worker`、`taskDir`、`assignment` 和 `promptFile`。
- assignment prompt 明确说明：如果能看到外层 “Spawn one ... agent” 运输文本，必须忽略并仅把 assignment 文件当作 worker brief。
- worker-scoped `resume` 不再回到 coordinator 的 resume checklist，而是只输出 assignment-local 恢复信息。
- 根目录与 template 中的 `agent-team-execution` skill 明确要求在 Codex 中使用 `spawn_agent` / `wait_agent` / `close_agent`，且禁止把协调器 dispatch 文案混入 worker 初始消息。
- 相关 Python unittest 通过。

## 验证方式

- `python3 -m unittest tests.test_agent_team_plan_parser -v`
- `python3 -m unittest tests.test_agent_team_docs -v`
- `python3 -m unittest tests.test_agent_team_runtime -v`
- `python3 -m unittest tests.test_worker_execution_context -v`
