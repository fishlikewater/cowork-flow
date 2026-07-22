---
name: party-mode
description: Use when the user requests a multi-agent roundtable for advisory discussion, option review, or risk assessment.
---

# Party Mode

协调真实子代理进行圆桌讨论，产出建议、证据、分歧和验收信号。

## 边界

- 仅提供建议，不能推进任务状态
- 不能替代 `cowork-implement` 或 `cowork-check`
- 子代理是叶子执行者，不得派发其他代理

## 配置

默认值：`max_agents=3`、`max_rounds=5`

配置优先级：调用参数 > 任务配置 > `.cowork-flow/config.yaml` > 默认值

## 流程

1. 明确问题、决策需求、范围和证据包
2. 选择最小有用的代理阵容（不超过 `max_agents`）
3. 第一轮使用新鲜子上下文，向每个子代理发送相同的问题和不同的视角
4. 综合证据支持的主张到紧凑的声明表
5. 仅在满足继续条件时继续，发送窄跟进提示
6. 停止条件满足时停止，关闭所有子代理

## 命令

```bash
.cowork-flow/run party-v2 init
.cowork-flow/run party-v2 monitor
.cowork-flow/run party-v2 view
.cowork-flow/run party-v2 post
.cowork-flow/run party-v2 respond
.cowork-flow/run party-v2 advance
.cowork-flow/run party-v2 finalize
```
