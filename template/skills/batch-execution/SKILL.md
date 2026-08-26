---
name: batch-execution
description: Use when the user approves a full plan and asks for continuous execution across the task graph; each task still goes through lifecycle checks, implementation, check, completion, and commit independently.
---

# Batch Execution

## Core Contract

Batch Scheduler is a persistent state machine. Do **not** simulate or check completion inside the CLI.

- Batch is not the default path for ordinary task work.
- Use normal step-by-task progression unless the user explicitly approves automatic continuous execution.
- Task ordering comes **only** from the topological order of leaf tasks in the task tree.
- `implement.jsonl` and `check.jsonl` serve **only** as current-task context and review evidence; they must **not** be used as the Batch task list.
- Only one host-neutral `next_action` is published at a time.
- After the host executes a real action, results must be written back; the state machine validates repository state before advancing.
- Any failure in lifecycle checks, binding, implementation, check, test, completion, or commit **pauses** the batch.
- Completed tasks, phases, and commits are never re-executed on resume.

## Startup Conditions

Start only when **all** conditions are met:

1. The user explicitly approves the plan and asks for automatic continuous execution.
2. A valid task graph links the parent task and all leaf tasks.
3. The current session is main/coordinator — not a worker or delegated subagent.
4. The host can perform task, subagent, and Git actions.

Startup command:

```bash
./.cowork-flow/run task next <parent-task> --run --intent batch --auto --approved
```

The command routes through `task next`, runs the runtime-gated Batch action, and returns the full Batch state, where `next_action` is the **only** allowed next step.

## Read-Only Inspection

Hosts may inspect an existing Batch operation without advancing, resuming, or
saving the state:

```bash
batch-action inspect <operation_id>
```

The inspect report is derived from the persisted Batch state and includes
`operationId`, `state`, `rootTask`, `currentPhase`, `currentTask`,
`completedTasks`, `pausedReason`, `failedAction`, `nextAction`, and `recovery`.
Use it for monitoring, recovery UI, or handoff facts. It must not replace
`record-result` after a host action. Do not use inspect as completion evidence.

## Host Action Loop

Each cycle processes in this order:

1. Read `next_action`; verify `action_id`, `type`, `task`, and `task_dir`.
2. Execute **only** that action — do not advance to later phases prematurely.
3. Write the result to a UTF-8 JSON file.
4. Write back the result through the Batch action script packaged with this Skill; do not call removed task subcommands directly.
5. Read the new state. If `awaiting_host`, continue with the new `next_action`. If `paused`, halt all subsequent tasks.

## Action Types

### `start_task`

Run the real task startup action through `task next` and pass through the readiness/spec gates:

```bash
./.cowork-flow/run task next <task_dir> --run --intent implement
```

A successful result must contain:

```json
{
  "action_id": "<action-id>",
  "type": "start_task",
  "outcome": "success",
  "task_status": "in_progress"
}
```

The state machine also reads `task.json` and trusts only the genuine `in_progress` status.

### `init_implement_context` / `init_check_context`

Run with `role`, `agent_type`, `task_dir`, and `title` from the action:

```bash
./.cowork-flow/run subagent init \
  --role <role> \
  --agent-type <agent_type> \
  --execution-task-dir <task_dir> \
  --title "<title>"
```

The host must use the returned `cowork_runtime_context_id` and `cowork_host_context_key` to dispatch the matching worker, and the worker's first step must run `subagent bind`.

Write back the initialization result:

```json
{
  "action_id": "<action-id>",
  "type": "init_implement_context",
  "outcome": "success",
  "runtime_context_id": "<runtime-context-id>",
  "host_context_key": "<host-context-key>"
}
```

For the check phase, change `type` to `init_check_context`.

### `await_implement_result` / `await_check_result`

Wait for the corresponding worker to finish, and verify the output belongs to the current task and the runtime context is bound to the expected host.

A successful result must contain the same `runtime_context_id` and `host_context_key` as the action. The state machine verifies `status=bound` before closing the runtime context. If close succeeds but the Batch checkpoint has not yet been flushed, repeating the write-back can still recover.

### `review_task`

Run the review action through `task next`:

```bash
./.cowork-flow/run task next <task_dir> --run --intent review
```

The successful result's `task_status` must be `review`; the state machine also reads the genuine `task.json`.

### `complete_task`

Run the completion action through `task next`:

```bash
./.cowork-flow/run task next <task_dir> --run --intent review
```

The successful result's `task_status` must be `completed`; the state machine also reads the genuine `task.json`.

### `archive_task`

Run the real archive action through `task next` to move the completed task to `archive/<year-month>/`:

```bash
./.cowork-flow/run task next <task_dir> --run --intent archive
```

The host must verify the task directory has been moved to the archive location. A successful result must contain:

```json
{
  "action_id": "<action-id>",
  "type": "archive_task",
  "outcome": "success",
  "archive_destination": ".cowork-flow/tasks/archive/<year-month>/<task_name>"
}
```

The state machine verifies the destination directory exists on disk. If the archive fails (task directory not found or move conflict), write back a failure result and the batch pauses. On resume, only `archive_task` is retried — `complete_task` is not re-executed.

### `commit_task`

Commit only the current task's verified changes, and write back the real commit id:

```json
{
  "action_id": "<action-id>",
  "type": "commit_task",
  "outcome": "success",
  "commit_id": "<git-commit-id>"
}
```

The state machine uses Git to verify the object is genuinely a commit. Empty values, placeholder strings, or non-existent commits all cause a pause.

## Failure and Recovery

When the host is unavailable or any action fails, write back a non-success result:

```json
{
  "action_id": "<action-id>",
  "type": "<action-type>",
  "outcome": "failure",
  "detail": "<specific cause>"
}
```

The state becomes `paused`. The failed task and all subsequent tasks are **not** marked completed.

Inspect the paused operation first:

```bash
batch-action inspect <operation_id>
```

Use the report's `failedAction`, `pausedReason`, and `recovery` facts to decide
what the host must repair. Repair or rerun the failed Host action outside the Batch state file.
Do **not** manually edit the Batch state file.

Resume only after the failed action can succeed:

```bash
batch-action resume <operation_id>
```

Alternatively, rerun the approved Batch action through `task next` for the
parent task:

```bash
./.cowork-flow/run task next <parent-task> --run --intent batch --auto --approved
```

The recovered run generates a new `action_id` but preserves completed tasks, phases, runtime evidence, and commits. Do **not** skip the failed task. Do **not** manually edit the Batch state file.

## Completion Verification

Once the Batch state becomes `completed`:

1. Run the project's full test and build commands.
2. Verify `completed_tasks`, `task_phases`, and `commits` correspond one-to-one.
3. Verify each leaf task has its own independent commit.
4. Run spec sync, doctor, and pre-release checks.
