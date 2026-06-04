# Cowork Flow 工作流

## 1. 目标

默认执行模型固定为：

```text
计划 -> 实现 -> 检查 -> 完成
```

核心路径：

1. 计划：建立任务、明确 PRD、整理 `implement.jsonl` / `check.jsonl`。
2. 实现：主会话通过当前宿主适配器派发 `cowork-implement`，先发 `COWORK_DISPATCH_V1` 信封并等待 `COWORK_ACK`。
3. 检查：主会话通过当前宿主适配器派发 `cowork-check`，先发 `COWORK_DISPATCH_V1` 信封并等待 `COWORK_ACK`。
4. 完成：主会话做最终验证、同步规格、提交、归档、记录会话。

`cowork-flow` 只保存项目状态、任务上下文、宿主适配器契约和恢复线索；实际执行由主会话和固定 `cowork-*` 代理完成。宿主工具名只写在 `.cowork-flow/adapters/<host>/adapter.yaml`，不进入流程分支。

## 1.1 状态注入与入口分类

宿主钩子或插件每轮注入当前会话的入口分类和任务状态。状态提示的文本片段定义在 `.cowork-flow/spec/workflow-state-templates.md`，hook 从该文件读取；不再内联到本文件。

入口分类必须先于任务启动、恢复、归档或子代理派发。当入口类型为 `DELEGATED_HARD`、`DELEGATED_SOFT` 或 `UNKNOWN` 时，hook 必须注入 `delegated_subtask` 状态而非 `no_task`，防止子代理被首屏拉偏。

## 1.2 需求澄清与头脑风暴门禁

新需求先判断清晰度。只读问题、单步且目标/范围/验收标准都清楚的小改可以绕过；否则必须先进入 `brainstorming`，在写 PRD、计划或固定代理派发前收束方向。

以下情况触发头脑风暴：

- 目标、用户价值或期望行为不清楚。
- 范围边界、非目标或影响面不清楚。
- 存在多种有效方案或关键取舍尚未决定。
- 涉及 L1/L2 行为变化，或影响架构、接口、数据、权限、发布迁移。
- 验收标准缺失、风险未知，或关键假设需要暴露。

`brainstorming` 输出至少包括：目标、非目标、关键假设、范围边界、推荐方向、被拒方案、验收标准、开放问题/阻塞。只有方向和验收标准清楚后，才进入 PRD、计划或固定代理派发。

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

当前任务是会话级状态。没有 `COWORK_FLOW_CONTEXT_ID`、`CODEX_SESSION_ID`、`CODEX_THREAD_ID`、`OPENCODE_SESSION_ID` 或 `CLAUDE_SESSION_ID` 时，不得猜测当前任务。

## 3. 固定代理

固定代理只执行主会话派发的叶子任务。子代理是执行者，子任务是工作单元。

| 代理 | 读取 | 允许 | 禁止 | 输出 |
| --- | --- | --- | --- | --- |
| `cowork-research` | 任务上下文和调研输入 | 只做调研，只写入 `<task>/research/` | 改代码、改规格、改任务状态、操作 Git | 调研结论和证据 |
| `cowork-implement` | `<task>/prd.md`、`<task>/info.md`、`<task>/implement.jsonl` 和 JSONL 指向的文件 | 按任务范围实现 | 启动其他代理、提交、归档、运行 `task start`、`task finish` 或 `task archive` | 改动文件和验证命令 |
| `cowork-check` | `<task>/prd.md`、`<task>/check.jsonl` 和 `git diff` | 检查行为、测试、规格同步和遗漏；范围内问题直接修复 | 提交、归档、启动其他代理 | 检查结论、修复内容和验证结果 |

## 3.1 固定代理派发入口

固定 `cowork-*` 代理使用宿主适配器契约，由主会话负责派发、等待、验收和取消。宿主专属原语只在 `.cowork-flow/adapters/<host>/adapter.yaml` 中声明；工作流只关心能力与固定协议。

### 3.1.1 兼容入口提示

兼容旧派发时，提示仍可用这一行开头：

```text
Active task: .cowork-flow/tasks/<task>
```

