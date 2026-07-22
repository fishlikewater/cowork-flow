---
name: tdd
description: Use when implementing behavior changes with red-green-refactor discipline. Guides test-first development and records optional or high-risk red/green evidence in check.jsonl.
---

# TDD

在活跃 cowork-flow 任务内实践测试驱动开发。此技能不负责任务生命周期状态，使用 `cowork-flow` 进行状态管理。

## 触发条件

适用于行为、状态、协议、CLI、数据格式、权限或错误处理变更。纯文档/注释/格式工作跳过 TDD，在 `check.jsonl` 中记录验证方法。

## Red-Green-Refactor

1. 将行为映射到 `decision-anchor.md` 的验收 ID
2. 编写最小的有意义测试，因目标行为缺失或错误而失败
3. 运行测试，确认红色失败是目标行为问题，非 setup/import/环境噪音
4. 实现最小变更
5. 运行同一测试变绿，然后运行直接依赖的测试
6. 仅在行为固定为绿色后才能重构

## 证据记录

对于普通行为变更，推荐记录 red/green 证据以便审查，但不是强制要求。

对于高风险变更（协议、状态机、权限、安全、迁移、公共契约、文件格式变更），在 `<task>/check.jsonl` 中记录 `type: "tdd"` 对象：

```json
{
  "type": "tdd",
  "acceptanceId": "AC-001",
  "testFile": "tests/test_feature.py",
  "testName": "test_behavior",
  "redCommand": "pytest tests/test_feature.py::test_behavior -q",
  "redExitCode": 1,
  "redOutputExcerpt": "FAILED test_behavior - AssertionError",
  "failureReason": "Feature not implemented",
  "whyThisTestMatters": "Core acceptance criteria",
  "greenCommand": "pytest tests/test_feature.py::test_behavior -q",
  "greenExitCode": 0,
  "broaderVerification": "pytest tests/ -q"
}
```

仅文档/注释/格式工作可使用 `type: "tdd_exemption"` 记录。

## 反合理化

不要使用以下借口跳过有意义的行为测试：

| 借口 | 为何失败 | 替代方案 |
|------|----------|----------|
| "逻辑简单，不需要测试" | 简单逻辑仍会在边缘情况和后续编辑中出错 | 为验收 ID 编写最小行为测试 |
| "其他测试已覆盖" | 不可见的覆盖不是 red-green 证据 | 在 `check.jsonl` 中指向确切测试命令和验收 ID |
| "实现后补测试" | 实现后测试不是 red-green 循环 | 先红后绿；需要证据时记录两个命令 |
| "看起来正确" | 视觉检查会遗漏测试能固定的场景 | 将预期行为和边缘情况转化为断言 |
| "这只是内部行为" | 内部行为仍会影响调用方和工作流状态 | 通过公共入口测试，或直接测试窄内部契约 |
