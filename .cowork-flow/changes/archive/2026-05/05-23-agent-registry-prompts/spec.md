# Agent Registry Prompt and Selection Spec

## Registry parsing

- `agents.yaml` MUST support these per-agent fields:
  - `agent_type`: string
  - `capabilities`: list of strings
  - `preferred_task_types`: list of strings
  - `file_patterns`: list of glob-like strings
  - `risk_limits.max_parallel_write_conflicts`: integer
  - `prompt`: multiline string using `prompt: |`
- `codex_type` MUST NOT be parsed or treated as a fallback.
- All per-agent fields are optional; missing `capabilities`, `preferred_task_types`, `file_patterns`, `risk_limits`, or `prompt` MUST NOT fail `agent-team prepare`.
- `default_adapter` remains supported.

## Assignment selection

- The three assignment phases remain `implementer`, `spec-reviewer`, and `quality-reviewer`.
- For each phase, runtime SHOULD select the best configured agent by matching role-compatible capability/preferred task type and task files.
- If no configured agent matches, runtime MUST fall back to the phase name with default type values.
- The selected agent name and `agent_type` MUST be written to `dispatch-plan.yaml`, `status.json`, and `next` output as before.

## Prompt rendering

- If the selected agent has `prompt`, generated assignment markdown MUST include it under an `Agent prompt` section.
- Assignment prompt MUST still include role, recommended agent, agent type, task title, files, steps, and commands.
- Missing prompt is allowed and MUST not break prepare.

## Default agents

- Template `agents.yaml` MUST define common agents with practical prompts, including implementation, testing, review, documentation, debugging, and release-focused roles.
- Default active selection MUST continue to produce implementation, spec review, and quality review assignments for standard plans.
