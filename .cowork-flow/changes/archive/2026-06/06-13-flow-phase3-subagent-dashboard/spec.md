# Phase 3 Subagent And Dashboard Spec

## Required Behavior

1. `subagent spawn-family <parent_id>` must resolve a Flow task parent and enumerate its direct child tasks.
2. `spawn-family` must create contexts only for child tasks whose status is not `completed` or `archived`.
3. `spawn-family` must skip a child when an active `agent_run` exists for the same child and agent type.
4. `spawn-family` output must be JSON and include enough host-neutral data for dispatch.
5. `subagent check-family <parent_id>` must return JSON with `all_done`, `pending`, `done`, and `failed`.
6. `check-family` must exit `0` only when all child runs are done and no failed run remains.
7. `dashboard/server.py` must expose read-only GET endpoints for board, task detail, children, and patterns.
8. Dashboard must not call task lifecycle mutators or provide write endpoints.
9. `run.py` must register a `dashboard` command.
10. Root and template copies of scripts, specs, workflow docs, and adapters must remain synchronized.

## Family Status Semantics

- Active statuses: `pending`, `bound`, `running`
- Done statuses: `success`, `closed`
- Failed statuses: `failed`, `cancelled`, `error`

If a child has no run and is not completed/archived, `check-family` reports it as pending with no run id.

## Adapter Capabilities

All host adapters must declare:

```yaml
capabilities:
  spawnMultipleSubagents: native
  waitMultipleChildren: native
```

The adapter schema must allow these capability keys.

## Dashboard API Contract

- `GET /api/board` returns columns grouped by task status.
- `GET /api/task/<id>` returns task detail, children, audit trail, active block, and agent runs.
- `GET /api/task/<id>/children` returns direct child tasks.
- `GET /api/patterns` returns registered pattern names and short descriptions.

## Verification Contract

The Phase 3 implementation is acceptable only when these commands pass:

```powershell
python -m pytest tests/test_subagent_dispatch.py tests/test_flow_store.py tests/test_flow_script_paths.py tests/test_host_adapters.py tests/test_no_legacy_template_paths.py tests/test_patterns.py -q
npm run test:all
git diff --check
.\.cowork-flow\run.cmd doctor --subagent-safety
```
