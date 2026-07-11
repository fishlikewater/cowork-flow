# P2 拆分 FlowStore 存储与迁移边界

## Goal

降低 `.cowork-flow/scripts/flow/store.py` 的存储层复杂度，把 schema/migration、task、runtime、dashboard 等职责拆清，同时保持 SQLite schema 和公开 API 行为兼容。

## Scope

- 审计 `FlowStore` public API 和调用方。
- 提取 migration/schema helper 与 repository 边界。
- 保持现有 schema、migration dry-run/status 和 checksum 语义。
- 增强旧库/迁移/事务相关测试。
- 同步 template 实现。

## Non-Goals

- 不改变 task lifecycle 语义。
- 不做大规模 DB schema 重设计。
- 不改 dashboard UI，除非存储边界拆分暴露必须修复的问题。

## Acceptance Criteria

1. `FlowStore` public API 保持兼容，调用方无需大面积改动。
2. migration 发现、dry-run、status、checksum、失败事务有测试覆盖。
3. task/runtime/dashboard 存储职责在代码结构上更清晰。
4. root/template 同步完成。
5. 旧测试和新增测试通过。

## Relevant Files

- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/flow/migrate.py`
- `.cowork-flow/scripts/flow/migrations/`
- `.cowork-flow/scripts/flow/schema.sql`
- `tests/test_flow_store.py`
- `tests/test_flow_migrate.py`
- `tests/test_flow_migration.py`
- `tests/test_flow_script_paths.py`
- `template/.cowork-flow/scripts/flow/`

## Verification

- `.cowork-flow/run.cmd python -m pytest tests/test_flow_store.py tests/test_flow_migrate.py tests/test_flow_migration.py tests/test_flow_script_paths.py -q`
- `.cowork-flow/run.cmd flow migrate --dry-run`
- `.cowork-flow/run.cmd flow migrate --status`
- `npm run test:template`
- `git diff --check`