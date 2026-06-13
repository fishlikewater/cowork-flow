# Dashboard UX Chinese UI Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Make the read-only Dashboard more useful and switch the page UI to Simplified Chinese.
**Architecture:** Keep server APIs read-only and unchanged. Rework static HTML/CSS/JS to add Chinese labels, status filters, compact empty states, visible task detail, audit timeline, children, agent runs, and active block sections. Sync root/template static files.
**Verification:** focused dashboard tests, `npm run test:template`, `git diff --check`, browser smoke at `http://127.0.0.1:8080/`.

## Execution Strategy

Serial work. The static files and tests are tightly coupled, and root/template parity is required.

## Steps

1. Add focused regression coverage.
   - File: `tests/test_dashboard.py`.
   - Assert root/template dashboard static files stay synchronized.
   - Assert `index.html` has `lang="zh-CN"` and Simplified Chinese shell text.
   - Assert `app.js` contains Chinese status/pattern labels, archived filter behavior, and detail sections for audit, children, agent runs, and active block.
   - Verification: focused test fails before implementation if old UI remains.

2. Rework Dashboard static UI.
   - Files: `.cowork-flow/scripts/dashboard/static/index.html`, `app.js`, `style.css`.
   - Add Chinese topbar, search/filter controls, status tabs, active/archived split, selected task state, detail inspector/drawer, timeline/details rendering, and compact empty states.
   - Keep all behavior read-only and GET-only.
   - Verification: focused test passes.

3. Sync template assets.
   - Files: `template/.cowork-flow/scripts/dashboard/static/index.html`, `app.js`, `style.css`.
   - Copy the same static resources to template.
   - Verification: template parity test passes.

4. Integrated verification.
   - Commands:
     - `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_dashboard.DashboardTest -v`
     - `rtk npm run test:template`
     - `rtk git diff --check`
   - Browser smoke: reload the in-app browser, verify Chinese UI, archived toggle, task detail visibility, and no console errors.

5. Workflow closeout.
   - Move task to review, run cowork-check, complete, archive, add session, and commit if verification passes.

## Acceptance Mapping

- Simplified Chinese page text: steps 1-2.
- Archived no longer dominates first screen: steps 1-2.
- Details visible after click: steps 1-2 and browser smoke.
- Audit/children/agent runs/block detail: steps 1-2.
- Root/template parity and read-only preservation: steps 1-4.
