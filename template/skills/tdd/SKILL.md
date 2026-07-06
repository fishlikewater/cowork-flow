---
name: tdd
description: Use when implementing behavior changes, bug fixes, state transitions, protocols, CLI/runtime contracts, data format changes, or error handling that can be tested before implementation.
---

# TDD

Use this before editing behavior-changing code.

## Red-Green-Refactor

1. Map the task PRD acceptance criteria to stable IDs such as `AC-001`.
2. Write the smallest meaningful failing test first.
3. Run the red command and confirm it fails because the target behavior is missing or wrong.
4. Implement the smallest change that makes the behavior pass.
5. Run the green command and relevant broader verification.
6. Refactor only after the behavior is green.

Do not count shallow tests as TDD evidence. Tests that only import code, assert a function exists, assert `True`, count mocks without behavior, or mirror implementation details do not satisfy red-green-refactor.

## Evidence

Record TDD proof in `<task>/tdd.jsonl`. Each evidence line is one JSON object:

```json
{
  "acceptanceId": "AC-001",
  "testFile": "tests/test_example.py",
  "testName": "test_behavior",
  "redCommand": "python -m unittest tests.test_example.TestCase.test_behavior -v",
  "redExitCode": 1,
  "redOutputExcerpt": "expected failure excerpt",
  "failureReason": "target behavior was not implemented",
  "whyThisTestMatters": "explains which user-visible behavior would regress",
  "greenCommand": "python -m unittest tests.test_example.TestCase.test_behavior -v",
  "greenExitCode": 0,
  "broaderVerification": "python -m unittest tests.test_example -v"
}
```

Every evidence record must map to a PRD `acceptanceId`. The red failure must be about the target behavior, not syntax, import, environment, fixture, or setup failure.

`testName` must resolve to the exact behavior test in `testFile`. Use one of:
`test_method`, `ClassName.test_method`, or `module.ClassName.test_method`.
Do not point evidence at a class, module, or a name that only exists in a command string.

## Exemption

Pure documentation, comment-only, or formatting-only tasks may use an exemption record instead of red/green evidence:

```json
{
  "type": "exemption",
  "acceptanceId": "AC-001",
  "exemptionType": "docs-only",
  "reason": "Only documentation wording changed; runtime behavior is untouched.",
  "verificationCommand": "git diff --check"
}
```

Do not use an exemption for runtime, CLI, protocol, state, data format, permission, or error-handling changes.

## Anti-Rationalization

> 以下借口不能免除 TDD 证据要求。每条都对应一个可执行的替代方案。

| Agent 心理 | 反驳 | 替代方案 |
|---|---|---|
| "这个逻辑很简单，不需要测试" | 简单逻辑也会因边界条件和后续修改出错。简单不是免除证据的理由。 | 写一个断言核心行为的覆盖测试，耗时 < 2 分钟 |
| "其他测试已经覆盖了" | "已经覆盖"无法从 tdd.jsonl 证据中验证。看不见的证据 = 不存在。 | 在 tdd.jsonl 中能直接定位到对应的 acceptanceId 和 redCommand |
| "我会在实现之后补测试" | 实现后补的测试不是红绿循环——它验证的是实现，不是行为。 | 先 red，再 green，证据留在 tdd.jsonl |
| "肉眼可以看出正确" | 肉眼能看出的错误不会成为 bug。能成为 bug 的都是"看起来正确"的场景。 | 将"看起来正确"的输入变成断言，将"意外输入"变成边界测试 |
| "写过类似的测试，模式一样" | 模式一样不等于行为一样。每个 acceptanceId 的证据必须是独立的。 | 为当前 acceptanceId 重新运行 redCommand 并记录输出 |
| "这是内部函数，外部不可见" | 内部函数也会被其他内部调用者依赖。行为变化通过调用链传播。 | 通过调用它的公共入口写测试，或直接测内部函数 |
