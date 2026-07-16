# Design: Post-closeout workflow hardening

## Current Behavior

- `cmd_archive` in `.cowork-flow/scripts/task.py` finds linked active changes via `change.linked_active_changes_for_task`, validates them, archives the task, then archives every linked change.
- This works for a single-task change, but a multi-task change currently stores only one `change.yaml.task` pointer, so the archive command cannot tell whether more tasks in the same plan/change remain.
- Archived tasks keep JSONL context entries as authored. When linked changes/tasks move to archive directories, any JSONL entries pointing at the active path become invalid.
- `npmCommandOptions('win32')` returns `{ shell: true }`, which keeps `npm` executable on Windows but triggers Node `DEP0190` in modern runtimes.

## Proposed Direction

1. **Linked change final gate**
   - Keep existing single-task auto-archive behavior covered by tests.
   - Add an explicit finalization signal or derived readiness check before auto-archiving a linked change that is part of a multi-task plan.
   - Prefer a narrow helper over broad workflow redesign.

2. **Archive context rewrite**
   - Add a post-move normalization step for archived task context files.
   - Rewrite known repo-relative active paths to their archived destinations when the current command moves those artifacts.
   - Validate archived task context after archive in tests.
   - Keep root/template copies aligned when runtime script behavior changes.

3. **Shellless npm commands**
   - Replace Windows `shell: true` with explicit `npm.cmd` command resolution for npm invocations.
   - Update tests that currently expect `{ shell: true }`.
   - Verify package/update tests and pack check.

4. **Completed task audit**
   - Inspect the 06-25 completed tasks as a batch.
   - Archive tasks that pass validation and have no active change dependency.
   - If any remain completed, write a reason into the audit task evidence.

## Risks

- Archive behavior is central closeout machinery; regression tests must cover both single-task auto archive and multi-task non-final behavior.
- Context rewrite must not mutate historical prose broadly; limit it to JSONL context file `file` fields and directly moved known artifacts.
- Windows npm command behavior must still work for both `execFile` and `spawn`.
