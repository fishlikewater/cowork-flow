# Runtime Session Subagent Dispatch

## Goal

Design a runtime-context dispatch model that prevents subagent first-screen
bootstrap capture across Codex, Claude Code, and OpenCode, and prepare the
implementation plan and task context for the migration.

## Scope

- L2 change proposal, design, and spec artifacts.
- Implementation plan with verification steps.
- Task context indexes for the runtime, hook, adapter, host, template, and test
  files that need migration.
- Runtime context files under `.cowork-flow/.runtime/subagents/`.
- Main and subagent session separation under `.cowork-flow/.runtime/sessions/`.
- Codex and Claude Code hook runtime-context binding.
- OpenCode plugin runtime-context binding.
- Host adapter schema and Codex/Claude Code/OpenCode adapter declarations.
- Fixed agent, command, skill, workflow, README, and template synchronization.
- Tests for runtime context creation, binding, cleanup, adapter contracts, and
  legacy protocol removal.

## Non-goals

- No compatibility with legacy formal dispatch protocols.
- No prompt-classifier fallback for formal subagent identity.
- No use of fixed-agent dispatch while modifying the dispatch runtime.
- No unverified claim that a host supports env or metadata transport.
- No edits to historical archive files under `.cowork-flow/changes/archive/` or
  `.cowork-flow/tasks/archive/`.

## Acceptance Criteria

- Design defines how formal fixed-agent dispatch is keyed by
  `cowork_runtime_context_id`.
- Design defines how a subagent gets its own runtime session and is
  distinguishable from the main session before workflow state is injected.
- Design defines hook/plugin binding behavior for Codex, Claude Code, and
  OpenCode.
- Design defines child close and runtime cleanup behavior.
- Design decides that the former prompt-boundary skill is removed and `start` becomes
  main-session-only.
- Design specifies zero compatibility with legacy dispatch protocols and lists
  the required cleanup/test migration.
- The linked plan and task context make the implementation scope executable in a
  follow-up step.
- Historical archive files are excluded from legacy string cleanup.

## Related Files

- `.cowork-flow/changes/06-04-runtime-session-subagent-dispatch/proposal.md`
- `.cowork-flow/changes/06-04-runtime-session-subagent-dispatch/design.md`
- `.cowork-flow/changes/06-04-runtime-session-subagent-dispatch/spec.md`
- `.cowork-flow/plans/2026-06-04-runtime-session-subagent-dispatch.md`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/common/active_task.py`
- `.codex/hooks/inject-workflow-state.py`
- `.claude/hooks/inject-workflow-state.py`
- `.opencode/plugins/cowork-flow.js`
- `.cowork-flow/adapters/`
- `template/`
- `tests/`

## Verification

- `./.cowork-flow/run change validate`
- Focused hook/runtime/adapter tests after implementation.
- Legacy string absence check after migration.
- `git diff --check`
- `npm run test:all`
