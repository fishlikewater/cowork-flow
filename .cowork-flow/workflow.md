# 标准开发工作流

## 1. 流程目标

开发过程必须形成稳定闭环：

```text
获取上下文 -> 阅读规范 -> 任务分级 -> 规格与计划 -> 执行实现 -> 验证审阅 -> 状态同步 -> session 记录
```

所有任务先明确目标和验收标准，再进入实现；所有完成结论都必须有验证证据。命令示例默认使用 macOS / Linux / Git Bash / WSL；Windows cmd / PowerShell 使用 `.\.cowork-flow\run.cmd <command>` 替代 `./.cowork-flow/run <command>`。

---

## 2. 职责边界

| 对象 | 负责内容 |
|------|----------|
| `cowork-flow change` | 行为变更治理：`proposal` 说明为什么改，`spec` 定义外部行为与验收标准，`design` 记录复杂或跨层设计取舍，`change.yaml` 保存状态/分级/关联 plan 与 task，`archive` 归档完成后的行为规格。 |
| `superpowers` | 工作方法：`brainstorming` 澄清需求和方案，`writing-plans` 拆可执行计划，`test-driven-development` 约束实现，`executing-plans` 顺序执行，`subagent-driven-development` 并行拆分，`verification-before-completion` 完成前取证。 |
| `.cowork-flow` | 任务状态和上下文：当前开发者、当前任务、PRD、`implement/check/debug` 上下文、journal、session 记录和任务归档。 |

`.cowork-flow` 不替代 superpowers，也不替代项目验证命令。除一次性原型、生成代码、纯配置文件等明确例外并经人工确认外，功能新增、缺陷修复、重构和行为变更都必须按 RED-GREEN-REFACTOR 推进；复杂或难点问题按深度优先。

---

## 3. 核心原则

1. **先读后写**：动手前先读取项目规则、任务上下文和相关规范。
2. **规格先行**：有行为变化时，先补规格，再写计划，再实现。
3. **计划后编码**：复杂或行为变更任务必须先形成可执行计划。
4. **上下文显式化**：不要依赖记忆，把关键规范、设计、计划写入任务上下文。
5. **一次一个任务**：避免在多个无关任务之间切换。
6. **执行中回写状态**：plan、task、change metadata 和 journal 不应长期漂移。
7. **证据先于结论**：未验证前不声称完成、通过或可交付。
8. **经验沉淀回规范**：实现中发现的契约、坑点、规则应更新到 `.cowork-flow/spec/`。

---

## 4. 会话开始流程

### 4.1 初始化开发者身份

首次进入项目时执行；如果已经存在开发者身份，只需读取当前身份。

```bash
./.cowork-flow/run get-developer
./.cowork-flow/run init-developer <developer-name>
```

### 4.2 获取当前上下文

每次开始工作先执行：

```bash
./.cowork-flow/run resume
./.cowork-flow/run task list
git status
git log --oneline -10
```

至少确认当前开发者、当前任务、未归档任务、工作区状态，以及最近提交是否影响当前任务。

### 4.3 阅读固定入口文件

开始编码前至少读取：

```bash
cat AGENTS.md
for f in .cowork-flow/spec/frontend/index.md .cowork-flow/spec/backend/index.md .cowork-flow/spec/guides/index.md; do
  [ -f "$f" ] && cat "$f"
done
```

然后根据索引读取与当前任务相关的细分规范。

---

## 5. 任务分级

所有任务先分级，再选择流程。

| 等级 | 适用场景 | 流程 |
|------|----------|------|
| L0：无外部行为变化 | 文档整理、小范围重构、测试补充、注释/格式/脚本清理、不改变用户可观察行为的内部调整 | 任务 -> 读取规范 -> 简短计划 -> 实现 -> 验证 -> 记录 session |
| L1：局部行为变化 | 单模块功能调整、单接口行为变化、局部数据处理逻辑变化、有明确边界的新能力 | cowork-flow change -> brainstorming -> writing-plans -> 任务上下文 -> 执行计划 -> 验证 -> 归档与记录 |
| L2：跨层或重要行为变化 | 跨前后端或跨服务变更；API / DB / 消息 / 缓存 / 文件等契约变化；架构边界变化；影响发布、迁移、安全、权限或兼容性的变更 | cowork-flow change -> brainstorming -> design.md -> writing-plans -> 任务上下文 -> 执行计划 -> 多视角审阅 -> 验证 -> 归档与记录 |

---

## 6. L0 标准流程

### 6.1 创建或选择任务

```bash
./.cowork-flow/run task list
./.cowork-flow/run task create "<title>" --slug <task-name>
```

