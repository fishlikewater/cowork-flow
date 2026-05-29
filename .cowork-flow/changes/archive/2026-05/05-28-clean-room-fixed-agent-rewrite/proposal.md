# 05-28-clean-room-fixed-agent-rewrite

## 背景

当前项目借鉴了 公开工作流思路，但实现上仍以 `agent-team` 为中心，存在上下文边界重、状态机复杂、子 agent 可能误入主流程的问题。

## 目标

把 cowork-flow 重新组织成一个 clean-room 的 fixed-agent 工作流：

- 主线变成 `task -> prd -> context -> implement -> check -> finish`
- 子 agent 固定为 `research / implement / check`
- 上下文注入改为按 task path 自加载，而不是依赖复杂调度状态
- 删除不符合新模型的旧实现，而不是长期保留兼容层

## 范围

会涉及：

- `.cowork-flow/workflow.md`
- `.cowork-flow/scripts/`
- `.agent/skills/` 与 `template/.agent/skills/`
- 任务上下文、session 记录、恢复入口
- 测试与模板同步

## 不做的事

- 不复制 外部项目源码
- 不引入 `.current-task` fallback
- 不保留双轨上下文模型
- 不把旧 agent-team 状态机当作默认主路径

## 成功标准

- 子 agent 不会误入 coordinator 流程
- 当前任务由 session-scoped 状态管理
- 子 agent 通过 task path 自加载上下文
- 旧的、与新模型冲突的实现可以删除
- 现有测试与模板能反映新流程
