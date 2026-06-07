# Design: Manual Party Mode

## 决策

采用 skill-first 设计：新增 `party-mode` skill 作为用户手动入口，由主会话按 host adapter 派发真实子代理、等待结果、发起有限追问并综合结论。CLI 命令只作为可选的状态和报告辅助，不直接依赖 Codex 工具，也不承担派发能力。

## 架构边界

Party Mode 是 advisory workflow，不是正式实现或检查阶段。它可用于 `brainstorming`、plan 前评审、任务切片诊断、复盘和 check 争议会，但不能推进 `task review`、`task complete` 或替代 `cowork-check`。

主会话是唯一协调者。讨论子代理是叶子执行者，禁止再派发、等待、列出或关闭其他代理。正式 `cowork-*` 派发仍按 `.cowork-flow/spec/subagent-dispatch.md` 使用 runtime context；generic `worker` 只能作为 advisory 观点来源。

## 轮次模型

```text
init -> round1_independent -> synthesize
     -> round2_rebuttal? -> synthesize
     -> round3_decision_check? -> close
```

- 第 1 轮：默认 2 到 3 个真实子代理独立首判，互不可见；超过生效 `max_agents` 需要用户明确覆盖。
- 第 2 轮：只把主会话提炼出的分歧点发回 1 到 2 个相关子代理。
- 第 3 轮：只做决策校验，禁止开新方向。

默认上限为 `max_agents=3`、`max_rounds=3`。这些是内置默认值，不是硬编码常量。超过生效上限必须由用户明确继续。

## 配置模型

配置优先级：

```text
用户本次调用参数
> task/change 局部配置
> .cowork-flow/config.yaml 默认配置
> skill 内置默认值
```

可配置项：

- `max_agents`
- `max_rounds`
- 角色/视角 roster
- 是否生成报告
- 报告输出位置
- 是否允许第 2/第 3 轮

可收紧但不宜放松的安全闸：

- 继续条件
- 停止条件
- 超过上限需用户明确继续
- 无新增证据或未缩小范围即停止

输出 schema 的核心字段是最小必填契约。实现可以追加字段，但不能删除 `evidence`、`risk`、`acceptance_signal`、`stop_reason` 等决策所需字段。

## 继续条件

下一轮必须满足至少一项：

- 存在会改变推荐方案的重大分歧。
- 存在高风险但证据不足。
- 验收标准仍不可测。
- 子代理提出了新的文件、命令、规则或用户场景证据。
- 主会话无法写出唯一推荐方向。

## 停止条件

满足任一条件即停止：

- 已形成推荐方案、被拒方案和可测验收标准。
- 只剩用户价值取舍，继续讨论不能增加证据。
- 连续一轮没有新增证据，也没有缩小范围。
- 达到 `max_rounds`。
- 讨论跑题或输出不符合 schema，修复追问一次后仍不合格。

## 输出约束

每个子代理输出：

```text
position:
evidence:
risk:
tradeoff:
rejected_option:
acceptance_signal:
what_would_change_my_mind:
```

主会话最终输出：

```text
consensus:
disagreements:
evidence:
decision:
rejected_options:
acceptance_criteria:
open_questions:
stop_reason:
```

## 优雅性约束

- 文档以短节、明确门禁和可检索术语为主，避免口号和长段背景。
- 代码只新增必要入口，不维护第二套任务状态。
- CLI 若实现，只读写 Party Mode 报告和元数据，不调用 host 专属工具。
- root/template 资产保持同步，Claude skill mirror 按既有同步规则处理。
