
# Post-roadmap hardening follow-up

## 背景

2026-07-11 workflow optimization roadmap 已完成并归档。最终复扫确认当前运行时文档已经清理旧状态权威表述，`doctor --release-health` 与 `doctor --subagent-safety` 也通过。

剩余风险不是功能缺口，而是三类维护体验问题：

1. `FLOW-UPGRADE-DESIGN.md` 仍包含迁移期的 `task.json` 与 `.runtime/subagents` 叙述。内容本身可以保留，但需要明确标注为历史设计/迁移背景，避免读者误当成当前运行时契约。
2. `src/lib/template-sync-gate.js` 中仍有 legacy flattened path allowlist。部分条目可能仍是有意的历史兼容，部分可能已可收窄；需要用测试固定“哪些允许、为什么允许”。
3. `07-11-opt-baseline-risk-map` 在任务列表中仍为 `completed`，而同一路线图其它任务已 `archived`。这不影响功能，但影响维护者快速判断路线图收口状态。

## 目标

用 3 个小任务完成 post-roadmap hardening：

- 给历史设计文档加明确边界，避免旧状态描述与当前 DB runtime authority 冲突。
- 审查并收窄 template sync legacy allowlist，让剩余例外都有测试和说明。
- 统一 07-11 路线图任务归档状态，消除 completed/archived 混合带来的视觉噪音。


## 用户价值

- 维护者可以快速分辨历史迁移设计和当前运行时契约，减少错误引用旧状态文件的风险。
- template sync gate 的 legacy 例外会变成可审查、可测试的契约，而不是长期积累的模糊豁免。
- 07-11 路线图收口状态更一致，后续恢复或审计时不需要额外解释为什么还有 completed 任务残留。

## 关键假设

- 07-11 workflow optimization roadmap 已完成并归档，当前工作只做后续 hardening。
- DB `runtime_session` / `runtime_context` 仍是当前运行时权威，不新增第二套状态。
- 三个 follow-up 任务可以串行执行，并分别独立验证。

## 非目标

- 不重新设计 DB runtime authority、runtime context binding 或 fail-closed 机制。
- 不删除历史设计材料中的迁移细节，除非它被证明已误导当前文档。
- 不重写 template sync gate；只做 allowlist 级别的收窄和测试补强。
- 不展开新的大规模 roadmap。

## 验收标准

- 历史设计文档顶部明确说明“历史/迁移设计”，并指向当前权威文档。
- 当前运行时文档仍不引用旧 `.runtime/subagents`、`.runtime/sessions` 或旧 state-template 路径作为权威。
- template sync legacy allowlist 的每个保留条目都有理由和测试覆盖；可删除条目已删除。
- 07-11 路线图任务状态展示一致，active task 仍为空。
- 每个任务都有 PRD、implement/check 上下文、验证命令和归档收口路径。
