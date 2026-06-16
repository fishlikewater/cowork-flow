# P0-A Entry Structured Signals Host Research

## Goal

为 change `06-15-workflow-maturity-roadmap` 的 P0-A 实现提供决策依据：确定 claude-code / codex / opencode 三宿主能否稳定提供 entry 分类所需的**结构化信号**，以及这些信号能否与现有 `cowork_runtime_context_id` 共用同一传输通道。

调研结论决定 P0-A 实现 task 的方案选型：是直接用结构化信号替代文本启发式（方案 1），还是必须保留兼容期文本回退（方案 1 + 兼容期）。

## Background

当前 `common/entry_classifier.py` 用中英文关键词子串匹配判定 MAIN_SESSION/READ_ONLY/COMMAND_ONLY，confidence 取固定值。这是 fail-closed 的守门人，但判别能力脆弱（中文变体、复合句式漏判）。

change design.md 的 P0-A 方案是把 main/read-only/command 三类弱信号从 prompt 文本迁移到宿主结构化元数据，但前提是"宿主侧可获取"。这个前提是否成立、在三个宿主分别如何成立，正是本调研要回答的。

## Scope

只读调研，覆盖三宿主：

1. **claude-code**：`.claude/hooks` 能否在注入 workflow state 前拿到 session role / invocation kind；hook input 是否暴露这些字段。
2. **codex**：`.codex` 适配器在派发/注入时能否拿到 thread/session 元数据；codex 的 session context（已有 `CODEX_SESSION_ID`/`CODEX_THREAD_ID`）是否携带 role 信号。
3. **opencode**：`.opencode` 适配器的 session context（已有 `OPENCODE_SESSION_ID`）能否提供 role/invocation 信号。

每个宿主回答四个问题：
- 能否稳定提供 `session_role`（main / subagent / command）？
- 能否稳定提供 `invocation_kind`（interactive / command_wrapper / hook / read_only）？
- 信号注入通道（env / metadata / prompt）是什么？是否与 `cowork_runtime_context_id` 同通道？
- 若无法稳定提供，兜底方案是什么（fail-closed UNKNOWN 还是兼容期文本回退）？

## Non-Goals

- 不改任何代码、spec、adapter.yaml、config.yaml。
- 不实现 P0-A（那是后续实现 task）。
- 不评估 runtime_context_id binding 强信号（那条已经稳定，不在调研范围）。
- 不做 P0-B schema 版本化调研。

## Deliverables

调研报告，落在任务目录下：

- `research/host-signals-report.md`：三宿主能力表 + 证据（hook 文档/适配器代码行号引用）+ 方案选型建议。

报告必须包含：

1. **能力矩阵**：三宿主 × 两信号（session_role / invocation_kind）× 可获取性（稳定 / 部分 / 不可）。
2. **证据**：每个"稳定/部分"结论附宿主资产引用（文件:行号 或 文档链接）。
3. **方案选型建议**：基于能力矩阵，建议 P0-A 实现选"结构化信号优先 + 哪些宿主需兼容期文本回退"。
4. **风险**：列出信号获取在哪些场景不稳定（如宿主升级、hook 时序、背景会话）。

## Acceptance Criteria

1. 三宿主均有明确结论（稳定 / 部分 / 不可），无遗漏。
2. 每个"稳定/部分"结论有可核验证据（文件路径 + 行号，或宿主官方文档链接）。
3. 给出 P0-A 实现的方案选型建议，并说明依据。
4. 报告识别出至少一个"信号获取不稳定"的具体场景（用于后续失败回归测试设计）。
5. 调研范围严格限定在只读，未改动任何项目文件（`git status` 干净）。

## Verification

- 调研报告存在且结构完整（四个必备章节）。
- 报告引用的证据路径可在仓库中核验（文件存在、行号有效）。
- `git status --short` 显示调研期间未产生任何代码/spec/adapter 改动。
- 报告结论被主会话 review 接受后，task 可推进到 review。

## 关联

- Change: `06-15-workflow-maturity-roadmap`（P0-A）
- Plan: `2026-06-15-workflow-maturity-roadmap.md` Step 1
- 上游问题：change design.md "Open Questions" 第 1 条
