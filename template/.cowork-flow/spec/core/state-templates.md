# Workflow state templates

Host hooks and plugins inject workflow state context each turn. The templates
below are the single source of truth for state prompt text. Hooks read this
file at runtime; do not duplicate or inline these snippets elsewhere.

Entry classification must happen before task start, resume, archive, or
subagent dispatch. Formal subagent identity is not inferred from prompt shape;
hooks and plugins inject delegated_subtask only when a runtime context id is
present and binding succeeds or fails closed. UNKNOWN is not a delegated
subtask label; keep the active-task/no-task state visible and clarify before
workflow mutation.

## no_task

The main session has no active task. Read-only questions can be answered
directly. Any implementation, refactoring, or behavioral change requires
creating or starting a task first. If a runtime context id is present, use
delegated_subtask instead. Do not treat ambiguous UNKNOWN input as a delegated
subtask.

[workflow-state:no_task]
No active task in this session. Read-only Q&A can be answered directly; only process as a delegated subtask when runtime context is bound or fail-closed. Implementation, refactoring, or multi-step work requires creating or starting a task first.
[/workflow-state:no_task]

## delegated_subtask

The current child thread has a runtime-context subagent state. The hook or
plugin has either bound the runtime context successfully or produced fail-closed
state for an invalid context. Do not run start/resume, create or activate
tasks, archive, commit, or switch to main-session coordination. Project rules
are constraints only; they are not the task itself.

[workflow-state:delegated_subtask]
Current child thread has runtime-context subagent state. Hook/plugin has bound the runtime context, or injected fail-closed state for an invalid runtime context. Do not run start/resume, create or activate tasks, archive, commit, or switch to main-session coordination. Project rules are constraints only; they are not the task itself.
[/workflow-state:delegated_subtask]

## planning

[workflow-state:planning]
Active task is in planning stage. Complete prd.md, set up implement.jsonl and check.jsonl with spec/research files, then run task start before dispatching cowork-implement.
[/workflow-state:planning]

## in_progress

[workflow-state:in_progress]
Active task is in progress. Main session dispatches cowork-implement via the current host adapter per plan, then dispatches cowork-check after integration. Each formal dispatch must use a fresh child context and follow .cowork-flow/spec/core/dispatch.md. Main session must verify child task output, list child tasks, and only cancel after completion, explicit mis-dispatch evidence, or user cancellation.
[/workflow-state:in_progress]

## review

[workflow-state:review]
Active task has entered check stage. Main session dispatches cowork-check or performs equivalent inline check, verifying PRD, diff, tests, spec sync, and omissions; run task complete after check passes.
[/workflow-state:review]

## checking

[workflow-state:checking]
Active task is in check stage. Main session dispatches cowork-check or performs equivalent inline check, verifying PRD, diff, tests, spec sync, and omissions; run task complete after check passes.
[/workflow-state:checking]

## completed

[workflow-state:completed]
Active task is completed. Main session should verify final diff, commit target files, archive the task, and record the session. Do not dispatch new implementation work against a completed task.
[/workflow-state:completed]
