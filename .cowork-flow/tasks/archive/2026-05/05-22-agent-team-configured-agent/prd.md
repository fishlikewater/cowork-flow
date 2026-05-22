# Use Configured Agent-Team Registry

## Goal

Fix `agent-team prepare` so generated dispatch artifacts use `.cowork-flow/agent-team/agents.yaml` instead of hard-coded Codex adapter metadata.

## Requirements

- Read `default_adapter` from the agent-team registry when preparing runtime artifacts.
- Read role `agent_type` values from the registry for implementer, spec-reviewer, and quality-reviewer assignments.
- Preserve existing defaults when registry values are missing.
- Keep changes scoped to agent-team runtime scripts, templates, and regression tests.

## Acceptance Criteria

- [x] A customized registry changes `dispatch-plan.yaml` adapter and role `agent_type` values.
- [x] The adapter metadata file uses the configured adapter name.
- [x] `agent-team next` reports the configured role type.
- [x] Existing agent-team parser/runtime tests pass under `rtk python3`.

## Technical Notes

This is an L1 bounded behavior change in the Python agent-team runtime. Use the existing simple YAML parsing style and avoid introducing new dependencies.
