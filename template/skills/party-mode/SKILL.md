---
name: party-mode
description: Use when the user requests a multi-agent roundtable for advisory discussion, option review, or risk assessment.
---

# Party Mode

协调真实子代理进行圆桌讨论。仅提供建议，不能推进任务状态或替代 `cowork-implement`/`cowork-check`。

## 配置

- 默认：`max_agents=3`、`max_rounds=5`
- 配置优先级：调用参数 > 任务配置 > `.cowork-flow/config.yaml` > 默认值
- 安全门禁：继续/停止条件只能收紧不能移除，超出限制需用户明确批准

## 轮次模型

1. 明确问题、决策需求、范围和证据包
2. 选择最小有用代理阵容，记录选择理由
3. 第一轮使用新鲜子上下文，子代理互不可见
4. 综合证据主张到声明表：`claim_id`、owner、claim、evidence、counterclaim、evidence gap、decision impact
5. 满足继续条件时才继续，发送窄跟进提示绑定到 `claim_id`
6. 挑战轮默认立场：审视，先测试对立主张
7. 停止条件满足时关闭所有子代理

## 轮次意图

- Round 1 = 独立首轮判断
- Round 2+ = 挑战（存在分歧、风险、证据缺失时）
- 收敛轮 = 仅验证、收窄或选择，不开启新方向

## 继续条件（至少满足其一）

- 分歧可能改变推荐决策
- 高风险缺乏足够证据
- 验收标准仍不可测试
- 子代理发现新证据
- 协调器无法写出单一推荐方向

## 边界

- 子代理是叶子执行者，不得派发/等待/列出/关闭其他代理
- `worker`/`default`/`explorer` 代理仅提供建议视图
