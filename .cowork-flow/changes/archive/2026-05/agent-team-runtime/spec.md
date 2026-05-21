# Agent Team Runtime 行为规格

## 1. 命令入口

系统必须提供独立命令组：

```bash
./.cowork-flow/run agent-team <command> [args...]
```

至少支持以下命令：

- `init`
- `prepare <task-dir> --plan <plan-file>`
- `status <task-dir>`
- `next <task-dir>`
- `record-result <task-dir> --assignment <id> --status <status> [--file <path>]`
- `record-review <task-dir> --assignment <id> --status <status> [--file <path>]`
- `retry <task-dir> --assignment <id> --reason <reason>`
- `complete <task-dir>`

当命令参数缺失、task 不存在、plan 不存在或上下文未初始化时，命令必须以非 0 状态退出，并输出明确错误。

## 2. 项目级配置

`agent-team init` 必须创建以下默认配置：

```text
.cowork-flow/agent-team/
├── agents.yaml
├── adapters.yaml
└── policy.yaml
```

重复运行 `init` 不得覆盖已有项目配置，除非未来显式提供覆盖参数。

默认配置必须包含：

- 内置基础角色：`implementer`、`spec-reviewer`、`quality-reviewer`、`docs-agent`。
- 默认适配器：`codex`。
- 兜底适配器：`manual`。
- 并行策略、重试策略和审阅策略的默认值。

## 3. 任务级工件

`prepare` 必须在任务目录下生成：

```text
.cowork-flow/tasks/<task>/agent-team/
├── team.yaml
├── dispatch-plan.yaml
├── status.json
├── metrics.json
├── assignments/
├── results/
├── reviews/
├── blockers/
└── adapters/
    └── codex.json
```

这些文件必须足以让主 agent 在上下文恢复后继续执行，不依赖聊天历史。

## 4. Plan 解析

`prepare` 必须解析现有 writing-plans Markdown，不要求新增 plan 格式。

必须识别：

- `### Task N: <title>` 任务标题。
- `**Files:**` 下的 `Create`、`Modify`、`Test` 文件范围。
- checkbox 步骤。
- 代码块或行内文本中的验证命令。
- 显式依赖文字，例如 `depends on Task 2`。

当 plan 格式不完整但仍可生成调度图时，必须在 `dispatch-plan.yaml` 中标记 `needs-human-review` 风险。无法识别任何任务时，`prepare` 必须失败。

## 5. 依赖图与并行批次

`prepare` 必须生成任务依赖图和并行批次。

规则：

- 文件范围重叠的任务默认不能并行。
- 同一个 plan task 的 `implementer`、`spec-reviewer`、`quality-reviewer` 必须严格串行。
- 测试、集成、完成类任务默认进入后置批次。
- 显式依赖优先于推断依赖。
- 主 agent 可以在执行前人工审查和调整生成的 dispatch plan。

## 6. Agent 匹配

系统必须支持“内置角色 + 项目 registry”。

匹配输入包括：

- task 标题。
- 步骤文本。
- 文件路径。
- 验证命令。
- registry 中的能力标签、文件模式、任务类型和风险限制。

输出必须包含：

- 推荐 agent。
- 推荐 Codex agent 类型，例如 `worker`、`explorer`、`default`。
- 匹配分数。
- 匹配理由。
- 风险提示。

脚本只能生成建议，最终调度权属于主 agent。

## 7. Codex 适配器

默认 `codex` 适配器采用主 agent 调度型：

- Python 脚本不直接调用 Codex runtime。
- 脚本生成 Codex-ready assignment prompt、上下文路径、写入边界和回写格式。
- 主 agent 使用 Codex 子 agent 能力执行分派。
- 主 agent 用 `record-result`、`record-review`、`retry` 回写状态。

当宿主环境不能调度 Codex 子 agent 时，主 agent 可以使用 `manual` 适配器产生的提示词和状态记录继续执行。

## 8. 执行、审阅与重试

每个 plan task 默认生成三段链路：

1. `implementer`
2. `spec-reviewer`
3. `quality-reviewer`

`record-result` 和 `record-review` 必须追加 attempt 记录，不得覆盖历史结果。

失败分类至少包含：

- `needs_context`
- `blocked`
- `failed_verification`
- `review_rejected`
- `adapter_failed`

`retry` 必须生成新的 attempt 记录和修订后的 assignment，不得删除旧记录。超过最大尝试次数时，状态必须变为 `needs-coordinator-decision`。

## 9. 状态、统计与完成检查

`status` 必须展示当前批次、ready/running/done/blocked/failed/review 状态摘要。

`next` 必须输出下一批 ready assignments，包括：

- assignment id。
- 推荐 agent。
- Codex agent 类型。
- 上下文文件。
- 写入边界。
- 风险提示。

`metrics.json` 必须记录基础统计：

- assignment 数量。
- attempt 数量。
- 成功、失败、重试和审阅返工次数。
- agent 维度的基础表现数据。

`complete` 必须在以下情况失败：

- 存在未完成 assignment。
- 存在失败未决或阻塞未决。
- 存在规格审阅或质量审阅未通过。
- 存在需要主 agent 决策的状态。

全部链路完成并审阅通过后，`complete` 才能成功。

## 10. 模板与同步

模板必须包含：

- `template/.cowork-flow/scripts/agent_team.py`
- `template/.cowork-flow/agent-team/agents.yaml`
- `template/.cowork-flow/agent-team/adapters.yaml`
- `template/.cowork-flow/agent-team/policy.yaml`
- `template/.agent/skills/agent-team-execution/SKILL.md`

`sync` 默认可以刷新脚本和通用 skill，但必须保护项目级 `.cowork-flow/agent-team/` 配置，避免覆盖项目定制。

## 11. 恢复能力

恢复后，主 agent 必须能通过以下命令重建执行状态：

```bash
./.cowork-flow/run agent-team status <task-dir>
./.cowork-flow/run agent-team next <task-dir>
```

流程文档必须说明执行 plan 时可以选择 agent team，并说明主 agent 在并行执行期间仍负责协调、指导、阻塞处理和结果集成。
