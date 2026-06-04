# Design

## Current Architecture Fit

cowork-flow already separates:

- project rules: `AGENTS.md`;
- workflow policy: `.cowork-flow/workflow.md`;
- contract/spec files: `.cowork-flow/spec/`;
- lifecycle scripts: `.cowork-flow/scripts/`;
- host adapters/assets: `.codex`, `.opencode`, `.claude`, and
  `.cowork-flow/adapters/<host>/`;
- task/change/plan state: `.cowork-flow/tasks`, `.cowork-flow/changes`,
  `.cowork-flow/plans`.

The optimization should use those surfaces instead of adding another coordinator.

## Navigator

Preferred shape:

- Add a small read-only workflow navigator command, exposed through
  `.cowork-flow/run`.
- Add `task next` as the task-aware entry because agents already know `task`
  commands.
- Optionally add `flow help` if a separate `flow.py` script makes top-level route
  help clearer than expanding runner help.

The navigator reads active task state, task files, linked change metadata, and
workflow templates. It prints next action and blockers. It does not write files.

## L2 Readiness

Use a shared readiness helper under `.cowork-flow/scripts/common/` so `task next`,
`task start`, and future dispatch checks can share the same contract.

Readiness sources:

- task `prd.md`;
- task `task.json`;
- task context JSONL files;
- change metadata referencing the task;
- L2 change `proposal.md`, `spec.md`, `design.md`;
- linked plan file.

Fail-closed points:

- before `task start` for linked L2 work;
- before formal fixed-agent dispatch when the main session checks next action;
- during `task next` output as blockers.

## Project Context

Preferred file: `.cowork-flow/project-context.md`.

Structure:

- managed generated block: project identity, stack, commands, workflow, specs,
  adapters, package scripts, current template version;
- manual notes block: preserved across refresh;
- timestamp/fingerprint block for stale-context detection.

Generation can start as a deterministic script reading local files. It should not
call external services. It should avoid copying large specs verbatim; list links
and short summaries instead.

## Test Strategy

- Unit tests for readiness helper states.
- Runner tests for new command dispatch.
- Task command tests for `task next` and start blockers.
- Template sync tests for root/template copies.
- Existing hook and subagent safety tests remain unchanged.

## Risks

- Too strict a readiness gate could block small L1/L0 work. Keep L2-only blocking
  behavior and read-only reporting for other levels.
- `project-context.md` can go stale. Add an idempotent refresh command and tests.
- Navigator output can become another doc surface. Keep it generated from live
  state and short.
