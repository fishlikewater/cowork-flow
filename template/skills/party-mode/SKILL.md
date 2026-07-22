---
name: party-mode
description: Use when the user requests a multi-agent roundtable for advisory discussion, option review, or risk assessment.
---

# Party Mode

协调真实子代理进行圆桌讨论。Python 运行时是讨论状态、看板可见性、验证、轮次上限和最终报告的权威来源。

## 边界

- 仅提供建议，不能推进任务状态
- 不能替代 `cowork-implement`/`cowork-check`
- 子代理是叶子执行者，不得派发/等待/列出/关闭其他代理
- 主持人不转发、总结、重写或综合子代理观点
- 不得绕过运行时拒绝手动接受子代理输出

## 命令

```bash
.cowork-flow/run party-v2 init       # 初始化讨论
.cowork-flow/run party-v2 monitor    # 监控状态
.cowork-flow/run party-v2 view       # 查看看板
.cowork-flow/run party-v2 post       # 发布观点
.cowork-flow/run party-v2 respond    # 响应观点
.cowork-flow/run party-v2 advance    # 推进轮次
.cowork-flow/run party-v2 record-action-result  # 记录行动结果
.cowork-flow/run party-v2 finalize   # 结束讨论
```

## 看板规则

- 子代理通过看板 API 交流
- 子代理可见输出仅限当前轮
- 历史看板状态为运行时私有，仅用于审计或最终报告
- 至少使用 3 个子代理，除非运行时配置明确允许不同值
- 运行时发出主机中立的下一步操作，由活动主机适配器或主持人执行
- 主机行动结果必须通过 `record-action-result` 记录回写

## 子代理响应规则

看到不同立场时，必须选择其一：`maintain`、`revise`、`concede`

- `concede`：需提供接受的证据和原立场失败原因
- `revise`：需提供接受部分、拒绝部分和更新后的立场
- `maintain`：需提供反证据或反推理

模糊修订和无证据反驳无效。

## 主持人职责

可以：运行运行时命令、通过主机执行操作、记录离题警告、关闭子代理（运行时要求时）、展示状态或报告

不得：转发表子代理观点、创建声明表、投票计数决定正确性

## 配置

- 默认：`max_agents=3`、`max_rounds=5`
- 配置优先级：调用参数 > 任务配置 > `.cowork-flow/config.yaml` > 默认值
- 安全门禁：继续/停止条件只能收紧不能移除，超出限制需用户明确批准
