---
name: tdd
description: Use for behavior_change or bugfix tasks to produce valid quality.json evidence before implementation.
---

# TDD

用于 `workType: behavior_change` 或 `bugfix` 任务。`task review`/`task complete` 强制合规。

## 流程

1. **读取任务** — PRD 验收标准定义测试必须证明的内容
2. **编写 testPlan** — `quality.json` 中每个验收点一个条目：
   ```json
   {
     "workType": "behavior_change",
     "testPlan": [{
       "acceptancePoint": "task creation returns valid ID",
       "testCommand": "pytest tests/test_task.py::test_creates_valid_id -q",
       "breaksWhen": "function returns None or empty string instead of a UUID"
     }]
   }
   ```
3. **记录 red 证据** — 实现前运行测试，记录失败输出：
   ```json
   "red": {
     "command": "pytest tests/test_task.py::test_creates_valid_id -q",
     "exitCode": 1,
     "failingTests": ["test_creates_valid_id"],
     "outputExcerpt": "FAILED ..."
   }
   ```
   red `exitCode` **绝不能**为 0
4. **实现** — 编写最小代码使测试通过
5. **记录 green 证据** — 再次运行同一命令族：
   ```json
   "green": {
     "command": "pytest tests/test_task.py::test_creates_valid_id -q",
     "exitCode": 0,
     "passingTests": ["test_creates_valid_id"],
     "outputExcerpt": "1 passed in 0.05s"
   }
   ```

## 拒绝浅层测试

以下测试不证明行为，将被生命周期门禁阻止：

- `assert True` / `assertTrue(True)` / `expect(true).toBe(true)`
- 空快照或无断言快照
- 仅存在性测试：`def test_exists(): pass`
- 仅 mock 调用断言，无可观察行为
- 逐字复制生产代码的断言

## 约束

- 证据必须记录为**命令输出**，非自由文本声明
- `refactor_no_behavior_change`：在 `testPlan` 中记录验证当前行为的现有测试，无需 red-first
- `docs_chore`：不需要 TDD 证据，完成时仍需 `standards` 和 `check` 证据
