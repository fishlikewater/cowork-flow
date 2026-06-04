# Runtime Context Data Model

## Goal

Implement the runtime data model that gives each formal subagent its own
runtime context and session identity.

## Scope

- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/common/active_task.py`
- Root/template script mirrors where applicable
- Tests covering runtime context creation, lookup, binding primitives, close,
  and stale cleanup

## Non-goals

- No hook/plugin injection changes in this task.
- No adapter/spec/doc cleanup in this task.
- No edits to historical archive files.

## Acceptance Criteria

- `subagent init` creates `.cowork-flow/.runtime/subagents/<id>.json`.
- `subagent init` creates `.cowork-flow/.runtime/sessions/subagent_<id>.json`.
- Output includes `cowork_runtime_context_id` and a minimal prompt transport
  line.
- Runtime helpers can bind a host session to a subagent context.
- Runtime helpers can close a bound child and remove its session files.
- Tests cover the new schema and fail if legacy ACK/EXECUTE fields return.

## Verification

- `python -m unittest tests.test_subagent_dispatch tests.test_active_task_runtime`
- `git diff --check`
