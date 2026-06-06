# Cowork Flow 工作流

## 1. 目标

默认执行模型固定为：

```text
changes -> brainstorming -> read spec -> plan -> tasks -> implement -> check -> complete
```

核心路径：

1. changes: 通过用户需求,构建原始需求文件
2. brainstorming：对changes需求做头脑风暴,确定目标、范围、验收标准、范围边界、被拒方案、实现方案、检查方案。
3. read spec: 读取项目规范
4. plan：构建开发计划。
5. tasks：根据plan拆分具体执行任务、明确 PRD、整理 `implement.jsonl` / `check.jsonl`。
6. implement：主会话通过当前宿主适配器派发 `cowork-implement`，按 `.cowork-flow/spec/subagent-dispatch.md` 执行固定代理派发协议。
7. check：主会话通过当前宿主适配器派发 `cowork-check`，按 `.cowork-flow/spec/subagent-dispatch.md` 执行固定代理派发协议。
8. complete：主会话做最终验证、同步规格、归档、记录会话、提交。

`cowork-flow` 只保存项目状态、任务上下文、宿主适配器契约和恢复线索；实际执行由主会话和固定 `cowork-*` 代理完成。宿主工具名只写在 `.cowork-flow/adapters/<host>/adapter.yaml`，不进入流程分支。

`task next` 是主会话的阶段导航器。进入任务阶段、恢复会话、派发实现、进入检查、完成收口前，先运行 `./.cowork-flow/run task next` 或 `.\.cowork-flow\run.cmd task next`，用当前任务和 `task.json.status` 决定下一步。该命令只读，不推进状态。

## 1.1 状态注入与入口分类

1. 宿主钩子或插件每轮注入当前会话的入口分类和任务状态。状态提示的文本片段定义在 `.cowork-flow/spec/workflow-state-templates.md`，hook 从该文件读取；不再内联到本文件。
2. runtime context 绑定先于入口分类。hook/plugin 先解析 `cowork_runtime_context_id`，绑定成功或 fail-closed 时注入 `delegated_subtask`。
3. 入口分类只服务主会话导航，不能用 prompt 形状推断正式子代理身份。`UNKNOWN` 不能冒充委托子任务；保持当前任务/no-task 状态可见，并在突变工作流前澄清。

## 1.2 需求澄清与头脑风暴门禁

1. 新需求先判断清晰度。只读问题、单步且目标/范围/验收标准都清楚的小改可以绕过；否则必须先进入 `brainstorming`，在写 PRD、计划或固定代理派发前收束方向。
2. 以下情况触发头脑风暴：
    - 目标、用户价值或期望行为不清楚。
    - 范围边界、非目标或影响面不清楚。
    - 存在多种有效方案或关键取舍尚未决定。
    - 涉及 L1/L2 行为变化，或影响架构、接口、数据、权限、发布迁移。
    - 验收标准缺失、风险未知，或关键假设需要暴露。

3. `brainstorming` 输出至少包括：目标、非目标、关键假设、范围边界、推荐方向、被拒方案、验收标准、开放问题/阻塞。只有方向和验收标准清楚后，才进入 PRD、计划或固定代理派发。

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
| 项目上下文摘要 | `.cowork-flow/project-context.md` |
| 会话记录 | `.cowork-flow/workspace/<developer>/journal-*.md` |

> 当前任务是会话级状态。没有 `COWORK_FLOW_CONTEXT_ID`、`CODEX_SESSION_ID`、`CODEX_THREAD_ID`、`OPENCODE_SESSION_ID` 或 `CLAUDE_SESSION_ID` 时，不得猜测当前任务。

任务阶段状态由生命周期命令维护：

| 阶段 | 命令 | `task.json.status` |
| --- | --- | --- |
| 计划 | `task create` | `planning` |
| 执行 | `task start <task-dir>` | `in_progress` |
| 检查 | `task review [task-dir]` | `review` |
| 完成 | `task complete [task-dir]` | `completed` |
| 归档 | `task archive <task-name>` | 归档副本保持 `completed` |

`task finish` 只清理当前会话任务指针，不改变 `task.json.status`。

## 3. 固定代理

固定代理只执行主会话派发的叶子任务。子代理是执行者，子任务是工作单元。

