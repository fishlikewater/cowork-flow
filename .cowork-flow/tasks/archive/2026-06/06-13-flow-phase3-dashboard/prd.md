# Implement Phase 3 Read-Only Dashboard

## Goal

Add a stdlib-only read-only dashboard command and API for Flow board inspection.

## Scope

- Create dashboard server and static files.
- Register `dashboard` in `run.py`.
- Provide board, task detail, children, and patterns endpoints.
- Add API smoke tests and template copies.

## Non-Goals

- No POST/PUT/DELETE endpoints.
- No frontend build step or npm dependency.
- No lifecycle mutation through dashboard.

## Acceptance Criteria

1. `run.cmd dashboard` starts the server and prints a URL.
2. Board and task APIs return stable JSON from FlowStore.
3. Unsupported write methods return non-success.
4. Dashboard files are synced to template.

## References

- `FLOW-UPGRADE-DESIGN.md`
- `.cowork-flow/plans/2026-06-13-flow-phase3-subagent-dashboard.md`
