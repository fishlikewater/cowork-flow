# P3 盘点 06-25 completed 任务状态

## Goal

Audit old 06-25 completed tasks and archive safe items or document intentional completed state.

## Scope

- 06-25 task lifecycle state
- Archived task validation
- Session evidence

## Non-Goals

- Do not modify implementation artifacts for those tasks
- Do not reopen old changes unless validation requires a documented reason

## Acceptance Criteria

1. Every remaining 06-25 completed task is either archived or has a written reason to stay completed.
2. Active task is empty after audit closeout.
3. Task list output is intentionally consistent.
4. git diff check passes.

## Relevant Files

- `.cowork-flow/tasks/`
- `.cowork-flow/tasks/archive/`
- `.cowork-flow/workspace/codex/index.md`
- `.cowork-flow/workspace/codex/journal-2.md`

## Verification

- `.cowork-flow/run.cmd task list`
- `.cowork-flow/run.cmd task current`
- `git diff --check`