| 代理 | 读取 | 允许 | 禁止 | 输出 |
| --- | --- | --- | --- | --- |
| `cowork-research` | 任务上下文和调研输入 | 只做调研，只写入 `<task>/research/` | 改代码、改规格、改任务状态、操作 Git | 调研结论和证据 |
| `cowork-implement` | `<task>/prd.md`、`<task>/info.md`、`<task>/implement.jsonl` 和 JSONL 指向的文件 | 按任务范围实现 | 启动其他代理、提交、归档、运行 `task start`、`task finish` 或 `task archive` | 改动文件和验证命令 |
| `cowork-check` | `<task>/prd.md`、`<task>/check.jsonl` 和 `git diff` | 检查行为、测试、规格同步和遗漏；范围内问题直接修复 | 提交、归档、启动其他代理 | 检查结论、修复内容和验证结果 |

## 3.1 固定代理派发入口

固定 `cowork-*` 代理使用宿主适配器契约，由主会话负责派发、等待、验收和取消。宿主专属原语只在 `.cowork-flow/adapters/<host>/adapter.yaml` 中声明；工作流只关心阶段职责、协调边界和验收责任。

正式派发协议见 `.cowork-flow/spec/subagent-dispatch.md`。该协议定义 runtime context 创建、传输、绑定、等待、返回验收、关闭清理和通用 worker 边界。

- 主会话必须使用新鲜子上下文派发固定代理。
- 主会话通过适配器等待原语、适配器列表原语和适配器取消/关闭原语完成收口。
- 固定 `cowork-*` 代理是叶子执行者；不得再派发、等待、列出或取消其他代理。
- 通用 `worker`、`default` 或 `explorer` 只能作为 advisory work，不能满足正式实现或检查完成条件。

## 3.2 手动 Party Mode

Party Mode 是用户手动触发的 advisory roundtable。主会话可通过当前宿主适配器创建 fresh child contexts，收集真实讨论子代理的证据、分歧、风险和可测验收信号，再由主会话综合结论。

Party Mode 不能推进任务状态，不能满足正式实现或检查完成条件，也不能替代 `cowork-implement` 或 `cowork-check`。轮次上限、继续/停止条件、输出 schema 和可配置默认值由 party-mode skill 定义；正式子代理协议仍以 `.cowork-flow/spec/subagent-dispatch.md` 为准。

## 3.3 并行会话

并行执行采用干净隔离的并行会话模型。并行只是执行策略，不改变固定代理叶子边界。

### 3.3.1 并行决策

- 用户无需在需求输入时声明是否并行；计划阶段由主会话评估并行可行性。
- 开发计划必须明确执行策略：串行执行，或列出可并行的低冲突切片。
- 同一文件、同一行为链、依赖未合并或验收标准不清的工作不得并行，改为串行。

### 3.3.2 隔离方式

- 多个独立任务优先拆成多个 cowork-flow 会话。
- 只要存在写入冲突风险，就用独立 `git worktree` 隔离。

### 3.3.3 单任务内切片

- 单个任务内只允许低冲突切片并行。
- 每个切片必须写清文件归属、依赖关系、预期产物和验证命令。

### 3.3.4 协调与验收

- 主会话是唯一协调者：派发所有子代理后逐个等待，核对子代理汇报的文件、命令和产物，再用适配器列表/取消原语收口。
- 多个实现切片合并后必须再执行最终集成验证；不能把各子代理的局部通过当成整体通过。
- 固定 `cowork-*` 代理仍是叶子执行者；并行不允许子代理再派发代理，也不引入旧集中式状态机。

## 4. 任务分级

### L0: 无外部行为变化

适用：文档、格式、小范围重构、注释、脚本整理、测试补充，且不改变用户可观察行为。
流程：`brainstorming` -> `read spec` -> `implement` -> `check` -> `complete`

### L1: 局部行为变化

适用：单模块功能、局部接口行为、局部数据处理逻辑，边界清晰。
流程： `changes` -> `brainstorming` -> `read spec` -> `plan` -> `tasks` -> `implement` -> `check` -> `complete` -> `archive` -> `add session`

### L2: 跨层或重要行为变化

适用：API / DB / 消息 / 权限 / 文件格式 / 架构边界 / 发布迁移 / 安全策略等变化。
流程：`changes` -> `brainstorming` -> `read spec` -> `plan` -> `tasks` -> `implement` -> `cross layer check` -> `complete` -> `archive` -> `add session`。

