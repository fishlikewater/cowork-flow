# Spec: Manual Party Mode

## Capability: Manual Roundtable

用户可以手动请求 Party Mode，用真实子代理围绕一个问题展开有限轮次讨论。入口应支持在无活动任务时进行只读讨论，也支持在已有 change/task 上生成可归档的报告。

Success signal: 用户得到包含共识、分歧、证据、推荐决策、被拒方案、验收标准和停止原因的结论。

## Capability: Bounded Discussion

Party Mode 必须有明确默认上限、继续条件和停止条件。每轮讨论必须带来新证据、缩小范围或改变决策，否则停止。

Success signal: 报告能说明为什么继续下一轮或为什么停止。

## Capability: Configurable Defaults

Party Mode 的 `max_agents`、`max_rounds`、角色 roster、报告开关、报告位置和允许轮次应支持配置覆盖。配置优先级为本次调用参数、task/change 局部配置、`.cowork-flow/config.yaml` 默认配置、skill 内置默认值。

Success signal: 文档和测试明确 `max_agents=3`、`max_rounds=3` 是默认值而非不可变常量。

## Capability: Evidence-Based Output

每个子代理必须输出立场、证据、风险、取舍、被拒方案、验收信号和可改变其判断的条件。无证据意见不得进入最终决策。

Success signal: 最终结论可追溯到子代理输出或项目文件、命令、规则、用户场景。

## Capability: Workflow Safety

Party Mode 是 advisory workflow。它不能替代正式实现或检查，不能推进任务阶段，不能允许讨论子代理修改代码、归档、提交、启动任务或再派发代理。

Success signal: 文档和测试都明确 generic worker/advisory 输出不能满足 `cowork-implement` 或 `cowork-check` 完成条件。

## Constraints

- 保持 `.cowork-flow/spec/subagent-dispatch.md` 为正式子代理协议源。
- `workflow.md` 保持 host-neutral，不写入 `spawn_agent` 等 Codex 专属原语。
- root 与 template 下新增 skill 保持同步。
- 若新增 CLI，命令只维护报告/状态，不直接执行 host 派发。
- 继续条件、停止条件和 schema 核心字段可以被项目收紧或扩展，但不能删除。

## Non-Goals

- 不实现 BMAD 全量 agent roster。
- 不实现子代理互相聊天或子代理自协调。
- 不改变 `task start/review/complete/archive` 的状态语义。
- 不把多数共识当作验证通过。