### 6.2 写入任务 PRD

在任务目录创建或更新 `prd.md`，至少包含：目标、范围、验收标准、相关文件或模块、验证方式。

### 6.3 初始化任务上下文

```bash
./.cowork-flow/run task init-context <task-dir> <type>
```

`<type>` 按任务选择：`backend`、`frontend`、`fullstack`、`test`、`docs`。

### 6.4 补充任务上下文

把任务相关规范、代码模式、计划文件加入上下文：

```bash
./.cowork-flow/run task add-context <task-dir> implement <path> "<reason>"
./.cowork-flow/run task add-context <task-dir> check <path> "<reason>"
```

### 6.5 激活任务并执行

```bash
./.cowork-flow/run task start <task-dir>
```

执行要求：

- 按 `prd.md` 和上下文实现。
- 遵循 `.cowork-flow/spec/` 中的相关规范。
- 变更保持聚焦。
- 若执行中发现行为变化升级，立即重新分级并进入 L1 / L2 流程。
- 执行计划中的每个实现步骤必须优先进入 `superpowers:test-driven-development` 循环，不得先写生产代码再补测试。

---

## 7. L1 / L2 标准流程

### 7.1 创建 cowork-flow change

```bash
./.cowork-flow/run change create <slug>
```

### 7.2 使用 brainstorming 形成方案

使用 `superpowers:brainstorming` 澄清需求、比较方案，并补齐：

- `.cowork-flow/changes/<slug>/proposal.md`
- `.cowork-flow/changes/<slug>/spec.md`
- L2 任务需要 `.cowork-flow/changes/<slug>/design.md`

### 7.3 校验 cowork-flow change

```bash
./.cowork-flow/run change validate <slug>
```

### 7.4 使用 writing-plans 形成计划

使用 `superpowers:writing-plans` 输出可执行计划：

```text
.cowork-flow/plans/YYYY-MM-DD-<slug>.md
```

计划必须包含可勾选步骤、每步验证方式、当前执行状态、阻塞与决策记录位置。

### 7.5 同步计划与状态边界

- `.cowork-flow/changes/<slug>/` 只保存 proposal、design、behavior specs 和 `change.yaml`。
- 实现 checklist 只保存在 `.cowork-flow/plans/*.md`。
- 任务运行状态只保存在 `.cowork-flow/tasks/`。
- 不要在 change 目录中维护实现 checklist，避免维护两套细节状态。

### 7.6 创建或绑定任务

将 proposal、spec、design（如存在）、implementation plan、相关 `.cowork-flow/spec/`、相关代码模式或契约文件加入任务上下文。

### 7.7 按 superpowers 方法执行

执行 plan 前，先判断**是否存在适合并行执行的独立任务**。并行是优化手段，不是完成定义；`agent_team.enabled` 只决定在适合并行时优先使用哪种机制，不决定是否必须并行。

适合并行的条件包括：

- 子任务之间没有共享写文件，或共享写文件已有明确顺序边界。
- 子任务之间没有强顺序依赖。
- 每个子任务都有清晰输入、输出和验收方式。
- 主 agent 能在集成前独立审查每个结果。
- 并行带来的收益大于调度、审阅和集成成本。

不适合并行的情况包括：

- 改动集中在同一组强耦合文件。
- 需要密集的 TDD 红绿循环或即时反馈。
- parser、schema、runtime、测试需要同步演进。
- 子任务边界不清，拆分后的主要成本会落在集成。
- 任务规模小于并行调度成本。

不得为了满足流程形式而强行拆分高耦合任务。若不适合并行，必须简要记录不使用并行的理由，并在当前会话中按 plan 顺序执行。

若适合并行：

- 当 `.cowork-flow/config.yaml` 中设置 `agent_team.enabled: true` 时，使用 `./.cowork-flow/run agent-team prepare <task-dir> --plan <plan-file>` 生成调度图，再用 `./.cowork-flow/run agent-team next <task-dir>` 获取可并行 assignments，由主 agent 审核并调度 subAgent。
- 当 `.cowork-flow/config.yaml` 中设置 `agent_team.enabled: false` 且宿主支持 subAgent 时，可使用 `superpowers:subagent-driven-development` 开启多 agent 并行执行。
- 当宿主不支持 subAgent 或任务不适合并行时，使用 `superpowers:executing-plans` 或当前会话顺序执行。

无论是否并行，都必须严格遵循 `superpowers:test-driven-development`，不得先写生产代码再补测试。

执行中必须持续同步：

