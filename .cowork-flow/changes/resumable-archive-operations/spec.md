# Resumable Archive Operations Spec

## Archive Directory Behavior
- When an archive command copies a source directory to an archive destination, it MUST verify that both directory trees contain the same relative file paths and identical file bytes before deleting the source.
- When the archive destination does not exist, the command MUST create parent directories, copy the source directory to the destination, verify the copy, then delete the source.
- When both source and destination exist and their contents match, the command MUST treat this as resumable partial progress and continue by deleting the source.
- When both source and destination exist and their contents differ, the command MUST fail with a conflict message that includes both paths.
- When destination verification succeeds but source deletion fails, the command MUST return a partial result and print the remaining source path instead of reporting the archive copy as lost.

## Task Archive Behavior
- `task archive <name>` MUST still resolve active task names by exact or suffix match.
- If the active task is the current task, `.current-task` is cleared before archive. If clearing fails, archive MUST stop before copying.
- If the source task and destination archive directory already match from a prior failed run, `task archive <name>` MUST finish by deleting the source, finalizing archived task metadata, and printing the archive path.
- If deletion remains blocked after verified copy, the command MUST fail with a clear partial-progress message and leave `.current-task` restored when it had been cleared for this attempt.

## Change Archive Behavior
- `change archive <slug>` MUST validate the active change before archive.
- If source and archive destination already match from a prior failed run, `change archive <slug>` MUST finish metadata finalization and remove the source.
- Archived change metadata MUST include `status: archived` and `archived_at`.
- `change.yaml task` links MUST be resolved correctly when written as either `05-22-demo` or `.cowork-flow/tasks/05-22-demo`.
- When archiving a change whose task link points to an already archived task under `.cowork-flow/tasks/archive/YYYY-MM/<task>`, the stored task value MUST be normalized to `archive/YYYY-MM/<task>`.

## Verification
- Regression tests cover matching source/destination resume behavior for task archive and change archive.
- Regression tests cover task-link validation for `.cowork-flow/tasks/<task>` and archived task-link normalization.
- Targeted Python tests pass.
- Template test suite passes.
