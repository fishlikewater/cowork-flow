---
name: doubt-review
description: Use when making non-trivial implementation decisions, starting L2 tasks, or claiming behavioral correctness. Use when correctness matters more than speed, working in unfamiliar code, or stakes are high.
---

# Doubt Review

## Overview

非平凡决策在被允许进入实现之前，必须通过怀疑审查。这不是可选的自我反思——它是 before-dev 门禁在 L2 任务中的子步骤。

与 `/review`（对已完成 artifact 的 verdict）不同，doubt-review 是 in-flight 姿态：非平凡决策在 course-correction 还便宜时被交叉审查。

## When to Apply

触发条件（满足任一）：
- L2 任务（L1 可选但推荐）
- 引入或修改分支逻辑
- 跨模块边界
- 依赖类型系统无法验证的属性（线程安全、幂等性、顺序不变量）
- 用户明确要求时

不适用于：
- 机械操作（重命名、格式化、文件移动）
- 阅读/总结现有代码
- 一行变更且正确性显见
- 用户明确要求速度 > 验证时

## The 5-Step Doubt Cycle

### Step 1: CLAIM — 2-3 行明确主张

```
CLAIM: "<决策一句话>"
WHY THIS MATTERS: <为什么这个决策错了会致命>
```

如果无法 2-3 行写清 CLAIM，说明你只有模糊感觉，不是决策。感觉到决策之间的距离 = 需要做的调研/思考。

### Step 2: EXTRACT — 最小可审查单元

- 代码：diff 或函数（不是整个文件）
- 决策：3-5 句子 + 约束条件
- 剥离推理过程——只给输入，不给结论

### Step 3: DOUBT — fresh-context 对抗性审查

```
找这个 artifact 的问题。假设作者过度自信。寻找：
- 未声明的假设
- 未处理的边界条件
- 隐藏耦合或共享状态
- 被违反的 contract 场景
- 被破坏的现有惯例
- 在意外输入下的失效模式

不要确认。不要总结。找到问题，或明确声明审查后未发现问题。

ARTIFACT: <粘贴 artifact>
CONTRACT: <粘贴约束>
```

**关键**：只传 ARTIFACT + CONTRACT，不传 CLAIM。传入 CLAIM 会使审查者偏向认同。

注意：不能在子代理上下文中 spawn fresh-context reviewer。如在子代理内遇到需要 doubt 的情形，surface 回主会话。

### Step 4: RECONCILE — 分类每个发现

按优先级（第一个匹配的类别生效）：
1. CONTRACT 误解 → 修复 CONTRACT 后重新分类
2. 有效 + 可行动 → 修改 artifact，重新怀疑周期
3. 有效但可接受权衡 → 明确记录
4. 噪声 → 记录并排除

### Step 5: STOP — 有界循环

满足任一条件停止：
- 下一轮只产生平凡或已考虑的发现
- 3 周期完成（停止，向用户报告不要继续第 4 个）
- 用户明确说"可以了"

3 周期后仍有实质发现 = artifact 不成熟，回到 Step 2 分解。

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "我很自信，跳过怀疑" | 自信与正确性相关性差。最自信时恰好是盲点藏匿处 |
| "spawn reviewer 成本高" | 在生产调试一个错误 commit 的成本更高。怀疑周期是有界的 |
| "检查会在 review 阶段做" | review 是最终 gate。doubt 在 in-flight 阶段，course-correction 还便宜时拦住 |
| "每步都怀疑会无限拖延" | 怀疑仅适用于非平凡决策，重读 When NOT to Use |
| "reviewer 不同意说明我错了" | reviewer 缺你上下文，不同意是信息不是 verdict。RECONCILE 再决定 |

## Red Flags

- 跳过怀疑步骤因为"我很自信"
- 将审查者的输出当作权威而不是信息
- 超过 3 周期仍在循环但未升级给用户
- 审查者提示词使用"这个好吗？"而不是"找问题"
- 连续 2+ 周期有实质发现但 0 个被分类为"可行动"——你在验证，不是怀疑
- 将 CLAIM 传给审查者（使其偏向认同）
- 怀疑表演：spawn reviewer 对未改的 artifact（得到同样发现 = 拖延）

## 与现有系统的关系

- before-dev：doubt-review 是 before-dev 门禁在 L2 任务中的子步骤
- check：check 验证实现正确性；doubt-review 质疑决策方向。使用两者
- party-mode：board 讨论可以产出 CLAIM，但不能替代 fresh-context 怀疑审查
- TDD：TDD 的 RED 步骤是怀疑的具体化——一个失败的测试就是 disproof attempt
- break-loop：当 reviewer 发现真实 failure mode，接入 debugging skill 定位修复

## Verification

- 每个非平凡决策有 CLAIM 记录
- 每个非平凡 artifact 至少一次 fresh-context review
- 审查者收到 ARTIFACT + CONTRACT（不是 CLAIM）
- 发现被分类（不是橡皮图章）
- 满足停止条件
