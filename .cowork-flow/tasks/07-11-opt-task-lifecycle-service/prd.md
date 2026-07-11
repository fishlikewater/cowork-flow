# P2 拆分任务生命周期运行时服务层

## Goal

降低 `.cowork-flow/scripts/task.py` 的职责密度，把状态迁移、pattern 校验、上下文解析和 CLI 输出边界拆成可测试服务，同时保持现有命令行为兼容。

## Scope

- 从 `task.py` 提取生命周期相关服务或 helper。
- 保持 CLI 参数、公开命令、退出码和默认输出兼容。
- 增强 lifecycle/pattern 测试。
- 同步 template 实现。

## Non-Goals

- 不改变 DB schema。
- 不改变 task status machine。
- 不在本任务中重构 FlowStore 内部存储。
- 不顺手调整用户可见流程文案，除非是拆分导致的错误修复。

## Acceptance Criteria

1. `task.py` 的核心状态迁移逻辑被提取到服务层或清晰 helper，CLI 保持薄入口。
2. start/review/complete/archive/block/unblock 和重复迁移拒绝都有行为测试。
3. pattern transition 行为保持不变。
4. root/template 代码同步。
5. 现有 task 命令 smoke check 通过。

## Relevant Files

- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/lifecycle.py`
- `.cowork-flow/scripts/patterns/base.py`
- `.cowork-flow/scripts/patterns/generic.py`
- `tests/test_lifecycle.py`
- `tests/test_patterns.py`
- `tests/test_flow_store.py`
- `template/.cowork-flow/scripts/task.py`

## Verification

- `.cowork-flow/run.cmd python -m pytest tests/test_lifecycle.py tests/test_patterns.py tests/test_flow_store.py -q`
- `.cowork-flow/run.cmd task --help`
- `.cowork-flow/run.cmd task next 07-11-opt-task-lifecycle-service`
- `npm run test:template`
- `git diff --check`