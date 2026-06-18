# P0-B DB Schema Versioned Migration

## Goal

引入 `schema_migrations` 表 + 编号迁移脚本机制，取代裸 `schema.sql` 的幂等 `CREATE IF NOT EXISTS`。让 schema 演进可追溯、可 dry-run、有备份回滚。

## Background

当前 `scripts/flow/schema.sql` 是单文件 `CREATE IF NOT EXISTS` 幂等。`store.py:_ensure_schema` 每次连接 executescript 整份。无版本号、无顺序迁移。`migrate.py` 是一次性脚本处理 task.json → SQLite，不是 schema 演进机制。

随着 P0-A、P1-A 等后续 task 需要修改 schema，裸文件幂等创建已不足以支撑安全演进。

## Scope

### 代码改动

1. **schema.sql**：拆分为 `scripts/flow/migrations/0001_initial.sql`（当前 schema.sql 全部内容）。
2. **新增 `schema_migrations` 表**：
   ```sql
   CREATE TABLE IF NOT EXISTS schema_migrations (
       version     INTEGER PRIMARY KEY,
       name        TEXT NOT NULL,
       applied_at  TEXT NOT NULL,
       checksum    TEXT NOT NULL
   );
   ```
3. **FlowStore.__init__ 改造**：
   - 确保 `schema_migrations` 表存在。
   - 读取已应用 version 列表。
   - 按编号顺序应用未执行迁移（每条在独立事务内 + 记录 version/name/checksum）。
   - version 跳号或 checksum 不匹配 → 报错，不启动。
4. **CLI 命令**：
   - `flow migrate`：应用所有待执行迁移。
   - `flow migrate --dry-run`：列出待执行迁移，不执行。
   - `flow migrate --status`：列出已应用迁移。
5. **迁移前自动备份**：每次应用迁移前，复制 DB 到 `.cowork-flow/.runtime/db-backup-v<version>-<timestamp>.sqlite`。

### 不改动

- 不修改现有 schema 表结构（0001_initial.sql 是纯搬运）。
- 不引入 backward migration（只 forward-only，撤销靠写新迁移）。
- 不改动 runtime 数据表（runtime_context/runtime_session 等保持不变）。

## Non-Goals

- 不实现自动 down migration（只 forward-only）。
- 不修改 `migrate.py` 的 task.json → SQLite 迁移逻辑（那是另一个用途）。
- 不一次性拆分 schema.sql 为所有历史迁移文件（0001_initial.sql 搬运全部当前 schema）。

## Acceptance Criteria

1. `schema_migrations` 表存在且有 `version/name/applied_at/checksum` 字段。
2. `FlowStore.__init__` 自动执行未应用的迁移，且每条在独立事务内。
3. `flow migrate --dry-run` 输出待执行迁移列表但不执行。
4. `flow migrate --status` 输出已应用迁移列表。
5. 已应用迁移 checksum 被篡改时，FlowStore.__init__ 报错而非静默继续。
6. 迁移前自动备份 DB 文件。
7. 失败回归测试覆盖：
   - 跳号迁移 → 报错
   - checksum 不匹配 → 报错
   - 空库初始化 → 正常应用 0001_initial
8. root/template 一致性测试通过。

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_flow_migration -v`
- `rtk npm run test:template`
- `rtk git diff --check`

## 关联

- Change: `06-15-workflow-maturity-roadmap`（P0-B）
- Plan: `2026-06-15-workflow-maturity-roadmap.md` P0-B Phase
- 上游依赖：无（可与 P0-A 实现并行）
