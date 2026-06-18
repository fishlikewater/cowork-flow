# Script Compatibility And Dead Code Cleanup Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Remove compatibility-only and test-only script paths that no longer affect the current workflow.
**Architecture:** Current workflow authority is DB-backed runtime/session/task state plus prompt transport for formal subagent dispatch. Legacy JSON import fallbacks, pointer-file payloads, and deprecated write-only APIs should be removed when they are not part of the live runtime contract, with root/template/spec/test parity preserved.
**Verification:** `rtk python -m pytest tests/test_active_task_runtime.py tests/test_flow_store.py tests/test_dashboard.py tests/test_subagent_dispatch.py -v`, `rtk npm run test:template`, `rtk git diff --check`

## Execution Strategy

Serial work. The candidates share runtime contracts, output payloads, tests, and template parity, so one coordinated cleanup is safer than parallel slices.

## Steps

1. Remove deprecated agent-run write APIs that are only retained by tests.
   Files:
   - `.cowork-flow/scripts/flow/store.py`
   - `template/.cowork-flow/scripts/flow/store.py`
   - `tests/test_flow_store.py`
   Check:
   - Delete `create_agent_run` / `update_agent_run_status` if no live caller remains.
   - Remove tests that only assert deprecated no-op behavior.

2. Remove legacy JSON import fallbacks from active task/runtime resolution.
   Files:
   - `.cowork-flow/scripts/common/active_task.py`
   - `template/.cowork-flow/scripts/common/active_task.py`
   - `tests/test_active_task_runtime.py`
   Check:
   - Keep DB-backed runtime/session reads.
   - Delete legacy file import helpers and tests that only cover import-on-read fallback.

3. Remove dashboard legacy state-file fallback if DB state is the only live path.
   Files:
   - `.cowork-flow/scripts/dashboard/server.py`
   - `template/.cowork-flow/scripts/dashboard/server.py`
   - `tests/test_dashboard.py`
   Check:
   - Keep DB-backed start/status/stop behavior.
   - Remove `dashboard.json` compatibility import behavior and related references.

4. Re-evaluate pointer-file/output compatibility and remove it if unused by live flow.
   Files:
   - `.cowork-flow/scripts/subagent.py`
   - `template/.cowork-flow/scripts/subagent.py`
   - `tests/test_subagent_dispatch.py`
   - related spec if touched
   Check:
   - Remove `runtimeContextFile` or related pointer-file writes only if no live contract depends on them.
   - Keep `promptTransport`, `bindCommand`, and DB-backed runtime/session semantics.

5. Sync docs/spec and verify.
   Files:
   - touched spec files
   - touched tests
   Check:
   - Remove stale compatibility wording.
   - Re-run targeted and template verification.
