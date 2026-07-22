---
name: party-mode-v2
description: Use for runtime-controlled multi-agent board discussion where children communicate through board APIs.
---

# Party Mode V2

运行时控制的圆桌讨论，子代理通过看板 API 交流，主持人只监控和纠偏。

## 边界

- 仅提供建议，不能推进任务状态
- 不能替代 `cowork-implement` 或 `cowork-check`
- 子代理是叶子执行者，不得派发其他代理
- 主持人不转发、总结或综合子代理观点

## 命令

```bash
.cowork-flow/run party-v2 init      # 初始化讨论
.cowork-flow/run party-v2 monitor   # 监控状态
.cowork-flow/run party-v2 view      # 查看看板
.cowork-flow/run party-v2 post      # 发布观点
.cowork-flow/run party-v2 respond   # 响应观点
.cowork-flow/run party-v2 advance   # 推进轮次
.cowork-flow/run party-v2 finalize  # 结束讨论
```

## 流程

1. 初始化讨论：`party-v2 init`
2. 发布观点：`party-v2 post`
3. 响应观点：`party-v2 respond`
4. 推进轮次：`party-v2 advance`
5. 结束讨论：`party-v2 finalize`
