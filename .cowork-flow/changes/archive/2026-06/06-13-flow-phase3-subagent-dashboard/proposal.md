# 06-13-flow-phase3-subagent-dashboard

Describe the proposed behavior change.
# 06-13-flow-phase3-subagent-dashboard

## Goal

Implement Phase 3 of `FLOW-UPGRADE-DESIGN.md`: add Fan-out family subagent helpers, a read-only dashboard, and root/template contract synchronization.

## Benefits

- Fan-out parent tasks gain a CLI surface to create and inspect child runtime contexts in one operation.
- Operators can view Flow task status, child progress, audit history, and pattern metadata without mutating state.
- Host adapters and templates advertise the new multi-child capabilities consistently for fresh projects.
- Phase 2 pattern semantics become usable in an end-to-end workflow rather than only advisory `task next` output.

## Problem

Phase 2 can model Fan-out, Pipeline, and Human-loop behavior, but Fan-out execution still requires manual child runtime context creation and manual status inspection. The design also promises a read-only Web Dashboard, yet `run.py` has no dashboard command and no static/API server exists.

## Scope

- Extend `subagent.py` with `spawn-family` and `check-family`.
- Use `agent_run` rows as the durable index for family execution state while keeping `.runtime/subagents/*.json` as the binding source of truth.
- Add a stdlib-only dashboard server with read-only API endpoints and static files.
- Register the dashboard command in `run.py`.
- Extend host adapter capability declarations and schema.
- Sync root/template runtime files, specs, workflow docs, and registry metadata.
- Add focused tests and run full verification.

## Key Assumptions

- FlowStore remains the only persistence writer for task, child, audit, block, and agent run state.
- Dashboard endpoints are read-only and never call mutating FlowStore methods.
- Host adapter execution remains outside Python runtime; `spawn-family` returns contexts for the host to dispatch.
- No third-party Python or npm dependency is added.

## Non-Goals

- No dashboard write operations.
- No automatic host-agent spawning inside `subagent.py`.
- No Phase 4 migration/release automation.
- No implementation of Pipeline stage dispatch beyond preserving current Phase 2 semantics.

## Acceptance

- `subagent spawn-family <parent>` creates missing runtime contexts for non-completed child tasks and is idempotent through active `agent_run` rows.
- `subagent check-family <parent>` returns JSON with `all_done`, `pending`, `done`, and `failed`, and exits `0` only when all child runs are done.
- `.\.cowork-flow\run.cmd dashboard [--port N]` starts a read-only HTTP dashboard and reports the final URL.
- Dashboard API returns board, task detail, children, and pattern data without opening write transactions.
- Adapter capability schema and all host `adapter.yaml` files include multi-child capabilities.
- Root and template copies stay synchronized.
- Focused Python tests, `npm run test:all`, `git diff --check`, and `.\.cowork-flow\run.cmd doctor --subagent-safety` pass.
