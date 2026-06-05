# Runtime Binding Shim

## Goal

Codex, Claude Code, and OpenCode formal subagents must support an explicit
runtime-context binding shim. A child agent may only perform formal
`cowork-*` work after runtime state records a successful binding.

## User Value

Users can trust formal subagent execution across hosts because a child is not
accepted as `cowork-research`, `cowork-implement`, or `cowork-check` until
runtime state proves it is bound to the dispatched context. This prevents
prompt-only success from hiding host integration gaps.

## Background

Real Codex `spawn_agent(cowork-check)` smoke testing showed that the child
could behave like a leaf checker, but runtime state stayed
`status=pending` and `bound_context_key=null`. Direct hook invocation can bind,
so the gap is in the host child-session path, not in runtime context data.

Claude Code and OpenCode already have hook/plugin binding paths, but their
model-before-execution guarantees differ by host. The workflow needs a unified
shim that works even when automatic binding is unavailable.

## Scope

- Runtime bind semantics in `.cowork-flow/scripts/subagent.py` and helpers.
- Dispatch contract specs under `.cowork-flow/spec/`.
- Adapter declarations for Codex, Claude Code, and OpenCode.
- Fixed-agent and command assets for `.codex/`, `.claude/`, `.opencode/`.
- Template mirrors for all changed root assets.
- Tests for runtime binding, adapter truth, host assets, hooks/plugins, and
  package/sync behavior.

## Non-goals

- Do not add a new agent runtime or daemon.
- Do not restore legacy prompt ACK/EXECUTE dispatch.
- Do not treat generic `worker` dispatch as formal `cowork-*` completion.
- Do not implement unrelated archive, task, or workflow wording changes.

## Key Assumptions

- Host hooks/plugins may bind earlier, but not every host can prove that binding
  happens before child model execution.
- A first-step explicit bind command is acceptable for formal child work when
  the parent verifies runtime files before accepting output.
- Existing runtime context files can keep their schema; only bind semantics and
  prompt contracts need tightening.
- Generic `worker` dispatch remains advisory and cannot satisfy formal
  Implement or Check completion.

## Acceptance Criteria

- Codex no longer declares unverified native runtime context binding.
- Codex, Claude Code, and OpenCode formal agent prompts require:
  - `cowork_runtime_context_id`
  - `cowork_host_context_key`
  - first-step `subagent bind <id> <context-key>`
  - fail-closed stop when bind fails.
- `subagent bind` succeeds for valid open contexts, is idempotent for the same
  key, and rejects binding the same runtime id to a different key.
- Parent acceptance checks runtime files before accepting child final text.
- Direct hook/plugin runtime binding behavior remains covered and green.
- Root/template assets remain synchronized.

## Related Files

- `.cowork-flow/changes/06-05-runtime-binding-shim/proposal.md`
- `.cowork-flow/changes/06-05-runtime-binding-shim/design.md`
- `.cowork-flow/changes/06-05-runtime-binding-shim/spec.md`
- `.cowork-flow/plans/2026-06-05-runtime-binding-shim.md`
- `.cowork-flow/spec/subagent-dispatch.md`
- `.cowork-flow/spec/capabilities.md`
- `.cowork-flow/spec/adapter.schema.json`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/common/active_task.py`
- `.cowork-flow/adapters/`
- `.codex/agents/`
- `.claude/agents/`
- `.opencode/agents/`
- `.codex/hooks/`
- `.claude/hooks/`
- `.opencode/plugins/`
- `template/`
- `tests/`
- `test/`

## Verification

- `./.cowork-flow/run change validate 06-05-runtime-binding-shim`
- `./.cowork-flow/run task validate .cowork-flow/tasks/06-05-runtime-binding-shim`
- `python -m unittest tests.test_subagent_dispatch tests.test_active_task_runtime`
- `python -m unittest tests.test_host_adapters tests.test_cowork_agents`
- `python -m unittest tests.test_codex_hooks tests.test_claude_hooks`
- `node --test test/opencode-plugin.test.js`
- `./.cowork-flow/run doctor --subagent-safety`
- `git diff --check`
- `npm run test:all`
