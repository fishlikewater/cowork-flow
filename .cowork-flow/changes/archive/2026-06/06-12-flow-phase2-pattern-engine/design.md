# Phase 2 Pattern Engine Design

## Architecture

`patterns/` is a pure decision layer. It receives already-loaded task data and returns validation issues or advisory actions. It does not read files, open SQLite connections, update task status, spawn agents, or call host-specific APIs.

`task.py` remains the lifecycle command surface. For each lifecycle operation it:

1. Resolves the target FlowStore task.
2. Builds a `TaskContext` with task, child tasks, active block, and metadata.
3. Resolves the task pattern through `PatternRegistry`.
4. Runs validation and transition checks.
5. Calls the existing FlowStore mutator only after the pattern gate passes.

FlowStore remains the single write path for tasks, child links, audit rows, and block rows.

## Contract Types

- `StepKind`: enum-like action identifiers for start, dispatch, wait children, request human decision, review, complete, and archive suggestions.
- `Action`: next recommended operation returned by `Pattern.next_action()`.
- `TaskContext`: immutable context object containing `task`, `children`, and `active_block`.
- `BlockView`: normalized active block data used by Human-loop.
- `TaskView`: shared task row shape used by FlowStore and patterns.

## Pattern Behavior

### Generic

Generic preserves Phase 1 lifecycle and adds the already-supported blocked path:

`planning -> in_progress -> review -> completed -> archived`

`in_progress -> blocked -> in_progress`

### Fan-out

Fan-out parent tasks require at least one generic child. The parent cannot move to review while any child is not `completed` or `archived`. In Phase 2, Fan-out only reports wait/complete actions; actual child dispatch is Phase 3.

### Pipeline

Pipeline tasks require `meta.stages` and `meta.current_stage`. A stage can move to review; successful review advances `current_stage`. Completion is allowed only after `current_stage >= len(stages)`.

### Human-loop

Human-loop tasks require `meta.decision_points`. Blocking records the pending decision. Unblocking requires `--decision`; the decision is stored on the block row before the task returns to `in_progress`.

## Testing Strategy

- Pure pattern tests cover validation, transitions, and next actions without touching the filesystem.
- Lifecycle tests use temp repositories and real `task.py` commands to prove pattern gates prevent invalid FlowStore mutation.
- Template parity tests prove runtime/spec files are shipped to new projects.

## Compatibility

Existing tasks with missing or unknown pattern resolve to Generic. Phase 2 does not migrate existing task rows beyond reading their current `pattern` and `meta` values.
