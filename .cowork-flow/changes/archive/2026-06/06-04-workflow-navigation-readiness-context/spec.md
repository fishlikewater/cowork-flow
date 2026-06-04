# Behavior Specification

## Workflow Navigator

- The workflow must provide a command-oriented navigator for main-session use.
- The navigator must be read-only and must not mutate task, change, session, or
  Git state.
- It must report current active task path and status when present.
- It must report missing task when no active task exists.
- It must report next safe action and exact command when a command is required.
- It must report blockers that prevent start, dispatch, finish, archive, or commit.
- It must cover at least: no task, planning task, in-progress task, completed task,
  unknown/stale task, and delegated-subtask protection guidance.

## L2 Readiness Gate

- L2 work is not ready for implementation or formal fixed-agent dispatch until it
  has goal and user value, non-goals, key assumptions, scope boundary, acceptance
  criteria, proposal/spec/design artifacts, linked plan and task, and verification
  commands.
- Missing required readiness fields must produce actionable blockers.
- A failed readiness check must not start a task, dispatch a fixed agent, archive,
  commit, or mutate unrelated workflow state.
- Existing `change validate` remains valid; readiness may call it or share its
  checks, but must expose L2 blockers in the task/start path.

## Project Context

- The workflow must support generating and refreshing `.cowork-flow/project-context.md`.
- Generated sections must be idempotent.
- Manual notes must survive regeneration.
- The context must summarize project identity, stack, workflow commands, host
  adapters, important specs, test commands, and local constraints.
- The context is an index and summary, not a replacement for `AGENTS.md`,
  `.cowork-flow/workflow.md`, or `.cowork-flow/spec/`.

## Template Sync

- Root and template copies of changed workflow scripts, docs, and tests must stay
  synchronized.
- Host-specific behavior must stay in host adapter or host asset directories.
- `.cowork-flow/workflow.md` must stay host-neutral.
