# Harden Dashboard Runtime Control

## Goal

Fix Dashboard correctness gaps around real subagent runtime visibility, archived-task browsing, archived filter state, and project-local server lifecycle commands.

## Scope

- Record direct formal `subagent init` runs in Flow `agent_run`.
- Preserve existing status updates through `bind` and `close`.
- Improve archived Dashboard display into a full-width history layout.
- Keep archived tab and `显示归档` checkbox independent.
- Add `dashboard serve/start/status/stop` scoped to the current repository.
- Sync root and template implementations.
- Add focused tests for runtime, CLI, UI contract, and parity.

## Non-Goals

- No Dashboard task mutation controls.
- No global Dashboard daemon.
- No schema migration beyond using the existing `agent_run` table.
- No broad redesign of the Dashboard API.

## Acceptance Criteria

1. Direct formal subagent init for a known task creates one `agent_run`.
2. Binding and closing that runtime update the same `agent_run`.
3. Dashboard task detail can show those real direct formal agent runs.
4. Archived tasks render as a full-width history section, not a left-only board column.
5. The archived status tab does not toggle the `显示归档` checkbox or leak archived visibility after switching tabs.
6. CLI commands can start, inspect, and stop only the current project's Dashboard server.
7. Root/template files remain in sync.

## Relevant Files

- `.cowork-flow/scripts/subagent.py`
- `template/.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/dashboard/server.py`
- `template/.cowork-flow/scripts/dashboard/server.py`
- `.cowork-flow/scripts/dashboard/static/app.js`
- `.cowork-flow/scripts/dashboard/static/style.css`
- `template/.cowork-flow/scripts/dashboard/static/app.js`
- `template/.cowork-flow/scripts/dashboard/static/style.css`
- `.cowork-flow/spec/subagent-dispatch.md`
- `tests/test_subagent_dispatch.py`
- `tests/test_dashboard.py`

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_subagent_dispatch.SubagentDispatchTest tests.test_dashboard.DashboardTest -v`
- `rtk npm run test:template`
- `rtk git diff --check`
- Browser smoke at `http://127.0.0.1:8080/`.
