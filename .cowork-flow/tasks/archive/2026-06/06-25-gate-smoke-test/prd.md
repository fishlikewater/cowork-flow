# workflow-gate-smoke-test

## 目标
验证子代理路径是否正确接收 delegated_subtask 状态。

## 范围
- 派发 cowok-research 子代理
- 验证子代理中 workflow-state 是否为 delegated_subtask
- 验证 before-dev skill 对 delegated_subtask 的行为

## 验收标准
- 子代理成功 bind runtime context
- 子代理报告中包含 workflow-state 信息
- gate 不阻断子代理执行

## 验证方式
子代理在 response 中报告其接收到的 workflow-state
