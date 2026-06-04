# Runtime Dispatch Verification

## Goal

Run the integrated verification pass for the runtime-context dispatch migration
and fix any in-scope regressions.

## Scope

- Test migrations missed by prior tasks
- Root/template synchronization issues
- Current change/task/plan documentation alignment
- Final diff hygiene

## Non-goals

- No unrelated refactors.
- No edits to historical archive files.

## Acceptance Criteria

- Focused runtime, hook, adapter, agent, workflow, and template tests pass.
- `npm run test:all` passes.
- `git diff --check` passes.
- Current plan and task statuses reflect completed work truthfully.

## Verification

- `python -m unittest tests.test_subagent_dispatch tests.test_active_task_runtime tests.test_codex_hooks tests.test_claude_hooks tests.test_host_adapters tests.test_cowork_agents tests.test_workflow_parallel_sessions tests.test_no_legacy_template_paths`
- `npm run test:all`
- `git diff --check`
