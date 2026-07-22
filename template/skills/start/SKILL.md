---
name: start
description: Use when starting or resuming main-session work in a cowork-flow project, after context compression, or before repository changes.
---

# Start

主会话启动入口。子代理在 runtime context 绑定后才进入正式执行，不得加载此启动流。

## 加载状态

1. 读取 `AGENTS.md`
2. 读取 `.cowork-flow/workflow.md`
3. 运行 `./.cowork-flow/run resume` 获取当前任务状态
4. 如有活跃任务，读取任务 PRD 和 JSONL 索引

报告：当前任务、工作流阶段、阻塞项、下一步。

## 路由

根据请求类型路由：

| 请求类型 | 路由 |
|----------|------|
| 只读问题 | 直接回答 |
| 小改动（目标/范围/验收清晰） | 创建/启动任务 → 直接执行 |
| 需求不清晰、多方案、行为变更 | `brainstorming` |
| 多步骤实现 | `writing-plans` → 派发固定代理 |
| 编码前 | `before-dev` |
| 实现完成后 | `check` → `finish-work` |

## 固定代理

主会话负责协调：

- **调研**: 派发 `cowork-research`
- **实现**: 派发 `cowork-implement`
- **验证**: 派发 `cowork-check`

每次正式派发使用 runtime-context 协议：

```text
cowork_runtime_context_id: <runtime_context_id>
cowork_host_context_key: <host_context_key>
```

派发前创建 runtime context：`./.cowork-flow/run subagent init`

子代理第一步绑定：`./.cowork-flow/run subagent bind <id> <key>`

父会话验证 `status=bound` 后才接受输出。