- plan checkbox
- plan 当前执行状态
- 任务状态
- agent-team status / result / review / retry 工件，如本次执行启用了 agent team
- 必要的 `.cowork-flow/spec/` 更新

启用 agent team 时，主 agent 仍是协调者：负责审核并行安全性、补充上下文、处理阻塞、集成结果，并在完成前运行 `./.cowork-flow/run agent-team complete <task-dir>`。

---

## 8. 验证与审阅

### 8.1 验证命令来源

验证命令按以下顺序读取：

1. `.cowork-flow/config.yaml`
2. `AGENTS.md`
3. 项目现有脚本或配置文件

如果需要推断验证命令，必须明确说明推断依据。

### 8.2 完成前检查

完成前至少确认：

- 相关测试通过
- 新增或修改的行为有测试先失败、再通过的验证证据
- lint / format / build / typecheck 按项目要求通过
- 行为符合 cowork-flow change 规格或 PRD
- 相关 `.cowork-flow/spec/` 已同步
- 计划状态与真实进度一致
- 没有未说明的临时文件、调试输出或绕过逻辑

### 8.3 L2 额外审阅

L2 任务完成前需要多视角审阅：行为契约、数据流、错误处理、兼容性、测试覆盖、发布或迁移风险。

---

## 9. 会话结束流程

### 9.1 收尾前同步状态

结束前确认当前 task 状态、plan checkbox、change metadata、必要的 `.cowork-flow/spec/` 沉淀和工作区状态都与真实进度一致。

### 9.2 记录 session

```bash
./.cowork-flow/run get-context --mode record
./.cowork-flow/run add-session \
  --title "<session-title>" \
  --commit "<commit-or-handoff-ref>" \
  --summary "<summary>"
```

### 9.3 归档任务

仅在任务真实完成后归档：

```bash
./.cowork-flow/run task archive <task-name>
```

行为变更任务还需要归档 cowork-flow change：

```bash
./.cowork-flow/run change archive <slug>
```

---

## 10. 状态持久化与恢复

长任务必须把关键状态写入文件，而不是只留在聊天上下文中。

| 状态 | 持久化位置 |
|------|------------|
| 当前开发者 | `.cowork-flow/.developer` |
| 当前任务 | `.cowork-flow/.current-task` |
| 任务目标 | `.cowork-flow/tasks/<task>/prd.md` |
| 任务上下文 | `.cowork-flow/tasks/<task>/*.jsonl` |
| 行为变更规格 | `.cowork-flow/changes/<slug>/` |
| 执行计划 | `.cowork-flow/plans/*.md` |
| 项目规范 | `.cowork-flow/spec/` |
| 会话记录 | `.cowork-flow/workspace/<developer>/journal-*.md` |

如果状态只存在于对话中，就不能视为可靠流程状态。

### 10.1 恢复分层

| 层级 | 读取内容 | 使用时机 |
|------|----------|----------|
| 最小恢复层 | `resume.py` 输出中的 `RESUME CHECKLIST` | 每次恢复、压缩后、重新接手任务 |
| 任务执行层 | 当前任务 `prd.md`、当前 plan 状态、`task.py list-context <task-dir>` | 准备继续实现或检查前 |
| 细节规范层 | jsonl 指向的具体 spec、代码模式或计划段落 | 当前修改确实需要该细节时 |

### 10.2 恢复规则

- 先执行 `./.cowork-flow/run resume`。
- 按 `RESUME CHECKLIST` 读取当前 PRD、当前 plan 和 `list-context` 输出。
- 不要全量重读 `.cowork-flow/spec/`、所有 plan、所有 task 或 workspace journal。
- 如果 plan 有 `Current Execution Status`，先读该段以确定下一步。
- 如果 jsonl 指向的规范过多，先根据当前阶段选择最小相关集合。

恢复目标是重建“现在该做什么”和“当前门禁是否满足”，不是把全部历史重新塞进上下文。

---

## 11. 禁止事项

- 不跳过上下文读取直接编码。
- 不在未验证时声称完成。
- 不把 reusable skill 改成项目临时清单。
- 不维护互相冲突的任务状态。
- 不在行为变化未补规格时直接实现。
- 不在计划未同步时记录 session 或归档任务。

---

## 12. 完成定义

一个任务只有在以下条件同时满足时，才算完成：

- 需求或 PRD 已满足
- cowork-flow change 规格或计划中的必要步骤已完成
- 验证命令已按项目要求执行
- 失败、跳过或无法执行的验证已明确说明
- 相关规范已更新
- change metadata、计划状态、任务状态不冲突
- session 已记录
