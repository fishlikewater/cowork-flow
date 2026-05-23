# Clarify parallel agent workflow

## Goal

澄清 `.cowork-flow/workflow.md` 中 L1/L2 plan 执行阶段关于 agent-team / subagent 的使用条件，避免把并行执行误读为强制步骤。

## Requirements

- 明确先判断是否存在可安全并行的独立任务。
- 明确 `agent_team.enabled` 只决定使用哪种并行机制，不决定是否必须并行。
- 明确不适合并行时应说明理由并顺序执行。
- 明确不得为了满足流程形式强行拆分高耦合任务。
- 当前 `.cowork-flow/workflow.md` 与模板 `template/.cowork-flow/workflow.md` 保持一致。

## Acceptance Criteria

- [x] 两份 workflow 文档都包含并行适用/不适用条件。
- [x] 两份 workflow 文档都说明不适合并行时顺序执行并记录理由。
- [x] 文档测试通过。

## Technical Notes

- 分级：L0 文档澄清。
- 不修改运行时代码。
