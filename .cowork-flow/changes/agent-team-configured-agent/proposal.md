# agent-team-configured-agent

## Problem

`agent-team prepare` built dispatch artifacts with hard-coded Codex adapter metadata. Projects that customize `.cowork-flow/agent-team/agents.yaml` could not affect generated assignments.

## Proposed Change

Read `.cowork-flow/agent-team/agents.yaml` when preparing runtime artifacts. Use `default_adapter` for the dispatch adapter and each role's `agent_type`, while preserving existing Codex defaults when configuration is missing.

## Scope

- Update the agent-team runtime helper and prepare command.
- Add regression coverage for customized registry values.
- Keep the existing simple YAML parsing style and avoid new dependencies.
