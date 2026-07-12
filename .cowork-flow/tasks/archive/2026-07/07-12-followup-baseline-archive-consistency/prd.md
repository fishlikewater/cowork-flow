
# P3 对齐基线任务归档一致性

## Goal

Resolve or document the final completed-vs-archived status mismatch in the 07-11 roadmap task set.

## Scope

- 07-11 baseline task lifecycle state
- Roadmap plan/status notes if needed
- Session/archive records

## Non-Goals

- Do not modify completed implementation artifacts.
- Do not reopen archived roadmap change.

## Acceptance Criteria

1. Baseline task is archived when safe, or a written reason explains why it remains completed.
2. Active task remains empty after the operation.
3. 07-11 task status display is consistent or intentionally documented.
4. git diff --check passes.

## Relevant Files

- `.cowork-flow/tasks/07-11-opt-baseline-risk-map/`
- `.cowork-flow/tasks/archive/2026-07/`
- `.cowork-flow/plans/2026-07-11-workflow-optimization-roadmap.md`
- `.cowork-flow/workspace/codex/`

## Verification

- `.cowork-flow/run.cmd task next 07-11-opt-baseline-risk-map`
- `.cowork-flow/run.cmd task list`
- `.cowork-flow/run.cmd task current`
- `git diff --check`
