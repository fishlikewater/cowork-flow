# Formal Subagent Dispatch Guardrails Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Make the correct Codex formal-subagent path the obvious path, while keeping child bind mandatory.
**Architecture:** Add a host-specific CLI helper that wraps runtime-context init and emits spawn-agent-ready JSON/prompt. Keep host tool execution in the main session; Python only prepares the payload.
**Verification:** Focused Python tests for dispatch payload and `task next`, template tests, subagent safety doctor, diff check.

## Execution Strategy

Serial work. `subagent.py`, `task.py`, root/template mirrors, and tests share contracts.

## Tasks

1. Add failing tests
   - Modify `tests/test_subagent_dispatch.py` to assert `subagent dispatch-codex` emits runtime ids, host key, `bindCommand`, and a child prompt beginning with bind guidance.
   - Modify `tests/test_flow_script_paths.py` to assert `task next` for formal implement/check mentions `subagent dispatch-codex` and warns against bare `spawn_agent`.

2. Implement CLI helper
   - Modify `.cowork-flow/scripts/subagent.py`.
   - Add `dispatch-codex` subcommand that calls the same runtime-context creation path as `init`.
   - Return JSON with `spawn_agent` fields: `agent_type`, `task_name`, `fork_turns`, `message`, `runtimeContextId`, `hostContextKey`, `bindCommand`.
   - Do not call host tools from Python.

3. Improve workflow guidance
   - Modify `.cowork-flow/scripts/task.py`.
   - For formal implement/check next actions, print `subagent dispatch-codex ...` first.
   - Include explicit “do not use bare spawn_agent for cowork-* workflow gates” text.

4. Sync template
   - Mirror `subagent.py` and `task.py` to `template/.cowork-flow/scripts/`.

5. Verify
   - Run focused tests.
   - Run template tests.
   - Run `doctor --subagent-safety`.
   - Run `git diff --check`.