### 3.1.2 派发前置条件

正式派发必须满足：

- `COWORK_ENTRY_CONTRACT_V1` 已完成入口分类。
- 宿主适配器具备 `dispatchSubagent`、`freshChildContext`、`waitChild`、`listChildren` 和 `cancelChild` 所需能力，或按 `fallback.whenRequiredCapabilityMissing` 进入内联/人工兜底。
- 子任务第一屏必须包含 `COWORK_DISPATCH_V1` 或 `COWORK_DELEGATION_V1`。
- 子代理必须是叶子执行者。

### 3.1.3 派发信封

主会话派发信封：

```text
COWORK_DISPATCH_V1
dispatch_id: <unique-id>
task_dir: .cowork-flow/tasks/<task>
agent_type: cowork-implement
role: implement
context_file: <context-file>
ack_token: <ack-token>
COWORK_DISPATCH_END

只返回：COWORK_ACK <dispatch_id> <ack_token>
```

### 3.1.4 ACK 与执行闸门

- 执行前先用适配器等待原语等待 `COWORK_ACK <dispatch_id> <ack_token>`。
- 缺失或不匹配的 `COWORK_ACK` 表示任务尚未成功派发。
- 只有匹配 ACK 后，才通过适配器后续发送原语发送 `EXECUTE <dispatch_id>`；若宿主不支持后续发送，则必须在正式命令或任务提示中包含等价执行闸门。
- 发送 `EXECUTE <dispatch_id>` 时记录 `execute_sent_at[dispatch_id]`。

### 3.1.5 ACK 后宽限期与健康判断

- 计算 `deadline[dispatch_id] = execute_sent_at[dispatch_id] + post_ack_execution_grace_ms`；不得在多个子任务之间使用共享/全局截止时间。
- `EXECUTE <dispatch_id>` 后，子任务加载上下文期间没有回复或没有 `compass` / `status` 文件，不能判定异常。
- 判断执行健康前必须使用 ACK 后执行宽限期。默认值是 `300000` ms，可由适配器相关运行时配置调整。
- 不得因为执行中的子任务尚未产出 `compass` / `status` 文件就取消或关闭它。
- 如果适配器列表原语仍显示子任务运行中，应继续等待 ACK 后执行宽限期，而不是取消它。
- 某个 `dispatch_id` 的 ACK 后执行宽限期到期，只是该子任务的复核点，不是关闭触发器，也不是其他子任务的证据。
- 如果存在 `progress`、`compass` 或 `status` 文件，继续等待，不得只因宽限期到期而关闭。
- 如果子任务报告另一个 `dispatch_id`，关闭该子任务并重新派发目标任务。
- 执行中的子任务只能在错派证据明确、子任务完成或用户取消后关闭。

### 3.1.6 返回验收与收口

- 用适配器等待原语等待子代理返回。
- 用适配器列表原语确认没有遗留运行中的子任务。
- 验收子代理汇报的文件、命令和结果；不只信“已完成”文本。
- 完成或失败后用适配器取消/关闭原语收口子代理。
- 子代理自身是叶子执行者；不得再派发、等待、列出或取消其他代理。

### 3.1.7 通用 worker 边界

- 正式执行只使用 `cowork-research`、`cowork-implement` 或 `cowork-check`。
- 通用 `worker` 派发只视为尽力而为。
- 对 Codex 默认 `worker`、`default`、`explorer`，项目级 `.codex/agents/*.toml` 负责阻止首屏被 bootstrap / start / resume 拉偏；这不改变正式执行仍以固定 `cowork-*` 代理为主线。
- 如果通用 worker 重试一次后仍未 ACK，关闭它且不要执行该任务。
- 没有硬信封的建议型/默认子代理一律视为 `DELEGATED_SOFT`。首句仍应说明这是有边界的委托任务，不是主会话启动请求；这只是自然语言首屏边界，不是正式执行证据。建议型输出不能满足正式实现或检查完成条件。

## 3.2 并行会话

并行执行采用干净隔离的并行会话模型。并行只是执行策略，不改变固定代理叶子边界。

