# 决策锚点：上下文渲染复杂度收口

## 背景

正式版提示面已完成多轮清理，剩余 review/complete 复杂度 warning 主要集中在上下文渲染函数，属于维护噪音而非行为缺陷。

## 目标

- 拆分 `execution_context.py` 与 `git_context.py` 中剩余超长上下文渲染函数。
- 保持 worker/subagent resume 文本与 git context 输出行为不变。
- 降低复杂度门禁 warning 噪音，避免后续真实问题被淹没。

## 非目标

- 不改 workflow 状态机语义。
- 不引入兼容期或旧术语回退。
- 不扩大到无关运行时重构。

## 验收标准

- 聚焦测试通过。
- 复杂度门禁不再报告本任务目标函数。
- `npm run test:all` 通过。
