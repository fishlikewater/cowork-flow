# Polish Dashboard UX And Chinese UI

## Goal

Improve the read-only Dashboard so it works as a practical workflow inspection surface and uses Simplified Chinese UI text.

## Scope

- Rework Dashboard static UI layout and interaction.
- Add Simplified Chinese labels, status names, pattern names, empty states, and detail text.
- Add status/search filters and make archived tasks visually secondary.
- Render task detail sections for audit trail, children, agent runs, and active block.
- Sync root and template Dashboard static resources.
- Add focused tests for static UI contracts and template parity.

## Non-Goals

- No lifecycle mutation controls in Dashboard.
- No FlowStore write-path changes.
- No API schema change unless absolutely necessary.
- No broader workflow redesign.

## Assumptions

- `/api/board` and `/api/task/<id>` already expose enough data for the requested UI.
- Dashboard remains stdlib-only and dependency-free.
- The in-app browser narrow viewport is an important target.

## Acceptance Criteria

1. Dashboard visible UI text is primarily Simplified Chinese.
2. Active workflow states are emphasized; archived tasks are accessible through filter/toggle and do not dominate the first screen by default.
3. Clicking a task makes details visible in the current viewport on desktop and narrow layouts.
4. Detail view renders task basics, audit trail, children, agent runs, and active block state.
5. Root/template static files stay synchronized.
6. Existing read-only API behavior remains covered and passing.

## Relevant Files

- `.cowork-flow/scripts/dashboard/static/index.html`
- `.cowork-flow/scripts/dashboard/static/app.js`
- `.cowork-flow/scripts/dashboard/static/style.css`
- `template/.cowork-flow/scripts/dashboard/static/index.html`
- `template/.cowork-flow/scripts/dashboard/static/app.js`
- `template/.cowork-flow/scripts/dashboard/static/style.css`
- `tests/test_dashboard.py`

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_dashboard.DashboardTest -v`
- `rtk npm run test:template`
- `rtk git diff --check`
- Browser smoke at `http://127.0.0.1:8080/`.
