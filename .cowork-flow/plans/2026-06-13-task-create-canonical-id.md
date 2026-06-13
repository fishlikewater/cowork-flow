# Task Create Canonical Id Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Normalize date-prefixed `task create --slug` values before writing Flow task ids.
**Architecture:** Keep artifact directory generation unchanged through `ensure_task_date_prefix()`. Add a canonical id value in `cmd_create()` and use it for FlowStore ids while preserving existing parent resolution.
**Verification:** `.\.cowork-flow\run.cmd python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_cmd_create_keeps_existing_date_prefix -v`; `npm run test:template`; `git diff --check`.

## Execution Strategy

Serial work. The test and implementation share `task.py`, root/template parity, and lifecycle behavior.

## Steps

1. Add failing regression coverage.
   - File: `tests/test_flow_script_paths.py`.
   - Assert that `task create --slug 05-18-demo` creates artifact dir `05-18-demo`, stores Flow id `demo`, and does not store `05-18-demo`.
   - Verification: focused unittest fails before implementation.

2. Implement canonical id normalization.
   - Files: `.cowork-flow/scripts/task.py`, `template/.cowork-flow/scripts/task.py`.
   - Compute `task_id = TASK_DATE_PREFIX_PATTERN.sub("", slug)` once in `cmd_create()`.
   - Use `task_id` for `store.create_task(id=...)`.
   - Keep `artifact_dir=dir_name`.
   - Verification: focused unittest passes.

3. Run integrated checks.
   - Commands: focused unittest, `npm run test:template`, `git diff --check`.
   - Expected result: all pass; only this task/change/test/runtime scope is dirty.

4. Complete workflow.
   - Commands: `task review`, `task complete`, `task archive`, `add-session --commit "-"`, focused staging, commit.
   - Expected result: no active task; `.codegraph/` remains unstaged.

## Acceptance Mapping

- Canonical id for date-prefixed slug: steps 1 and 2.
- Artifact directory unchanged: steps 1 and 2.
- Parent and lifecycle compatibility: existing lifecycle tests plus focused regression.
- Root/template parity: step 2 and template tests.
