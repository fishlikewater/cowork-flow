# Workflow Maturity Roadmap Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** 在保持 runtime-context binding + fail-closed + 单一写入这套安全内核的前提下，收敛概念密度、消除重叠数据模型、降低安全链脆弱性，对低使用率子系统做去留决策。
**Architecture:** 按 P0-P4 分期推进；每期一个 task，独立 PRD 与验收。P1 依赖 P0 的 schema 版本化；P2 依赖 P1 的文档分层；P3/P4 相对独立。不在单期内同时改安全模型和数据模型。
**Verification:** 每期失败回归测试优先（AGENTS.md 第 8 条）；安全链测试必须能 fail-closed；root/template 一致性测试 `npm run test:template` 每期收口必须通过；容器 change 在所有分期验收通过后 archive。
**Status:** planning。本期仅推进 P0-A 的调研 task。

Execution strategy: serial across phases（P0 → P1 → P2 → P3 → P4），serial within each phase（每期单 task）。理由：安全链、数据模型、文档结构之间存在状态契约依赖，串行集成比并行更可控。

## 关联

- Change: `06-15-workflow-maturity-roadmap`
- Spec 契约点见 change 的 `spec.md` 契约版本总览表。

## Phases Overview

| Phase | Task slug | Status | 说明 |
| --- | --- | --- | --- |
| P0-A | `entry-structured-signals-research` | planning | 三宿主结构化信号获取调研（本期） |
| P0-A | `entry-structured-signals` | not started | 调研结论后的实现 task |
| P0-B | `db-schema-versioning` | not started | schema_migrations + 编号迁移 |
| P1-A | `runtime-agent-run-convergence` | not started | runtime_context/agent_run 收敛 |
| P1-B | `spec-three-layer` | not started | spec 三层分层 |
| P1-C | `registry-readwhen-enforcement` | not started | readWhen 强制化 |
| P2-A | `pattern-engine-review` | not started | pattern 使用率盘点与去留 |
| P2-B | `party-mode-positioning` | not started | Party Mode 定位决策 |
| P3-A | `runtime-coordination-sink` | not started | 机械协调下沉 runtime |
| P3-B | `doc-language-unification` | not started | spec 语言统一 |
| P4 | `dashboard-observability` | not started | 时间线/失败归因/readiness 通过率 |

## P0-A Phase（本期）

### Step 1 — 三宿主结构化信号获取调研

- [ ] Task: `entry-structured-signals-research`
- 交付物：调研报告，含三宿主（claude-code/codex/opencode）能力表
  - 各宿主能否稳定提供 `session_role`（main/subagent/command）。
  - 各宿主能否稳定提供 `invocation_kind`（interactive/command_wrapper/hook/read_only）。
  - 信号注入通道（env / metadata / prompt）与 runtime_context_id 同通道的可行性。
- 决策输出：P0-A 实现选方案 1（结构化信号优先 + 兜底）还是保留兼容期文本回退。
- 范围边界：只读调研，不改代码、不改 spec、不改 adapter.yaml。
- Verify: 调研报告被 review 接受；报告含每个宿主的可获取性结论与证据（hook 文档引用 / 适配器代码引用）。

### Step 2 — P0-A 实现（调研通过后另开 task）

- [ ] Task: `entry-structured-signals`（待 Step 1 review 后 create）
- 内容见 change `design.md` P0-A 节：adapter.yaml 加 entrySignals、entry_classifier 改造、兼容期开关、失败回归测试。
- Verify: 见 design.md P0-A 验证节。

## 后续 Phases（待 P0 完成后展开）

每个 Phase 启动前，在本 plan 追加该 Phase 的 Steps 细节，并 `task create` 对应 task。当前仅占位，避免提前展开未确定细节。

### P0-B（依赖：无，可与 P0-A 实现并行）

- [ ] schema_migrations 表 + migrations 目录
- [ ] FlowStore 启动逻辑改造
- [ ] CLI migrate --dry-run/--status
- 细节见 design.md P0-B。

### P1-A（依赖：P0-B schema 版本化）

- [ ] 基线调研：列出所有读 agent_run 的调用方
- [ ] 选方案 1 或方案 2
- [ ] 实现 + 基线一致性测试
- 细节见 design.md P1-A。

### P1-B / P1-C / P2-A / P2-B / P3-A / P3-B / P4

- 细节见 change `design.md` 对应章节；启动时展开 Steps。

## Risks（摘自 change proposal）

- 分期跨度大、中途漂移：每期独立 PRD + 独立验收；容器 change 只在所有分期验收通过后 archive。
- 安全链改造保护空窗：保留旧 classifier 作为 fallback，空窗期 fail-closed 仍生效。
- DB schema 迁移破坏旧库：每步可 dry-run、有备份、CI 跑旧库样本。
- pattern/Party Mode 去留争议：基于使用率数据，design.md 记录被拒方案。

## Open Questions（摘自 change design，推进时解决）

- P0-A 结构化信号在三宿主各自怎么获取？→ 本期 Step 1 调研解决。
- P1-A 选方案 1 还是方案 2？→ P1-A task 启动时基线调研后定。
- P2 使用率阈值？→ P2 task 启动时出原始数据后在 design review 定。
