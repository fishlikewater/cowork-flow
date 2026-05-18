# 模板收敛设计：`.agent` 与 `.flow`

## 背景

当前 cowork-flow 模板应用到目标项目后，会在项目根目录生成多组流程目录和入口文件：

- `AGENTS.md`
- `.agents/`
- `.trellis/`
- `docs/superpowers/`
- `openspec/`

这些目录分别承载 Agent 技能、任务状态、项目规范、计划文档和行为变更规格。职责本身有价值，但目录分布偏散，目标项目接入后根目录噪音较高，也容易让使用者误以为需要同时理解多套流程系统。

本次设计目标是让模板更收敛、更内聚：模板应用到具体项目后，根目录只保留 `AGENTS.md`、`.agent/` 和 `.flow/` 三个协作入口，同时保持当前工作流能力不降级。

## 目标

1. 保留当前 L0 / L1 / L2 工作流分级。
2. 保留“规格先行、计划后编码、验证后完成、会话记录归档”的闭环。
3. 保留 Agent skills 的可复用能力，但移动到 `.agent/skills/`。
4. 用自研 Python 脚本替代外部 OpenSpec 目录和命令依赖。
5. 避免 `changes`、`plans`、`tasks` 三类状态重复维护。
6. 更新模板文档、skills 和脚本中的路径引用，使新结构成为唯一推荐结构。

## 非目标

1. 不改变当前工作流的原则和门禁语义。
2. 不引入业务代码脚手架。
3. 不为具体技术栈预设 lint、build、test 命令。
4. 不继续依赖根目录 `openspec/` 或外部 `openspec` CLI。

## 目标目录结构

模板应用到目标项目后，根目录结构为：

```text
.
├── AGENTS.md
├── .agent/
└── .flow/
```

`AGENTS.md` 仍放在根目录，作为主流 Agent 工具默认识别的项目协作入口。它不再指向 `.trellis/`，而是指向 `.flow/` 和 `.agent/`。

`.agent/` 只承载 Agent 能力：

```text
.agent/
└── skills/
```

`.flow/` 承载全部流程状态和流程工具：

```text
.flow/
├── config.yaml
├── workflow.md
├── scripts/
├── spec/
├── changes/
├── plans/
├── tasks/
└── workspace/
```

## 职责边界

### `AGENTS.md`

项目级协作约定入口，继续承载：

- 项目定制位
- 编码前思考原则
- 简单优先、外科手术式改动、先读后写
- 测试验证意图
- 与 `.flow/`、`.agent/` 的入口说明

### `.agent/skills/`

承载可复用技能，不保存项目运行状态。

原 `.agents/skills/` 迁移到 `.agent/skills/`。技能内容中的路径引用统一更新为新结构，例如：

- `.agents/skills/...` -> `.agent/skills/...`
- `.trellis/workflow.md` -> `.flow/workflow.md`
- `.trellis/config.yaml` -> `.flow/config.yaml`
- `.trellis/spec/` -> `.flow/spec/`
- `docs/superpowers/plans/` -> `.flow/plans/`

### `.flow/spec/`

长期项目规范目录，承接原 `.trellis/spec/`。

它回答“这个项目长期应该怎么写”，例如后端目录规范、前端组件规范、跨层检查指南等。

### `.flow/changes/`

行为变更规格目录，替代原 `openspec/changes/`。

它回答“这次为什么改、外部行为改成什么、验收标准是什么”。每个变更目录结构为：

```text
.flow/changes/<slug>/
├── change.yaml
├── proposal.md
├── design.md
└── specs/
    └── <area>/spec.md
```

`design.md` 用于复杂或跨层变更。简单 L1 变更可以保留空文件模板，或由校验脚本允许缺省。

`.flow/changes/` 不再包含 `tasks.md`，避免和 `.flow/tasks/`、`.flow/plans/` 形成三份任务清单。

### `.flow/plans/`

实现计划目录，承接原 `docs/superpowers/plans/`。

它回答“怎么改、步骤是什么、每步如何验证”。计划可以引用某个 change slug，也可以服务于 L0 文档、测试、重构任务。

### `.flow/tasks/`

任务运行状态目录，承接原 `.trellis/tasks/`。

它回答“当前谁在做、任务上下文是什么、任务是否完成或归档”。任务上下文可以引用：

- `.flow/changes/<slug>/proposal.md`
- `.flow/changes/<slug>/specs/.../spec.md`
- `.flow/changes/<slug>/design.md`
- `.flow/plans/<date>-<slug>.md`
- `.flow/spec/...`

### `.flow/workspace/`

开发者工作区，承接原 `.trellis/workspace/`，保存 journal、session 和开发者索引。

## 自研 Change 脚本

新增 `.flow/scripts/change.py` 替代 OpenSpec CLI 的核心能力。

推荐命令：

