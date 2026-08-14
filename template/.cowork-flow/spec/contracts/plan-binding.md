# Plan Binding Contract

计划绑定让开发计划进入实施路径，但不把计划变成第二套流程内核。

## 权威边界

- `decision-anchor.md` 继续承载目标、验收标准和范围判断。
- `implement.jsonl` 继续承载 review/complete 的硬文件范围。
- `.cowork-flow/plans/*.md` 承载实施顺序、文件边界、验证命令和禁止漂移说明。
- `task.json.meta.planFile` 只记录 repo-relative 计划路径。

## 创建阶段

- 普通 `task create` 可以创建没有计划的 planning task。
- `task create --from-plan <path>` 是显式绑定请求；`<path>` 必须存在、位于仓库内，并位于 `.cowork-flow/plans/` 下。
- 成功绑定后，runtime 写入：

```json
{
  "meta": {
    "planFile": ".cowork-flow/plans/YYYY-MM-DD-slug.md"
  }
}
```

## 规划期绑定

- 未在创建时绑定的 planning task 可执行
  `./.cowork-flow/run task next <task-dir> --run --from-plan <path>` 补绑计划。
- 校验与创建阶段一致：路径存在、位于仓库内、`.cowork-flow/plans/` 下且非空。
- 绑定只写 `task.json.meta.planFile`（保留 meta 其它键），不改任务状态；
  绑定后重新运行 `task next <task-dir> --run` 继续。
- 非 planning 任务携带 `--from-plan` 被拒绝（next action 不是
  `edit_planning_artifacts` 时 runner 报错）。

## 启动实施前

Normal / High-risk task 从 `planning` 进入 `in_progress` 前必须满足：

- `task.json.meta.planFile` 存在。
- `planFile` 是 repo-relative `.cowork-flow/plans/` 路径。
- 计划文件存在且非空。
- `decision-anchor.md` 包含 `## 目标` 和 `## 验收标准`。
- `implement.jsonl` 通过既有 context validation。

Tiny task 可以没有 planFile，但仍必须满足现有 anchor 与 implement 范围要求。

## 实施恢复

当 active task 绑定了 `meta.planFile`，恢复清单必须提示先读取当前计划，再读取 `decision-anchor.md` 和 JSONL context。恢复输出只列路径，不展开计划正文。

## 归档阶段

- 归档任务时，runtime 把 `meta.planFile` 指向的计划文件按字节复制为归档任务目录下的 `plan.md` 快照，使归档记录自包含。
- 快照是复制不是移动：`.cowork-flow/plans/` 原件与 `meta.planFile` 指针保持不变。
- `meta.planFile` 缺失、为空或指向不存在的文件时跳过快照，归档照常完成。
- 快照写入失败按既有归档事务回滚（TASK-ARCHIVE-PLAN-001）；回滚时删除已写入的快照。

## v1 非目标

- 不解析计划 step 状态。
- 不做 Markdown AST 或 DSL。
- 不比较 AC 文本与计划任务正文。
- 不匹配验证命令和证据记录。
- 不引入 plan approval 数据模型。

这些能力只能在 warning 噪音和真实收益被验证后再考虑。
