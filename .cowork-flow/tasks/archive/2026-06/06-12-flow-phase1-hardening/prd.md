# Harden Flow Phase 1 Implementation

## Goal

修复 Flow Phase 1 已实现代码中的可靠性问题，并同步优化 `FLOW-UPGRADE-DESIGN.md`，使设计文档、SQLite store、迁移脚本、task CLI、hook 查询和 template 分发保持一致。

## Scope

- 修复 `FlowStore` 事务、读取、block/unblock 状态语义。
- 修复 `flow/migrate.py` 整体事务、父子关系迁移和失败回滚。
- 修复 `task.py` 生命周期命令的 FlowStore 写入一致性与错误返回。
- 修复 workflow-state hook 对 Flow-only 任务状态的查询。
- 同步 root/template 运行时文件。
- 更新 `FLOW-UPGRADE-DESIGN.md` 中 Phase 1 契约、风险和验收。
- 补充能证明真实回归路径的测试。

## Non-Goals

- 不实现 Phase 2 pattern engine。
- 不实现 Dashboard UI 或 subagent family 命令。
- 不重构无关 workflow、Party Mode 或 host adapter 行为。
- 不清理本任务之外的既有未提交改动。

## Acceptance Criteria

1. `FlowStore` 在 `IntegrityError` 后会 rollback，同一个连接仍可继续写入。
2. `task create --parent` 成功创建子任务且只生成一条父子关系，不抛重复主键错误。
3. `flow.migrate.run_migration()` 对有效父子关系不受目录排序影响；任一硬失败不得留下部分已迁移数据。
4. `unblock_task()` 在没有 active block 时返回失败，不改变任务状态，不写虚假 audit。
5. Hook 对只有 SQLite 记录、没有 `task.json` 的 active task 返回 FlowStore 中的真实状态，而不是 `stale`。
6. `review/complete/block/unblock/archive` 等生命周期命令遇到缺失 DB 行或 DB 更新失败时返回非零或明确失败，不静默成功。
7. `board_view()` 不使用写事务锁。
8. root/template 相关 runtime 文件保持同步。
9. `FLOW-UPGRADE-DESIGN.md` 与实际 `flow/` 路径、事务模型、迁移策略和 Phase 1 gate 一致。

## Relevant Files

- `FLOW-UPGRADE-DESIGN.md`
- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/flow/migrate.py`
- `.cowork-flow/scripts/flow/schema.sql`
- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/inject_workflow_state.py`
- `template/.cowork-flow/scripts/flow/store.py`
- `template/.cowork-flow/scripts/flow/migrate.py`
- `template/.cowork-flow/scripts/flow/schema.sql`
- `template/.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/common/inject_workflow_state.py`
- `tests/test_flow_store.py`
- `tests/test_flow_migrate.py`
- `tests/test_flow_script_paths.py`
- `tests/test_codex_hooks.py`
- `tests/test_claude_hooks.py`

## Verification

```powershell
python -m pytest tests/test_flow_store.py tests/test_flow_migrate.py tests/test_flow_script_paths.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q
npm run test:all
git diff --check
```
