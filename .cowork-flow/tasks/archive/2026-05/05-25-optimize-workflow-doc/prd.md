# Optimize Workflow Documentation

## Goal

优化 `template/.cowork-flow/workflow.md` 的措辞和流程排版，使 agent 更容易按 L0 / L1 / L2 路由执行，并明确传达：只要 subagent 可用且任务适合拆分，就应优先采用 subagent 方式。

## Requirements

- 调整流程描述，使 L0、L1、L2 的路径更容易扫描。
- 压缩或移动过长的并行执行说明，避免打断主流程。
- 明确 subagent 优先原则，同时保留“不强行拆分高耦合任务”的约束。
- 修正文档任务、纯格式任务被误读为必须 TDD 的措辞。
- 不修改命令语义，不改运行时代码。

## Acceptance Criteria

- [x] `template/.cowork-flow/workflow.md` 的任务分级与执行流程排版更清晰。
- [x] 文档明确说明 subagent 可用且适合并行时优先使用 subagent。
- [x] L0 文档/格式类任务不会被表述为必须进入 TDD。
- [x] 现有门禁要求未削弱。

## Technical Notes

- 本次任务按 L0 文档修改处理。
- 只修改模板流程文档，必要时同步任务状态。
