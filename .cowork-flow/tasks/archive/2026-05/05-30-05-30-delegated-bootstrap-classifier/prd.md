# Harden delegated bootstrap classification

## Goal

Keep project rules visible to subagents while preventing bootstrap, no-task workflow hints, or start/resume guidance from becoming the subagent's task when the delegated prompt has no hard marker.

## Assumptions

- A delegated prompt may not start with `COWORK_*` or another hard token.
- Project rules should still be available as constraints inside subagent context.
- The fix should stay lightweight: no new assignment ledger, outbox, or heavy runtime state.
- Main-session requests must still receive normal workflow-state guidance.

## Scope

- Update delegated prompt classification guidance in `AGENTS.md`, `template/AGENTS.md`, `.agent/skills/entry-boundary/SKILL.md`, and `.agent/skills/start/SKILL.md` plus template mirrors.
- Update Codex hook injection so bounded delegated prompts get delegated-subtask workflow guidance instead of no-task/start guidance.
- Add focused tests for hook classification and static skill wording.

## Acceptance Criteria

- Subagents can still see project rules, but hook-injected workflow state tells delegated subtask prompts to follow the delegated prompt first.
- Prompts without hard markers are treated as delegated when they combine a concrete task with boundary/output constraints.
- Main-session prompts without delegated signals keep the existing `no_task` workflow-state behavior.
- Root and template copies stay in sync for changed workflow-facing files.
- Tests cover delegated hook behavior without introducing a heavy runtime or real agent orchestration.

## Verification

- `python -m unittest tests.test_codex_hooks tests.test_workflow_parallel_sessions`
- `./.cowork-flow/run doctor --subagent-safety`
- `npm run test:all`
