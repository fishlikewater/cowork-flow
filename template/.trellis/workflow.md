# 标准开发工作流

## 1. 流程目标

开发过程必须形成稳定闭环：

```text
获取上下文 -> 阅读规范 -> 任务分级 -> 规格与计划 -> 执行实现 -> 验证审阅 -> 状态同步 -> session 记录
```

所有任务都应先明确目标和验收标准，再进入实现；所有完成结论都必须有验证证据支撑。

---

## 2. 职责边界

### 2.1 OpenSpec

`OpenSpec` 负责行为变更治理：

- proposal：为什么要改
- spec：外部行为与验收标准
- design：重要设计取舍，主要用于复杂或跨层变更
- tasks：高层里程碑
- archive：完成后的规格归档

### 2.2 superpowers

`superpowers` 负责工作方法：

- `superpowers:brainstorming`：澄清需求、比较方案、形成设计
- `superpowers:writing-plans`：把设计拆成可执行计划
- `superpowers:executing-plans`：按计划顺序执行
- `superpowers:subagent-driven-development`：在适合时并行拆分独立工作
- `superpowers:verification-before-completion`：完成前用证据验证

### 2.3 Trellis

`Trellis` 负责承载任务状态与上下文：

- 当前开发者身份
- 当前任务
- 任务 PRD
- implement / check / debug 上下文
- journal 与 session 记录
- 任务归档

执行按 superpowers 方法推进；Trellis 不替代 superpowers，也不替代项目验证命令。

---

## 3. 核心原则

1. **先读后写**：动手前先读取项目规则、任务上下文和相关规范。
2. **规格先行**：有行为变化时，先补规格，再写计划，再实现。
3. **计划后编码**：复杂或行为变更任务必须先形成可执行计划。
4. **上下文显式化**：不要依赖记忆，把关键规范、设计、计划写入任务上下文。
5. **一次一个任务**：避免在多个无关任务之间来回切换。
6. **执行中回写状态**：计划、任务状态、OpenSpec tasks 和 journal 不应长期漂移。
7. **证据先于结论**：未验证前不声称完成、通过或可交付。
8. **经验沉淀回规范**：实现中发现的契约、坑点、规则应更新到 `.trellis/spec/`。

---

## 4. 会话开始流程

### 4.1 初始化开发者身份

首次进入项目时执行：

```bash
python3 ./.trellis/scripts/get_developer.py
python3 ./.trellis/scripts/init_developer.py <developer-name>
```

如果已经存在开发者身份，只需读取当前身份。

### 4.2 获取当前上下文

每次开始工作先执行：

```bash
python3 ./.trellis/scripts/get_context.py
python3 ./.trellis/scripts/task.py list
git status
git log --oneline -10
```

至少确认：

- 当前开发者是谁
- 是否存在当前任务
- 是否存在未归档任务
- 工作区是否干净
- 最近提交是否影响当前任务

### 4.3 阅读固定入口文件

开始编码前至少读取：

```bash
cat AGENTS.md
for f in .trellis/spec/frontend/index.md .trellis/spec/backend/index.md .trellis/spec/guides/index.md; do
  [ -f "$f" ] && cat "$f"
done
```

然后根据索引读取与当前任务相关的细分规范。

---

## 5. 任务分级

所有任务先分级，再选择流程。

### 5.1 L0：无外部行为变化

适用场景：

- 文档整理
- 小范围重构
- 测试补充
- 注释、格式、脚本清理
- 不改变用户可观察行为的内部调整

流程：

```text
Trellis 任务 -> 读取规范 -> 简短计划 -> 实现 -> 验证 -> 记录 session
```

### 5.2 L1：局部行为变化

适用场景：

- 单模块功能调整
- 单接口行为变化
- 局部数据处理逻辑变化
- 有明确边界的新能力

流程：

```text
OpenSpec -> brainstorming -> writing-plans -> Trellis 任务上下文 -> 执行计划 -> 验证 -> 归档与记录
```

### 5.3 L2：跨层或重要行为变化

适用场景：

- 跨前后端或跨服务变更
- API / DB / 消息 / 缓存 / 文件等契约变化
- 架构边界变化
- 影响发布、迁移、安全、权限或兼容性的变更

流程：

```text
OpenSpec -> brainstorming -> design.md -> writing-plans -> Trellis 任务上下文 -> 执行计划 -> 多视角审阅 -> 验证 -> 归档与记录
```

---

## 6. L0 标准流程

### 6.1 创建或选择 Trellis 任务

```bash
python3 ./.trellis/scripts/task.py list
python3 ./.trellis/scripts/task.py create "<title>" --slug <task-name>
```

### 6.2 写入任务 PRD

在任务目录创建或更新 `prd.md`，至少包含：

- 目标
- 范围
- 验收标准
- 相关文件或模块
- 验证方式

### 6.3 初始化任务上下文

```bash
python3 ./.trellis/scripts/task.py init-context <task-dir> <type>
```

`<type>` 按任务选择：

