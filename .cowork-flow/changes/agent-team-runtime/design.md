# Agent Team Runtime 设计

## 1. 架构定位

Agent Team Runtime 是 cowork-flow 在“执行 plan”阶段的调度层。它不是替代 `task`、`change` 或 `plan`，而是在已有闭环之上补齐多 agent 协作执行所需的结构化工件。

总体边界：

- `change` 继续负责行为规格治理。
- `plan` 继续负责可执行步骤。
- `task` 继续负责任务生命周期和上下文注入。
- `agent-team` 负责把 plan task 转成可并行调度、可审阅、可重试、可恢复的 agent assignments。

## 2. 主 Agent 与子 Agent 职责

主 agent 是调度控制器：

- 读取 plan 与任务上下文。
- 调用 `agent-team prepare` 生成调度图。
- 审核脚本推断的依赖、并行批次和 agent 匹配。
- 调度可并行的子 agent。
- 在子 agent 执行时协调、答疑、补上下文、处理阻塞。
- 集成结果并触发规格审阅和质量审阅。
- 使用 `record-result`、`record-review`、`retry` 回写状态。

子 agent 是受约束执行者：

- 只处理 assignment 明确给出的任务。
- 遵守写入边界，不回滚他人改动。
- 输出修改文件、验证结果、阻塞与风险。
- reviewer agent 只审阅指定范围，不擅自扩大实现。

## 3. 适配器模型

默认适配器是 `codex`，采用“主 agent 调度型”。

原因：

- 当前 Codex 子 agent 能力由主 agent 工具调用，不适合让 Python 脚本直接调起。
- 脚本可以稳定生成 Codex-ready prompt 和状态工件。
- 主 agent 保持最终判断权，避免平台 API 变化破坏模板。

`manual` 适配器作为兜底：

- 生成可复制的 assignment prompt。
- 保留同样的状态、结果和审阅回写格式。
- 适合没有子 agent 工具的环境。

未来可以扩展适配器，但必须保持默认标准库可运行，不引入强制网络依赖。

## 4. 文件结构

项目级配置：

```text
.cowork-flow/agent-team/
├── agents.yaml
├── adapters.yaml
└── policy.yaml
```

任务级运行工件：

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

设计原则：

- 项目级配置可以被项目定制，`sync` 默认保护。
- 任务级工件跟随 task 生命周期，便于恢复和归档。
- assignment、result、review 分离，避免历史被覆盖。

## 5. Plan 解析

解析器只依赖现有 writing-plans Markdown 结构。

核心识别：

- `### Task N: <title>` 生成 plan task。
- `**Files:**` 下的 `Create`、`Modify`、`Test` 形成读写边界。
- checkbox 行形成执行步骤。
- `Run:`、命令代码块和常见验证关键词形成验证命令候选。
- `depends on Task N` 形成显式依赖。

解析器采取保守策略：

- 能确定的写入结构化字段。
- 不确定的写入 risk / warning。
- 完全无法识别 task 时失败。

## 6. 依赖图与并行策略

依赖图以 plan task 为节点，以文件冲突、显式依赖、推断依赖和阶段类型为边。

并行规则：

- 文件写入范围重叠时不得并行。
- 一个 task 的实现、规格审阅、质量审阅必须串行。
- 跨 task 的 reviewer 依赖对应 implementer 完成。
- 集成、全量测试、完成类 task 进入后置批次。
- 主 agent 可以人工调整生成的 `dispatch-plan.yaml`。

## 7. Agent Registry 与评分

默认 registry 包含：

- `implementer`
- `spec-reviewer`
- `quality-reviewer`
- `docs-agent`

项目可通过 `.cowork-flow/agent-team/agents.yaml` 扩展或覆盖。

评分维度：

- 能力标签匹配。
- 文件路径匹配。
- 任务类型匹配。
- 风险限制匹配。
- 默认 Codex agent type 匹配。

输出必须包含分数和理由，避免黑箱调度。

## 8. 状态机

Assignment 状态：

- `pending`
- `ready`
- `running`
- `done`
- `review`
- `blocked`
- `failed`
- `needs-context`
- `needs-coordinator-decision`
- `approved`

状态转移由命令驱动：

- `prepare` 创建 pending/ready。
- `next` 读取 ready。
- `record-result` 写入 done/failed/blocked/needs-context。
- `record-review` 写入 approved/review_rejected。
- `retry` 创建新 attempt。
- `complete` 检查所有终态。

## 9. 重试与历史反馈

每个 assignment 保存 attempts。

重试策略来自 policy：

- `max_attempts`
- `retry_on`
- `escalation`

当失败来自上下文不足，主 agent 应先补上下文再 retry。当失败来自任务过大，主 agent 应拆分任务或调整 plan。当多次失败仍未解决，状态进入 `needs-coordinator-decision`。

`metrics.json` 保存基础历史反馈：

- agent 成功次数。
- 失败次数。
- review 返工次数。
- attempt 数。
- 最近失败原因。

这些统计只作为建议输入，不自动替代主 agent 判断。

## 10. Skill 与流程接入

新增 `agent-team-execution` skill。

该 skill 负责告诉主 agent：

- 什么时候使用 agent team。
- 如何调用 `prepare`、`next`、`record-*`、`retry`、`complete`。
- 如何审查并行安全性。
- 如何调度 Codex 子 agent。
- 如何在子 agent 运行时继续协调和集成。

流程文档接入：

- `.cowork-flow/workflow.md`：执行 plan 阶段加入 agent team 选项。
- `.agent/skills/start/SKILL.md`：Task Workflow 执行阶段引用 agent team。
- `README.md`：说明命令组和默认 Codex 适配器。
- `template/AGENTS.md` 托管块：简短说明执行 plan 时可使用 agent team。

## 11. 测试策略

脚本测试使用临时复制的 `template/` 作为目标仓库，与现有 `change.py` 测试风格一致。

测试覆盖：

- init 幂等。
- prepare 解析标准 plan。
- 文件冲突阻止并行。
- 三段审阅链路串行。
- next 输出 ready assignments。
- record-result / record-review / retry 保留历史。
- complete 对未完成和失败未决严格失败。
- 模板同步保护项目级 agent-team 配置。
- README/workflow/start skill 包含入口说明。
