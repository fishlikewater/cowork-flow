# Plan: post_ack_execution_grace_ms Runtime Config

## Success Criteria

- Changing `codex.post_ack_execution_grace_ms` changes hook-injected runtime context.
- Invalid or missing values fall back to `300000`.
- Root/template runtime files remain synchronized.

## Execution Strategy

Serial inline execution. This task modifies subagent/runtime coordination behavior, so the main session will not dispatch `cowork-implement` or `cowork-check` against the mechanism being changed.

## Steps

1. [x] Add focused regression tests for hook runtime grace injection.
   - Verify: `.cowork-flow/run python -m unittest tests.test_codex_hooks`
2. [x] Implement config getter and hook runtime context injection in root files.
   - Verify: focused tests failed before implementation and pass after implementation.
3. [x] Mirror runtime changes to `template/`.
   - Verify: template/root synchronization assertions pass in `tests.test_codex_hooks`.
4. [x] Run workflow safety and full verification.
   - Verify: `.cowork-flow/run python -m unittest tests.test_workflow_parallel_sessions`
   - Verify: `npm run test:all`
