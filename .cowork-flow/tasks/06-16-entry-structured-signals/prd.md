# P0-A Implement Structured Entry Signals with Compat Fallback

## Goal

将 `entry_classifier.py` 从纯关键词文本启发式改造为"结构化信号优先 + 兼容期文本兜底"的双通道分类器。adapter.yaml 新增 `entrySignals` 段声明宿主可提供的结构化信号键；entry_classifier 优先读结构化信号，缺失时走 `_legacy_text_fallback`（兼容期默认启用，config 开关控制）。

## Background

调研结论：三宿主（claude-code/codex/opencode）均无法稳定提供 `session_role` 和 `invocation_kind`。唯一可获取的近似信号：
- claude-code: `hook_event_name`（UserPromptSubmit/SessionStart）
- codex: `dispatch_mode`（仅 sub-agent 场景有意义）
- opencode: 无（需后续 plugin 改造）

因此 P0-A 不能做"一刀切"的结构化信号迁移，必须保留兼容期文本回退，直到三宿主全部提供可用的结构化信号。

## Scope

### 代码改动

1. **adapter.yaml**：新增 `entrySignals` 段，声明宿主可提供的 entry 信号键。
   - 三宿主各一份：`.cowork-flow/adapters/claude-code/adapter.yaml`、`codex/`、`opencode/`
   - claude-code: `{sessionRole: null, invocationKind: hook_event_name}`
   - codex: `{sessionRole: null, invocationKind: dispatch_mode}`
   - opencode: `{}`（空，暂无法提供）

2. **entry_classifier.py**：改造 `classify_entry()` 为双通道：
   - 通道 1（结构化信号）：从 hook_input 中提取 adapter.yaml 声明的信号键值。
   - 通道 2（兼容期文本回退）：保留旧版 `_legacy_text_fallback` 函数，默认启用。
   - 优先级：结构化信号 > fallback > UNKNOWN。

3. **config.yaml**：新增 `entry.legacy_text_fallback.enabled: true/false` 开关。

4. **entry_contract.md**：更新为 V2，描述双通道分类顺序。

### 不改动

- `subagent-dispatch.md`（runtime-context binding 协议不变）
- `workflow.md`（流程不变，只是 entry classifier 内部逻辑变了）
- 宿主适配器代码（hook/plugin 不需要改，adapter.yaml 只声明能力）
- P0-B schema 版本化（独立 task）

## Non-Goals

- 不实现 opencode plugin 结构化信号注入（P0-A 后延期处理，见报告 Section 3）。
- 不删除旧 `entry_classifier.py` 的词表（兼容期保留，后续 P3-B 语言统一时清理）。
- 不改动 `subagent-dispatch.md` 或 runtime-context binding 协议。
- 不一次性改造所有 spec 文档（spec 分层是 P1-B 的范围）。

## Acceptance Criteria

1. `classify_entry()` 在有结构化信号时返回对应 EntryKind，confidence ≥ 0.9。
2. 结构化信号缺失时，fallback 启用 → 走旧文本分类逻辑；fallback 禁用 → 返回 UNKNOWN。
3. `config.yaml` 新增 `entry.legacy_text_fallback.enabled`，默认 `true`。
4. 三宿主 adapter.yaml 均含 `entrySignals` 段，claude-code 和 codex 声明近似信号键。
5. 失败回归测试覆盖 4 个不稳定场景（见调研报告 Section 4）：
   - 空 input → UNKNOWN
   - 信号冲突 → 按结构化信号分类
   - fallback 禁用 + 无信号 → UNKNOWN（非 MAIN_SESSION）
   - opencode 无信号 → fallback 或 UNKNOWN
6. `entry-contract.md` 更新为 V2，描述双通道分类顺序。
7. root/template 一致性测试通过。

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_entry_classifier -v`
- `rtk npm run test:template`
- `rtk git diff --check`

## 关联

- Change: `06-15-workflow-maturity-roadmap`（P0-A 实现）
- Plan: `2026-06-15-workflow-maturity-roadmap.md` Step 2
- 上游调研：`06-16-entry-structured-signals-research/research/host-signals-report.md`
