# Definition of Done

> 项目级完成门槛。每项变更在被视为"完成"前必须满足。与 per-task AC 互补但不替代。

## 通用门槛（所有任务）

| # | 检查项 | 验证 |
|---|---|---|
| G1 | 代码实现符合 decision-anchor acceptance criteria | AC 全部为 verified |
| G2 | 行为变更有对应测试或明确验证命令；高风险任务覆盖失败、边界或回归路径 | `./.cowork-flow/run task next <dir> --validate` 与任务验证命令通过 |
| G3 | check phase 完成，无 unresolved blocker | `task-review` 结论为 pass，completion lifecycle blocker 为 0 |
| G4 | 无新引入 lint/type/build 警告 | lint / build 命令通过 |
| G5 | Git status snapshot 仅含任务相关变更，包括 staged、unstaged、untracked | git status --porcelain=v1 -uall |

## L0 专属（docs/format/comments only）

| # | 检查项 |
|---|---|
| L0-1 | 确认变更不涉及行为（docs/format/comments only）|
| L0-2 | git diff --check 无空白错误 |

## L1 专属（单模块行为变更）

| # | 检查项 |
|---|---|
| L1-1 | brainstorming 记录存在 |
| L1-2 | 修改未扩散到无关模块（git diff 范围与 task.scope 一致）|

## L2 专属（跨层 / 架构 / 迁移）

| # | 检查项 |
|---|---|
| L2-1 | proposal.md / spec.md / design.md 齐全 |
| L2-2 | 结构化决策审查已按 Skill 指导完成或明确记录不适用 |
| L2-3 | readiness gate 全部通过（`task next <dir> --run` 无 blocker）|
| L2-4 | spec-sync Skill 已确认规格同步或明确记录无需更新 |

## DoD 与 per-task AC 的区别

| DoD | AC |
|---|---|
| 项目级不变量——本次任务不例外 | decision-anchor 特有的完成条件 |
| 来源：spec/references/definition-of-done | 来源：<task>/decision-anchor.md |
| 两者都满足 = 任务真正完成 |
