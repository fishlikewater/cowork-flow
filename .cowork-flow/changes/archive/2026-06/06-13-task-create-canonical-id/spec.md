# Task Create Canonical Id Spec

## Contract

- `task create` must treat `--slug` as the requested artifact slug.
- If `--slug` starts with the `MM-DD-` date prefix pattern, the Flow task id must strip that prefix.
- If `--slug` does not start with the date prefix pattern, the Flow task id must equal the slug.
- `artifact_dir` must continue to use `ensure_task_date_prefix(slug)`.

## Lifecycle Compatibility

- `_resolve_task_id()` remains the normalization point for task directory lookups.
- `task next`, `task start`, `task review`, `task complete`, and `task archive` must be able to resolve the canonical id from the artifact directory.
- Parent ids must be stored as canonical ids.

## Template Parity

Root `.cowork-flow/scripts/task.py` and `template/.cowork-flow/scripts/task.py` must contain the same task-create canonicalization behavior.