L2 任务在 `task start` 前必须通过 readiness gate；同一 blocker 列表会在
`task next` 中展示。缺少 proposal/spec/design、计划、任务链接、关键假设、
范围边界、验收标准或验证命令时，不得启动实现或正式派发固定代理。

## 5. 计划阶段

1. 对 L1/L2 创建 changes；L2 必须有 `design.md`。
2. 对changes需求做头脑风暴
3. 写开发计划 `.cowork-flow/plans/YYYY-MM-DD-<slug>.md`，每步带验证命令。
4. 读取 `AGENTS.md`、本文件、相关 `.cowork-flow/spec/` 索引。
5. 创建或确认任务：
    ```bash
    ./.cowork-flow/run task create "<title>" --slug <task-name>
    ```
6. 对创建的每项任务写 `prd.md`，至少包含目标、范围、验收标准、相关文件、验证方式。
7. 初始化上下文：
    ```bash
    ./.cowork-flow/run task init-context <task-dir> <type>
    ./.cowork-flow/run task add-context <task-dir> implement <path> "<reason>"
    ./.cowork-flow/run task add-context <task-dir> check <path> "<reason>"
    ```
8. 运行导航器确认准备状态：
    ```bash
    ./.cowork-flow/run task next <task-dir>
    ```
9. 启动当前会话任务；该命令会把 `task.json.status` 推进到 `in_progress`：
    ```bash
    ./.cowork-flow/run task start <task-dir>
    ```
   Windows PowerShell 使用：
    ```powershell
    .\.cowork-flow\run.cmd task start <task-dir>
    ```

## 6. 实现阶段

1. 先运行 `task next` 确认当前状态和下一步命令。
2. 默认通过宿主适配器派发 `cowork-implement`。派发必须使用新鲜子上下文，并遵守 `.cowork-flow/spec/subagent-dispatch.md`。
3. 派发内容应包含当前计划步骤、范围边界和期望验证命令。
4. 如果用户明确要求主会话内联执行，或当前任务正在修改子代理/运行时行为，可以不派发 `cowork-implement`，但必须说明原因，并仍按计划与测试循环推进。
5. 涉及行为变化时，先写失败测试，再实现，再验证变绿。
6. 实现完成并通过本阶段验证后运行 `./.cowork-flow/run task review [task-dir]`，把任务推进到检查阶段。

## 7. 检查阶段

1. 先运行 `task next` 确认任务处于 `review` / `checking` 检查阶段。
2. 默认通过宿主适配器派发 `cowork-check`。派发必须使用新鲜子上下文，并遵守 `.cowork-flow/spec/subagent-dispatch.md`。
3. 检查内容：
    - PRD 验收标准是否满足。
    - `git diff` 是否只包含预期范围。
    - 测试是否覆盖关键行为。
    - `.cowork-flow/spec/` 是否需要更新。
    - 计划勾选项和执行状态是否真实。
4. 如果用户明确要求主会话内联检查，可以不派发 `cowork-check`，但必须执行等价的 diff、测试、规格同步检查。
5. 检查通过后运行 `./.cowork-flow/run task complete [task-dir]`，把任务推进到完成阶段。

## 8. 完成阶段

1. 完成前必须确认：
    - 当前会话存在任务，或明确说明本次是无任务只读工作。
    - `cowork-check` 或等价最终检查已执行。
    - 所有声明通过的验证都有命令输出依据。
    - 规格已更新，或明确判断无需更新。
    - 计划状态、任务状态、`change` 元数据不冲突。
    - 先归档，再记录会话，然后提交。
    - 不纳入无关脏改。

2. 顺序：
    ```bash
    ./.cowork-flow/run task next
    git status --short
    git diff --check
    npm run test:all
    ./.cowork-flow/run task archive <task-name>
    ./.cowork-flow/run add-session --title "<title>" --commit "-" --summary "<summary>"
    git status --short
    git add <expected files>
    git commit -m "<message>"
    ```
   `task archive <task-name>` 会归档 task，并自动归档 `change.yaml.task`
   指向该 task 的 active change；无法通过 `change validate` 的 change 不会被自动归档。

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
