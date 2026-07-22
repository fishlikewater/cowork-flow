---
name: tdd
description: Use for behavior_change or bugfix tasks to produce valid quality.json evidence before implementation.
---

# TDD

用于 `workType: behavior_change` 或 `bugfix` 任务。生命周期状态转换（`task review`、`task complete`）强制合规。

## 流程

1. **读取任务** — PRD 验收标准定义测试必须证明的内容
2. **编写 testPlan** — `quality.json` 中每个验收点一个条目：
   ```json
   {
     "workType": "behavior_change",
     "testPlan": [
       {
         "acceptancePoint": "task creation returns valid ID",
         "testCommand": "pytest tests/test_task.py::test_creates_valid_id -q",
         "expectedResult": "exit 0"
       }
     ]
   }
   ```
3. **先写失败测试** — 在实现之前编写测试并确认失败
4. **实现** — 编写最小代码使测试通过
5. **验证** — 确认所有测试通过

## 原则

- 测试应表达业务意图，而非仅覆盖表面输出
- 禁止编写无意义的简单测试（如只断言函数存在）
- 测试应能在关键逻辑被破坏时失败
