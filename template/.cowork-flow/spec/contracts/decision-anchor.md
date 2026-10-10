# Decision Anchor Contract

**每个 task 必须有 `decision-anchor.md`，它是执行时防止漂移的唯一权威决策来源。**

它合并并替代了原来的 `prd.md`，同时承载"做什么"和"为什么不这么做"两个职责，压缩任务产物数量。

## Schema

```markdown
# Decision Anchor

## 目标
<一句话>

## 验收标准
- [ ] AC-001: <可验证>
- [ ] AC-002: <可验证>

## 被拒方案（可选）
- **方案B**: <简述> — 拒绝原因: <为什么>

## 关键假设（可选）
- <假设1>

## 范围边界（可选）
- 范围内: <列出>
- 范围外: <列出>

## 验证命令（可选）
- `<command>` → <expected>
```

## 章节要求

| 章节 | 必填 | 原因 |
|------|------|------|
| `## 目标` | 必备 | 没有目标就没有验收基准 |
| `## 验收标准` | 必备 | 没有验收标准 task_start 会被阻断 |
| `## 被拒方案` | 可选 | brainstorming 任务必填，防止执行时重新考虑被拒方案 |
| `## 关键假设` | 可选 | 复杂任务填写，暴露隐性约束 |
| `## 范围边界` | 可选 | 防止范围蔓延 |
| `## 验证命令` | 可选 | 复杂任务填写，作为自动验证依据 |

### 机器可读行格式（注入用）

`## 验证命令` 与 `## 范围边界` 会被 stage-contract 注入与 MCP 事实视图解析（`services/fact_view.parse_decision_anchor`）。行格式约定：

- `## 验证命令`：每行一条命令（可带 `- ` 前缀），截 120 字符，最多 5 条；命令由实现 agent 自行执行（自声明自查），reviewer 核对执行证据
- `## 范围边界`：仅取首个非空行，截 160 字符

## 场景

| 场景 | 来源 | 填充内容 |
|------|------|---------|
| 有 brainstorming | 从讨论结论提取 | 全部章节 |
| 无 brainstorming（需求明确） | 从需求描述和 plan 提取 | 最小：目标 + 验收标准 |

## 产物压缩

合并前（6个文件）：`prd.md` + `implement.jsonl` + `check.jsonl` + `debug.jsonl` + `task.json`

合并后（5个文件）：`decision-anchor.md` + `implement.jsonl` + `check.jsonl` + `debug.jsonl` + `task.json`

**净减 1 个文件类型。相关文件追踪现在由 implement.jsonl 统一负责。**

## Lifecycle Check 联动

- `task next <dir> --run` 启动任务时的 preflight 检查 `decision-anchor.md` 非空，并要求 `## 目标` 和 `## 验收标准` 章节存在。
- **门禁档案 `meta.gateProfile`**：新建任务写入 `"strict"`；未标记的任务按 `"legacy"` 处理——存量任务不被追溯重新门禁，档案可经事实视图查询。strict 任务在章节检查之上再要求：`## 验收标准` 至少一条可解析的 `- [ ] AC-xxx: ...` 行、AC id 不重复、该章节内没有非 AC 的列表行，且必须声明 `dev_type`（否则 `task specs` 的 dev-type 派发静默变短）。
- `## 验收标准` 行的勾选状态（`- [ ]` / `- [x]`）与证据记录（任务目录 `evidence.jsonl`）是完成门禁的事实源：存在未勾选 AC（`LIFECYCLE-AC-001`）、已声明 AC 缺证据（`LIFECYCLE-AC-002`）、strict 任务读不到 AC 行（`LIFECYCLE-AC-003`）或 AC 证据模块不可用（`LIFECYCLE-AC-004`）时完成被阻断。schema 与豁免见 `evidence-completion.md`。
- **复核凭证的变更指纹**（strict 任务完成时要求最新凭证与当前状态一致，`LIFECYCLE-REVIEW-003`）输入 = git 可见变更（路径 + 内容摘要）+ 本锚点的目标与 AC 正文 + 绑定计划的内容摘要 + `dev_type` + 被引用 spec 的**正文摘要** + `implement.jsonl` 的内容摘要。`spec/**` 与 `tasks/**` 都被 gitignore，后两项因此必须显式入指纹，否则改写被引用 spec 的正文、或扩大声明范围，都不会使旧凭证失效。
- 指纹**排除项**（机制）：变更集排除 `.cowork-flow/tasks/**` 整段、`.cowork-flow/.runtime/**` 与 `.cowork-flow/logs/**`——任务目录内的产物（`task.json`、`evidence.jsonl`、`review.jsonl`、`check.jsonl`、`debug.jsonl`，以及 anchor 的**路径层**）与运行期元数据都不计入，否则凭证一记录就自我失效。`implement.jsonl` 的路径层同样被排除，其**内容**改由 `scope` 分量计入。
- 推论（预期成本，非缺陷）：**`implement.jsonl` 的任意字节变化**（追加/删除范围条目、改 `reason` 措辞、`task context add` 自动追加的 domain guide 条目）**或被引用 spec 正文的改写，都会使既有凭证失效**，需在最终状态重跑一次复核。证据追加、AC 勾选与运行期元数据不在此列。
- `cowork-implement` 读取：见 .cowork-flow/spec/contracts/subagent-dispatch.md
- `cowork-check` 读取：同上
- `debug.jsonl` 引用：可选，偏差诊断时写入 anchor 锚点差异

## 正式版行为

正式版不自动迁移旧 `prd.md`。任务启动时只认可 `decision-anchor.md`
作为权威决策来源；如果任务目录只有 `prd.md` 而缺少
`decision-anchor.md`，`task next <dir> --run` 必须 fail-closed 并报告
`decision-anchor.md is missing or empty`。

已有旧任务需要人工把 `prd.md` 内容转换为 `decision-anchor.md`，并补齐
`## 目标` 与 `## 验收标准` 后再启动。