### 3.2.1 并行决策

- 用户无需在需求输入时声明是否并行；计划阶段由主会话评估并行可行性。
- 开发计划必须明确执行策略：串行执行，或列出可并行的低冲突切片。
- 同一文件、同一行为链、依赖未合并或验收标准不清的工作不得并行，改为串行。

### 3.2.2 隔离方式

- 多个独立任务优先拆成多个 cowork-flow 会话。
- 只要存在写入冲突风险，就用独立 `git worktree` 隔离。

### 3.2.3 单任务内切片

- 单个任务内只允许低冲突切片并行。
- 每个切片必须写清文件归属、依赖关系、预期产物和验证命令。

### 3.2.4 协调与验收

- 主会话是唯一协调者：派发所有子代理后逐个等待，核对子代理汇报的文件、命令和产物，再用适配器列表/取消原语收口。
- 多个实现切片合并后必须再执行最终集成验证；不能把各子代理的局部通过当成整体通过。
- 固定 `cowork-*` 代理仍是叶子执行者；并行不允许子代理再派发代理，也不引入旧集中式状态机。

## 4. 任务分级

### L0: 无外部行为变化

适用：文档、格式、小范围重构、注释、脚本整理、测试补充，且不改变用户可观察行为。

流程：读取规则 -> 创建或选择任务 -> 写 PRD -> 初始化上下文 -> 实现 -> 验证 -> 记录会话。

### L1: 局部行为变化

适用：单模块功能、局部接口行为、局部数据处理逻辑，边界清晰。

流程：`change` -> `brainstorming` -> `spec` -> `plan` -> `task context` -> 实现 -> 检查 -> 完成。

### L2: 跨层或重要行为变化

适用：API / DB / 消息 / 权限 / 文件格式 / 架构边界 / 发布迁移 / 安全策略等变化。

流程：`change` -> `brainstorming` -> `design.md` -> `spec` -> `plan` -> `task context` -> 实现 -> 检查 -> 完成 -> 跨层复核。

## 5. 计划阶段

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

## 6. 实现阶段

默认通过宿主适配器派发 `cowork-implement`。派发必须使用新鲜子上下文，优先使用 `COWORK_DISPATCH_V1` 信封；兼容旧消息时第一行：

```text
Active task: .cowork-flow/tasks/<task>
```

派发内容应包含当前计划步骤、范围边界和期望验证命令。

如果用户明确要求主会话内联执行，或当前任务正在修改子代理/运行时行为，可以不派发 `cowork-implement`，但必须说明原因，并仍按计划与测试循环推进。

涉及行为变化时，先写失败测试，再实现，再验证变绿。

## 7. 检查阶段

默认通过宿主适配器派发 `cowork-check`。派发必须使用新鲜子上下文，优先使用 `COWORK_DISPATCH_V1` 信封；兼容旧消息时第一行：

```text
Active task: .cowork-flow/tasks/<task>
```

检查内容：

- PRD 验收标准是否满足。
- `git diff` 是否只包含预期范围。
- 测试是否覆盖关键行为。
- `.cowork-flow/spec/` 是否需要更新。
- 计划勾选项和执行状态是否真实。

如果用户明确要求主会话内联检查，可以不派发 `cowork-check`，但必须执行等价的 diff、测试、规格同步检查。

## 8. 完成阶段

完成前必须确认：

- 当前会话存在任务，或明确说明本次是无任务只读工作。
- `cowork-check` 或等价最终检查已执行。
- 所有声明通过的验证都有命令输出依据。
- 规格已更新，或明确判断无需更新。
- 计划状态、任务状态、`change` 元数据不冲突。
- 提交在归档和会话记录之前完成。
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
3. 不批量读取所有规格、计划、任务或工作区日志。
4. 不存在当前会话任务时，先创建或启动任务。

## 10. 禁止事项

- 不在没有任务上下文时直接修改文件。
- 不在没有失败测试时实现行为变化。
- 不维护第二套执行状态。
- 不把口头状态当成可靠状态。
- 不把验证未运行说成通过。
- 不把旧运行模型作为兜底。
