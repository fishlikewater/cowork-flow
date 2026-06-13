# Implement Flow Phase 3 Subagent And Dashboard

## Goal

Implement Phase 3 of `FLOW-UPGRADE-DESIGN.md`: family subagent helpers, read-only dashboard, and template/contract synchronization.

## Benefits

This turns the Phase 2 Fan-out pattern from advisory lifecycle logic into an executable workflow surface and gives users a browser-visible Flow board without allowing dashboard writes.

## Key Assumptions

- FlowStore remains the single persistence writer.
- Family commands prepare runtime contexts and status indexes; host adapters still dispatch real children.
- Dashboard is GET-only and stdlib-only.
- Root/template parity is required for new project installs.

## Scope

- `subagent spawn-family` and `subagent check-family`.
- Agent run helper hardening where required by family commands and dashboard detail API.
- `dashboard/server.py` and static assets.
- `run.py` dashboard command registration.
- Adapter schema/yaml, workflow/spec/registry updates.
- Template sync and verification tests.

## Non-Goals

- No dashboard write operations.
- No automatic host-specific child spawning inside Python.
- No Phase 4 release, npm publish, or migration-from-v0.0.26 validation.
- No new Python or npm dependency.

## Child Tasks

- `06-13-flow-phase3-subagent-family`: family subagent commands and tests.
- `06-13-flow-phase3-dashboard`: read-only dashboard server, API, static UI, command registration.
- `06-13-flow-phase3-template-contracts`: adapter/spec/workflow/template synchronization.
- `06-13-flow-phase3-verification`: integrated verification and closeout.

## Acceptance Criteria

1. `spawn-family` creates one missing runtime context and `agent_run` per eligible child, while skipping completed/archived children and already-running child runs.
2. `check-family` returns deterministic JSON and exits `0` only when all child runs are done.
3. Dashboard starts through `run.cmd dashboard`, serves board/task/pattern APIs, and remains read-only.
4. Adapter capabilities include multi-child spawn/wait declarations and pass schema tests.
5. Root and template copies are synchronized.
6. `python -m pytest tests/test_subagent_dispatch.py tests/test_flow_store.py tests/test_flow_script_paths.py tests/test_host_adapters.py tests/test_no_legacy_template_paths.py tests/test_patterns.py -q`, `npm run test:all`, `git diff --check`, and `.\.cowork-flow\run.cmd doctor --subagent-safety` pass.

## References

- `FLOW-UPGRADE-DESIGN.md`
- `.cowork-flow/changes/06-13-flow-phase3-subagent-dashboard/`
- `.cowork-flow/plans/2026-06-13-flow-phase3-subagent-dashboard.md`
