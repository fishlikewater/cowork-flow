# Delegated Bootstrap Classification Plan

**Goal:** Make no-hard-marker delegated prompts win the first-screen classification over project bootstrap while preserving project rules as constraints.
**Execution strategy:** Serial inline work because this changes subagent/bootstrap behavior.
**Verification:** Focused Python tests, doctor safety check, then `npm run test:all`.

## Steps

1. Update hook classification -> Verify: delegated prompt test emits `delegated_subtask`, normal no-task test still emits `no_task`.
2. Update AGENTS/start/entry-boundary wording in root and template -> Verify: static tests require "before loading state" and delegated prompt priority language.
3. Run integrated checks -> Verify: `python -m unittest tests.test_codex_hooks tests.test_workflow_parallel_sessions`, `./.cowork-flow/run doctor --subagent-safety`, `npm run test:all`.

## Notes

- Do not add a result ledger, outbox, or runtime state machine.
- Keep the hook heuristic conservative: concrete task plus boundary or output constraints.
