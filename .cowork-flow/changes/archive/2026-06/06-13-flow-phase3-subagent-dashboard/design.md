# Phase 3 Subagent And Dashboard Design

## Architecture

Phase 3 keeps the Phase 1 rule: `flow/store.py` is the single SQLite access layer. `subagent.py` orchestrates runtime context files and records `agent_run` index rows through FlowStore. `dashboard/server.py` only performs read queries and serves static assets.

The host adapter remains responsible for actual child-agent dispatch. `spawn-family` creates one runtime context per eligible child and returns JSON describing what the host should dispatch. `check-family` summarizes persisted child run state and lets the main session decide whether a Fan-out parent may move toward review.

## Family Runtime Flow

1. Resolve the parent task id from CLI input.
2. Load direct child tasks from FlowStore.
3. Skip child tasks whose status is `completed` or `archived`.
4. For each remaining child, check for an active `agent_run` with the requested `agent_type`.
5. If active, return `already_running`.
6. Otherwise create a normal runtime context file using the existing subagent init path.
7. Insert an `agent_run` row whose id matches `runtime_context_id`.
8. Return JSON with runtime id, child task id, agent type, status, host context key, and prompt transport.

The file context remains authoritative for binding. `agent_run` is an index for dashboard and family checks; it does not replace `.cowork-flow/.runtime/subagents/*.json`.

## Dashboard

`dashboard/server.py` uses only Python stdlib `http.server`. It injects the scripts path, opens FlowStore per request, and serves:

- `/` and `/static/*`
- `/api/board`
- `/api/task/<id>`
- `/api/task/<id>/children`
- `/api/patterns`

All endpoints are GET-only. Unsupported methods return `405`. The server chooses the requested port or the next available port within a small range and prints the final URL.

## Scope Boundary

Dashboard is an observability surface, not a workflow driver. It must not implement create/start/review/complete/block/unblock. Family commands create runtime contexts and index rows, but they do not call host-specific spawn tools.

## Key Assumptions

- Existing `subagent init`, `bind`, and `close` semantics remain compatible.
- `agent_run.status` can use `pending`, `bound`, `success`, `failed`, and `closed`.
- Existing child task statuses remain the source for Fan-out parent lifecycle gating.
- Static dashboard files can be shipped through the existing template copy model.

## Acceptance Criteria

1. Family commands are idempotent and do not create duplicate active runs for the same child and agent type.
2. `check-family` classifies runs deterministically and exits according to aggregate state.
3. Dashboard API reads current FlowStore data and returns JSON with stable fields.
4. Template and root runtime copies are synchronized.
5. Adapter schema and adapter files validate with the new capability keys.

## Risks

- Runtime context ids and agent_run ids can drift if family creation is not atomic enough; tests must verify both artifacts.
- Dashboard task ids can be ambiguous when users enter artifact dirs; API should support task id first and artifact dir fallback.
- Template sync can omit dashboard static files; verification must include template parity or install-facing tests.
