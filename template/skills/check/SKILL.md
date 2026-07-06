---
name: check
description: Use after code or workflow changes to verify quality, spec compliance, tests, cross-layer contracts, and template/root consistency before finish-work.
---

# Check

Use this after implementation and before `finish-work`.

## Step 0: Anti-Rationalization Gate

在开始正式检查之前，用以下问题自检：

- "我是否在跳过某个步骤因为感觉很简单？" → 简单也需要证据
- "我是否在降低标准因为时间压力？" → 时间压力是红灯，不是借口
- "我是否在用'看起来对'代替'可验证的正确'？" → 命令输出才是证据
- "我是否在批量跳过步骤因为'都差不多'？" → 每个步骤有独立目的

任一项回答"是"时，回退到当前步骤的起点，用可验证的方式重新执行。

## Steps

1. Read active task PRD, plan, and `check.jsonl`.
2. Review `git diff --name-only` and `git diff`.
3. Check contracts across caller/callee, command output, persisted state, templates, and docs.
4. Verify spec compliance:
   - Read each spec file listed in `check.jsonl`.
   - For each guideline in the spec, check the diff for violations (naming, structure, encoding, error handling, quality gates).
   - Spec files not listed in `check.jsonl` do not apply to this check.
5. Confirm `.cowork-flow/spec/` is updated or explicitly unchanged.
6. Review test intent: reject shallow tests that do not fail for meaningful behavior breaks.
7. Run focused tests that would fail if the changed behavior broke.
8. Run broader validation when the change touches shared runtime, templates, packaging, or public workflow.
9. Report `test_intent_review` with the key tests that defend PRD acceptance behavior.
10. Report spec compliance: for each spec/ file checked, state pass/fail with evidence from the diff.

## Report

Return:

- Issues found and fixes made.
- Files reviewed.
- Commands run and results.
- Remaining risks.

Do not claim success from intent. Use command output and reviewed diffs as evidence.

## Debug Quality Check

- 根因修复有对应的回归测试（不是症状修复）
- 不是症状修复（修了 UI 层面的重复而不是 API 层面的重复）
- 证据记录在 `<task>/debug.jsonl` 中（如有）
- 如果是重复触发的 bug，break-loop 记录在 `<task>/break-loop.md` 中

## Simplification Review（代码修改量 > 50 行或 review 发现可读性问题时执行）

### 修改前自检（Chesterton's Fence）

对每处简化，回答：
- 这个代码的职责是什么？谁调用它？它调用什么？
- 现有测试定义的行为是否会被破坏？
- 原始作者为什么这样写？（git blame 检查）
如果无法回答，停下——你不理解这处代码。

### 简化信号

| 信号 | 处理 |
|---|---|
| 嵌套深度 >= 3 层 | 提取 guard clause 或 helper |
| 函数 > 50 行 | 按职责拆分为多个命名函数 |
| 嵌套三元表达式 `a ? b : c ? d : e` | 用 if/else / switch / lookup 替代 |
| 布尔参数标志 `doThing(true, false, true)` | 用 options 对象或拆分为两个函数替代 |
| 同一条件检查 >= 3 次 | 提取为命名 predicate 函数 |
| 冗余 wrapper `async () => await foo()` | 直接导出 foo |
| 未使用的 import / 变量 | 删除（确认无副作用后）|
| 缺少 type hint（项目约定强制时） | 补充 |

### 命名可读性信号

| 信号 | 处理 |
|---|---|
| `data`、`result`、`temp`、`val` | 改名描述内容：`userProfile`、`errors` |
| 缩写 `usr`、`cfg`、`btn`、`evt` | 用全称（`id`、`url`、`api` 例外） |
| 名称与行为不符（`get` 但 mutates） | 改名反映实际行为 |
| "what" 注释（`// increment counter` 在 `count++` 上） | 删除注释 |
| "why" 注释（`// Retry because API is flaky`） | 保留 |

### Rule of 500

如果一处重构会修改 > 500 行，用自动化工具（sed/codemod/AST 变换）而不是手工编辑——手工大规模修改容易出错且审查疲劳。

### Red Flags

- 简化导致测试失败（行为被改变了——违反"保留行为"原则）
- "简化"后更长且更难读
- 改名是按个人偏好而非项目约定
- 删除"让代码更整洁"的错误处理
- 批量多个简化到一个不可回滚的大 commit
