# 06-13-task-create-canonical-id

## Goal

Ensure `task create --slug <MM-DD-slug>` writes a canonical Flow task id without the date prefix while preserving the date-prefixed artifact directory.

## User Value

Users can safely rerun or script `task create` with an already date-prefixed directory slug and still get reliable `task next`, `task start`, `task review`, `task complete`, and `task archive` behavior.

## Problem

`task create` currently avoids doubling the date prefix in the artifact directory, but it still writes the raw `--slug` value as the Flow task id. If the slug is already date-prefixed, later helpers normalize the directory name with `_resolve_task_id()` and look for the unprefixed id, so lifecycle navigation can drift.

## Brainstorming

- Recommended: normalize the Flow task id at create time and keep the artifact directory unchanged.
- Rejected: stop stripping date prefixes in `_resolve_task_id()` because existing tasks and archive paths rely on that behavior.
- Rejected: migrate historical rows in this small smoke task because the goal is to validate the new flow with a focused code path.

## Scope

- Update root and template `task.py`.
- Add a regression test for date-prefixed `--slug` task creation.
- Keep parent linking and artifact directory behavior unchanged.

## Non-Goals

- No migration of already-created task rows.
- No change to archive directory naming.
- No broad refactor of task id resolution.

## Acceptance

1. `task create --slug 05-18-demo` creates artifact dir `05-18-demo`.
2. The Flow task id for that artifact is `demo`, not `05-18-demo`.
3. Parent/child linking still uses canonical ids.
4. Root and template runtime files stay synchronized.
