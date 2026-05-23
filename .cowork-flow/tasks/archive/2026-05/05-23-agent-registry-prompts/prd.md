# Agent registry prompts

## Goal

让 `agents.yaml` 中的 agent 配置真正影响 agent-team 运行时，支持自定义 prompt，并移除 `codex_type` 兼容字段。

## Requirements

- `agents.yaml` 支持并消费 `agent_type`、`capabilities`、`preferred_task_types`、`file_patterns`、`risk_limits`、`prompt`。
- `prompt: |` 多行文本应进入生成的 assignment markdown。
- agent-team prepare 应按配置选择更匹配的 agent，而不是永远使用固定 role 名。
- `codex_type` 不再被解析或作为 fallback。
- agent 字段都应是可选增强项，未配置时不应报错。
- 默认 agents.yaml 提供一组通用 agent 和配套 prompt。
- 模板文件和当前项目文件保持一致。

## Acceptance Criteria

- [x] 自定义 agent prompt 会出现在 `agent-team/assignments/*.md`。
- [x] 自定义 agent 可通过 capabilities / preferred_task_types / file_patterns 被选中。
- [x] 只有 `codex_type`、没有 `agent_type` 的配置不会改变 agent type。
- [x] 缺少 `capabilities`、`preferred_task_types`、`file_patterns`、`risk_limits`、`prompt` 时 prepare 仍成功。
- [x] 默认 `agents.yaml` 含通用 agents 和 prompt。
- [x] agent-team 相关 unittest 通过。

## Technical Notes

- 分级：L1。
- Change: `.cowork-flow/changes/05-23-agent-registry-prompts/`。
- Plan: `.cowork-flow/plans/2026-05-23-agent-registry-prompts.md`。
