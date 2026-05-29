# Cowork Flow 工作流

## 1. 目标

默认执行模型固定为：

```text
Plan -> Implement -> Check -> Finish
```

核心路径：

1. Plan: 建立任务、明确 PRD、整理 `implement.jsonl` / `check.jsonl`。
2. Implement: 主会话用 `spawn_agent` 派发 `cowork-implement`，`fork_turns="none"`，首行必须是 `Active task: <task-dir>`。
3. Check: 主会话用 `spawn_agent` 派发 `cowork-check`，`fork_turns="none"`，首行必须是 `Active task: <task-dir>`。
4. Finish: 主会话做最终验证、同步规格、提交、归档、记录 session。

`cowork-flow` 只保存项目状态、任务上下文和恢复线索；实际执行由主会话和固定 `cowork-*` agent 完成。

## 1.1 Hook 注入状态

`.codex/hooks/inject-workflow-state.py` 每轮读取当前 session task，并把下面的 `[workflow-state:*]` 片段注入 Codex 上下文。`workflow.md` 是状态提示的唯一来源；修改流程时必须同步这些片段。

[workflow-state:no_task]
No active task for this session. For read-only Q&A, answer directly. For implementation, refactor, behavior change, or multi-step work, create or start a task first, then continue through Plan -> Implement -> Check -> Finish.
[/workflow-state:no_task]

[workflow-state:planning]
The active task is in planning. Finish prd.md, curate implement.jsonl and check.jsonl with spec/research files, then run task start before dispatching cowork-implement.
[/workflow-state:planning]

[workflow-state:in_progress]
The active task is in progress. Main session dispatches cowork-implement work according to the plan, then cowork-check after integration. Every spawn_agent call uses fork_turns="none" and a first line of Active task: <task-dir>. Main session waits, verifies child output, lists agents, and closes children.
[/workflow-state:in_progress]

[workflow-state:completed]
The active task is completed. Main session should verify the final diff, commit intended files, archive the task, and record the session. Do not dispatch new implementation work against this completed task.
[/workflow-state:completed]

## 2. 状态文件

| 状态 | 文件 |
| --- | --- |
| 开发者身份 | `.cowork-flow/.developer` |
| 当前会话任务 | `.cowork-flow/.runtime/sessions/<context-key>.json` |
| 任务目标 | `.cowork-flow/tasks/<task>/prd.md` |
| 实现上下文 | `.cowork-flow/tasks/<task>/implement.jsonl` |
| 检查上下文 | `.cowork-flow/tasks/<task>/check.jsonl` |
| 调试上下文 | `.cowork-flow/tasks/<task>/debug.jsonl` |
| 行为变更 | `.cowork-flow/changes/<slug>/` |
| 实施计划 | `.cowork-flow/plans/*.md` |
| 项目规格 | `.cowork-flow/spec/` |
| 会话记录 | `.cowork-flow/workspace/<developer>/journal-*.md` |

当前任务是 session-scoped。没有 `COWORK_FLOW_CONTEXT_ID`、`CODEX_SESSION_ID` 或 `CODEX_THREAD_ID` 时，不得猜测当前任务。

## 3. Agent

### cowork-research

- 只做调研。
- 只写入 `<task>/research/`。
- 不改代码、不改规格、不改任务状态、不操作 git。

### cowork-implement

- 读取 `<task>/prd.md`、`<task>/info.md`、`<task>/implement.jsonl` 和 JSONL 指向的文件。
- 按任务范围实现。
- 不启动其他 agent，不提交，不归档，不运行 task start/finish/archive。
- 汇报改动文件和验证命令。

### cowork-check

- 读取 `<task>/prd.md`、`<task>/check.jsonl` 和 `git diff`。
- 检查行为、测试、规格同步和遗漏。
- 范围内问题直接修复。
- 不提交、不归档、不启动其他 agent。

每次派发提示必须以这一行开头：

```text
Active task: .cowork-flow/tasks/<task>
```

## 3.1 Agent 派发入口

固定 `cowork-*` agent 使用 Codex 原生 subagent 工具，由主会话负责派发、等待、验收和关闭。派发必须用 `fork_turns="none"`，避免子线程继承主会话历史。

主会话派发约定：

```python
spawn_agent(
    agent_type="cowork-implement",
    fork_turns="none",
    message="Active task: .cowork-flow/tasks/<task>\n\n<assignment>",
)
```

等待与验收约定：

- 用 `wait_agent` 等待子 agent 返回。
- 用 `list_agents` 确认没有遗留 running child。
- 验收子 agent 汇报的文件、命令和结果；不只信“已完成”文本。
- 完成或失败后用 `close_agent` 关闭子 agent。
- 子 agent 自身是 leaf executor；不得再调用 `spawn_agent`、`wait_agent`、`list_agents`、`close_agent`。

## 3.2 parallel sessions

并行执行采用 clean-room 的 parallel sessions 模型：

