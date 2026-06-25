# 全流程验证

## 验证范围
真实验证 cowork-flow 在 Claude Code 上的全部关键路径，不使用逻辑推断。

## 验证矩阵

| # | 验证项 | 方法 | 预期 |
|---|--------|------|------|
| V1 | before-dev gate: no_task 阻断 | 直接要求 before-dev | 阻断写代码 |
| V2 | before-dev gate: in_progress 放行 | task start 后要求 before-dev | 放行 |
| V3 | task lifecycle: create→start→review→complete→archive | 顺序执行命令 | 全部成功 |
| V4 | cowork-research: bind + execute | 派发并检查 bind 状态 | bind 成功 |
| V5 | cowork-implement: bind + execute | 派发并检查 bind 状态 | bind 成功 |
| V6 | cowork-check: bind + execute | 派发并检查 bind 状态 | bind 成功 |
| V7 | subagent close + cleanup | close 后检查文件状态 | closed + session 删除 |
| V8 | before-dev gate: delegated_subtask 识别 | 子代理中调用 before-dev | 进入子代理分支 |
| V9 | before-dev gate: planning 阻断实现 | task create 后 start 前要求写代码 | 阻断 |
| V10 | host auto-detect | subagent init 输出 | host=claude-code |
| V11 | task next 导航 | 各阶段运行 task next | 正确下一步 |
| V12 | before-dev gate: no_task 的 ⛔ STOP | 无任务时看上下文 | STOP 块存在 |

## 验证方式
每个用例执行后记录实际输出与预期对比。
