# agent-team-configured-agent Spec

## Behavior

When `.cowork-flow/agent-team/agents.yaml` contains a non-default `default_adapter` and role `agent_type` values, `agent-team prepare <task-dir> --plan <plan-file>` must:

- Write the configured adapter in `dispatch-plan.yaml`.
- Write adapter metadata to `adapters/<configured-adapter>.json`.
- Use each configured role `agent_type` in dispatch plan, status, `next` output, and assignment prompts.

## Fallback

If the registry file or a role entry is missing, existing defaults remain unchanged: adapter `codex`, implementer type `worker`, review roles type `default`.

## Non-Goals

- No new adapter execution backend.
- No general YAML parser dependency.
- No change to agent-team enabled gating.