```bash
python3 ./.flow/scripts/change.py create <slug>
python3 ./.flow/scripts/change.py validate <slug>
python3 ./.flow/scripts/change.py archive <slug>
python3 ./.flow/scripts/change.py list
```

### `create`

创建 `.flow/changes/<slug>/`，生成：

- `change.yaml`
- `proposal.md`
- `design.md`
- `specs/.gitkeep`

`change.yaml` 至少包含：

```yaml
slug: <slug>
status: draft
level: L1
created_at: <ISO-8601 timestamp>
plan: null
task: null
```

### `validate`

校验单个 change 是否结构完整：

- `change.yaml` 存在且 slug 匹配目录名。
- `proposal.md` 存在且非空。
- 至少存在一个 `specs/**/spec.md`，或明确标记为 documentation-only。
- L2 变更必须有非空 `design.md`。
- 如果 `change.yaml` 声明了 `plan` 或 `task`，对应文件或目录必须存在。

### `archive`

将 `.flow/changes/<slug>/` 移动到：

```text
.flow/changes/archive/YYYY-MM/<slug>/
```

归档前必须通过 `validate`。脚本只移动 change 规格，不归档 `.flow/tasks/`；任务归档继续由 task 脚本负责。

### `list`

列出 active 与 archived change，显示 slug、level、status、关联 plan、关联 task。

## 工作流映射

### L0：无外部行为变化

```text
.flow/tasks/ -> 读取 .flow/spec/ -> 简短计划 -> 实现 -> 验证 -> .flow/workspace/ session
```

L0 默认不需要 `.flow/changes/`。

### L1：局部行为变化

```text
.flow/changes/ -> brainstorming -> .flow/plans/ -> .flow/tasks/ -> 实现 -> 验证 -> 归档与 session
```

### L2：跨层或重要行为变化

```text
.flow/changes/ -> design.md -> .flow/plans/ -> .flow/tasks/ -> 多视角审阅 -> 验证 -> 归档与 session
```

## 避免重复的规则

1. `.flow/changes/` 只记录行为契约，不记录实现 checklist。
2. `.flow/plans/` 记录实现步骤和步骤级验证。
3. `.flow/tasks/` 记录运行状态、上下文绑定和归档状态。
4. `.flow/spec/` 记录长期规范，不记录一次性任务状态。
5. `.flow/workspace/` 记录 session，不作为计划或需求来源。

## 迁移范围

需要更新的模板内容包括：

- README 中的结构、快速开始和命令示例。
- 根目录 `template/AGENTS.md` 中的流程入口说明。
- `template/.agents/` 重命名为 `template/.agent/`。
- `template/.trellis/` 重命名为 `template/.flow/`。
- `template/docs/superpowers/plans/` 迁移为 `template/.flow/plans/`。
- `template/openspec/changes/` 迁移为 `template/.flow/changes/`。
- `template/openspec/config.yaml` 的有用配置并入 `template/.flow/config.yaml`。
- Python 脚本中的常量、提示文案、git add 路径和安全路径判断。
- skills 中所有旧路径引用。

## 验证策略

实现阶段应优先补测试或脚本级验证：

1. 验证 `.flow/scripts/task.py` 能创建、启动、归档任务。
2. 验证 `.flow/scripts/change.py create/validate/archive/list` 的成功路径和失败路径。
3. 验证 `get_context.py`、`init_developer.py`、`add_session.py` 使用 `.flow/`。
4. 验证 README 中的命令可以在模板结构下成立。
5. 使用全文搜索确认旧路径引用已清理或仅作为迁移说明存在。

## 风险与应对

### Agent 工具默认只识别根目录 `AGENTS.md`

应对：保留根目录 `AGENTS.md`，不迁移到 `.agent/`。

### OpenSpec 能力替换后校验不完整

应对：`change.py` 先实现最小可靠校验，覆盖结构完整性、必填文件、L2 design 和关联 plan/task 存在性。更复杂的语义校验后续再演进。

### `changes`、`plans`、`tasks` 状态漂移

应对：职责边界写入 `.flow/workflow.md`，并让 `validate` 检查声明的 plan/task 是否存在，但不维护第三份 tasks 清单。

### 大量路径替换导致脚本遗漏

应对：实现完成前用 `rg` 搜索 `.trellis`、`.agents`、`openspec`、`docs/superpowers`、`AGENTS.md` 等关键路径，逐项确认保留原因。

## 成功标准

1. 模板应用到目标项目后，根目录协作资产只有 `AGENTS.md`、`.agent/`、`.flow/`。
2. 当前 L0 / L1 / L2 工作流仍能完整执行。
3. 不再依赖根目录 `openspec/` 或外部 `openspec` CLI。
4. task、change、plan 三类状态职责清晰，不重复维护 checklist。
5. README、AGENTS、workflow、skills、scripts 的路径引用一致。
