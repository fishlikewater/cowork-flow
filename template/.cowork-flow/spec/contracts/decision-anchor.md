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