- 多个独立任务优先拆成多个 Codex sessions；只要存在写入冲突风险，就用独立 `git worktree` 隔离。
- 单个 task 内只允许低冲突的 low-conflict slices 并行；每个 slice 必须写清 file ownership、dependencies、expected outputs 和验证命令。
- 同一文件、同一行为链、依赖未合并或验收标准不清的工作不得并行，改为串行。
- 主会话是唯一协调者：派发所有子 agent 后逐个 `wait_agent`，核对子 agent 汇报的文件、命令和产物，再 `list_agents` / `close_agent` 收口。
- 多个实现 slice 合并后必须再执行 final integrated verification；不能把各子 agent 的局部通过当成整体通过。
- 固定 `cowork-*` agent 仍是 leaf executor；并行不允许子 agent 再派发 agent，也不引入旧集中式状态机。

## 4. 任务分级

### L0: 无外部行为变化

适用：文档、格式、小范围重构、注释、脚本整理、测试补充，且不改变用户可观察行为。

流程：读取规则 -> 创建或选择任务 -> 写 PRD -> 初始化上下文 -> 实现 -> 验证 -> 记录 session。

### L1: 局部行为变化

适用：单模块功能、局部接口行为、局部数据处理逻辑，边界清晰。

流程：change -> brainstorming -> spec -> plan -> task context -> Implement -> Check -> Finish。

### L2: 跨层或重要行为变化

适用：API / DB / 消息 / 权限 / 文件格式 / 架构边界 / 发布迁移 / 安全策略等变化。

流程：change -> brainstorming -> design.md -> spec -> plan -> task context -> Implement -> Check -> Finish -> cross-layer review。

## 5. Plan 阶段

1. 读取 `AGENTS.md`、本文件、相关 `.cowork-flow/spec/` 索引。
2. 创建或确认任务：

```bash
./.cowork-flow/run task create "<title>" --slug <task-name>
```

3. 写 `prd.md`，至少包含目标、范围、验收标准、相关文件、验证方式。
4. 初始化上下文：

```bash
./.cowork-flow/run task init-context <task-dir> <type>
./.cowork-flow/run task add-context <task-dir> implement <path> "<reason>"
./.cowork-flow/run task add-context <task-dir> check <path> "<reason>"
```

5. 对 L1/L2 创建 change；L2 必须有 `design.md`。
6. 写 `.cowork-flow/plans/YYYY-MM-DD-<slug>.md`，每步带验证命令。
7. 启动当前会话任务：

```bash
./.cowork-flow/run task start <task-dir>
```

Windows PowerShell 使用：

```powershell
.\.cowork-flow\run.cmd task start <task-dir>
```

## 6. Implement 阶段

默认派发 `cowork-implement`。派发调用必须设置 `fork_turns="none"`，消息第一行：

```text
Active task: .cowork-flow/tasks/<task>
```

派发内容应包含当前计划步骤、范围边界和期望验证命令。

如果用户明确要求主会话 inline 执行，或当前任务正在修改 subagent/runtime 行为，可以不派发 `cowork-implement`，但必须说明原因，并仍按计划与测试循环推进。

涉及行为变化时，先写失败测试，再实现，再验证变绿。

## 7. Check 阶段

默认派发 `cowork-check`。派发调用必须设置 `fork_turns="none"`，消息第一行：

```text
Active task: .cowork-flow/tasks/<task>
```

检查内容：

- PRD 验收标准是否满足。
- `git diff` 是否只包含预期范围。
- 测试是否覆盖关键行为。
- `.cowork-flow/spec/` 是否需要更新。
- plan checkbox 和执行状态是否真实。

如果用户明确要求主会话 inline 检查，可以不派发 `cowork-check`，但必须执行等价的 diff、测试、规格同步检查。

## 8. Finish 阶段

完成前必须确认：

- 当前 session 存在任务，或明确说明本次是无任务只读工作。
- `cowork-check` 或等价最终检查已执行。
- 所有声明通过的验证都有命令输出依据。
- 规格已更新，或明确判断无需更新。
- 计划状态、任务状态、change metadata 不冲突。
- 提交在归档和 session 记录之前完成。
- 不纳入无关脏改。

推荐顺序：

```bash
git status --short
git diff --check
npm run test:all
git add <expected files>
git commit -m "<message>"
./.cowork-flow/run task archive <task-name>
./.cowork-flow/run add-session --title "<title>" --commit "<commit>" --summary "<summary>"
```

## 9. 恢复规则

恢复时只读取最小上下文：

1. 运行 `./.cowork-flow/run resume`。
2. 按 `RESUME CHECKLIST` 读取当前任务 PRD、计划状态和 JSONL 指向文件。
3. 不批量读取所有 spec、所有 plans、所有 tasks 或 workspace journal。
4. 不存在当前 session task 时，先创建或启动任务。

## 10. 禁止事项

- 不在没有任务上下文时直接修改文件。
- 不在没有失败测试时实现行为变化。
- 不维护第二套执行状态。
- 不把口头状态当成可靠状态。
- 不把验证未运行说成通过。
- 不把旧运行模型作为 fallback。
