# Lifecycle TDD Quality Gates

## Goal

Implement the architecture in `.cowork-flow/plans/2026-06-23-lifecycle-tdd-quality-gates.md`: lifecycle transitions must enforce TDD evidence, coding standards, review completeness, and agent safety through machine-readable gates instead of prompt-only instructions.

## Scope

- Add shared gate modules for quality evidence, test quality, coding standards, and agent policy.
- Add a concise TDD skill and expose it through default implementation context.
- Harden `task review` and `task complete` so missing evidence blocks state transitions.
- Keep root and `template/` runtime/docs/skill copies aligned.
- Fix the known advisory-agent safety drift in `.codex/agents/default.toml` as part of the agent-policy phase.

## Out Of Scope

- Do not add a new workflow DSL.
- Do not make git worktree double-patch replay the default gate.
- Do not reintroduce removed pattern types.

## Acceptance Criteria

- All child tasks are completed and verified.
- `task review` fails for behavior-changing work without valid red evidence.
- `task complete` fails without green evidence, coding-standard evidence, and check evidence.
- Shallow tests are rejected by a gate.
- Coding-standard violations are rejected by the completion gate.
- `doctor --subagent-safety` and `tests/test_cowork_agents.py` enforce the same advisory-agent rules.
- Root/template copies remain synchronized.
- Final integrated verification passes:
  `rtk python -m pytest tests/test_quality_gate.py tests/test_test_quality.py tests/test_coding_standards.py tests/test_flow_script_paths.py tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py -q`
  `rtk .\.cowork-flow\run.cmd doctor --subagent-safety`
  `rtk git diff --check`
  `rtk npm run test:all`

## Execution

Execute child tasks serially in phase order. Each child task must update both root and `template/` copies where applicable and leave focused tests that fail for meaningful behavior regressions.