- `backend`
- `frontend`
- `fullstack`
- `test`
- `docs`

### 6.4 补充任务上下文

把任务相关规范、代码模式、计划文件加入上下文：

```bash
python3 ./.trellis/scripts/task.py add-context <task-dir> implement <path> "<reason>"
python3 ./.trellis/scripts/task.py add-context <task-dir> check <path> "<reason>"
```

### 6.5 激活任务并执行

```bash
python3 ./.trellis/scripts/task.py start <task-dir>
```

执行要求：

- 按 `prd.md` 和上下文实现
- 遵循 `.trellis/spec/` 中的相关规范
- 变更保持聚焦
- 若执行中发现行为变化升级，立即重新分级并进入 L1 / L2 流程

---

## 7. L1 / L2 标准流程

### 7.1 创建 OpenSpec 变更

```bash
openspec new change <slug>
```

### 7.2 使用 brainstorming 形成方案

使用 `superpowers:brainstorming` 澄清需求、比较方案，并补齐：

- `openspec/changes/<slug>/proposal.md`
- `openspec/changes/<slug>/specs/.../spec.md`
- L2 任务需要 `openspec/changes/<slug>/design.md`

### 7.3 校验 OpenSpec

```bash
openspec validate --strict --type change <slug>
```

### 7.4 使用 writing-plans 形成计划

使用 `superpowers:writing-plans` 输出可执行计划：

```text
docs/superpowers/plans/YYYY-MM-DD-<slug>.md
```

计划必须包含：

- 可勾选步骤
- 每步验证方式
- 当前执行状态
- 阻塞与决策记录位置

### 7.5 回写 OpenSpec tasks

`openspec/changes/<slug>/tasks.md` 只保留高层里程碑。

细粒度执行状态以 `docs/superpowers/plans/*.md` 为准，避免维护两套细节状态。

### 7.6 创建或绑定 Trellis 任务

将以下内容加入 Trellis 任务上下文：

- proposal
- spec
- design，如存在
- implementation plan
- 相关 `.trellis/spec/`
- 相关代码模式或契约文件

### 7.7 按 superpowers 方法执行

执行时使用：

- `superpowers:executing-plans`
- 或在存在独立并行工作时使用 `superpowers:subagent-driven-development`

执行中必须持续同步：

- plan checkbox
- plan 当前执行状态
- Trellis task 状态
- OpenSpec 高层 tasks
- 必要的 `.trellis/spec/` 更新

---

## 8. 验证与审阅

### 8.1 验证命令来源

验证命令按以下顺序读取：

1. `.trellis/config.yaml`
2. `AGENTS.md`
3. 项目现有脚本或配置文件

如果需要推断验证命令，必须明确说明推断依据。

### 8.2 完成前检查

完成前至少确认：

- 相关测试通过
- lint / format / build / typecheck 按项目要求通过
- 行为符合 OpenSpec 或 PRD
- 相关 `.trellis/spec/` 已同步
- 计划状态与真实进度一致
- 没有未说明的临时文件、调试输出或绕过逻辑

### 8.3 L2 额外审阅

L2 任务完成前需要多视角审阅：

- 行为契约
- 数据流
- 错误处理
- 兼容性
- 测试覆盖
- 发布或迁移风险

---

## 9. 会话结束流程

### 9.1 收尾前同步状态

结束前确认：

- 当前 task 状态准确
- plan checkbox 与真实进度一致
- OpenSpec tasks 与 plan 高层状态一致
- `.trellis/spec/` 已沉淀必要经验
- 工作区状态清晰

### 9.2 记录 session

```bash
python3 ./.trellis/scripts/get_context.py --mode record
python3 ./.trellis/scripts/add_session.py \
  --title "<session-title>" \
  --commit "<commit-or-handoff-ref>" \
  --summary "<summary>"
```

### 9.3 归档任务

仅在任务真实完成后归档：

```bash
python3 ./.trellis/scripts/task.py archive <task-name>
```

行为变更任务还需要归档 OpenSpec：

```bash
openspec archive <slug>
```

---

## 10. 状态持久化规则

长任务必须把关键状态写入文件，而不是只留在聊天上下文中。

| 状态 | 持久化位置 |
|------|------------|
| 当前开发者 | `.trellis/.developer` |
| 当前任务 | `.trellis/.current-task` |
| 任务目标 | `.trellis/tasks/<task>/prd.md` |
| 任务上下文 | `.trellis/tasks/<task>/*.jsonl` |
| 行为变更规格 | `openspec/changes/<slug>/` |
| 执行计划 | `docs/superpowers/plans/*.md` |
| 项目规范 | `.trellis/spec/` |
| 会话记录 | `.trellis/workspace/<developer>/journal-*.md` |

如果状态只存在于对话中，就不能视为可靠流程状态。

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
- OpenSpec 或计划中的必要步骤已完成
- 验证命令已按项目要求执行
- 失败、跳过或无法执行的验证已明确说明
- 相关规范已更新
- 计划状态、Trellis 状态、OpenSpec 状态不冲突
- session 已记录
