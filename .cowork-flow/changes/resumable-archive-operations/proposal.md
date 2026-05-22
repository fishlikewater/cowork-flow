# Resumable Archive Operations

## Problem
The current archive flow is fragile on Windows and during interrupted runs. `task archive` and `change archive` rely on `shutil.move` as if it were atomic. In practice, a move can leave both the source and destination directories present. The next run then fails because the archive destination already exists, and recovery requires manual directory comparison, source deletion, metadata edits, and path fixes.

The previous archive run exposed these concrete failures:
- `.cowork-flow/.current-task` could not be deleted because of a Windows permission error.
- `task archive` left both the active task directory and archived task directory present.
- `change archive` failed when `change.yaml task` used `.cowork-flow/tasks/...` and link resolution prefixed `.cowork-flow/tasks/` again.
- `change archive` also left duplicate source and archive directories after a failed move.
- Archived change metadata had to be corrected manually.

## Goal
Make archive operations safe to retry after partial progress. A rerun should either finish the archive or clearly report the remaining manual action instead of forcing the user to inspect filesystem state by hand.

## Non-Goals
- Do not add a second archive command or a separate recovery CLI.
- Do not introduce a broad transaction framework.
- Do not change task/change creation or listing semantics except for normalized archived task references.
- Do not solve unrelated Windows permission problems beyond reporting deletion failures precisely.

## Proposed Approach
Replace move-as-transaction behavior with a small, shared archive helper:
1. Copy source to destination when the destination does not exist.
2. Verify source and destination have the same file set and file bytes.
3. Delete the source only after verification.
4. If source deletion fails, return a partial result that points to the verified archive destination and remaining source.
5. If source and destination both exist on a later run and match, resume from the delete-source step.
6. If both exist and differ, stop with a clear conflict error.

Change archive should normalize task links when archiving:
- Active task link may be `05-22-demo` or `.cowork-flow/tasks/05-22-demo`.
- Archived task link should be stored as `archive/YYYY-MM/05-22-demo` when it points at an archived task.

## Success Criteria
- Re-running `task archive` when source and archive destination already match completes without treating the existing destination as fatal.
- Re-running `change archive` when source and archive destination already match completes metadata finalization and removes source when possible.
- Change validation accepts existing task links written as `.cowork-flow/tasks/<name>` without double-prefixing.
- Archived change metadata always has `status: archived` and `archived_at`.
- The implementation has regression tests that fail before the fix and pass after it.
