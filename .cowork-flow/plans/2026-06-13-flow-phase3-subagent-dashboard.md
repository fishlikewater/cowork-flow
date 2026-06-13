# Phase 3 Subagent And Dashboard Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Implement Phase 3 family subagent helpers, read-only dashboard, and root/template contract synchronization.
**Architecture:** Keep FlowStore as the single persistence boundary. `subagent.py` creates runtime context files and `agent_run` rows; `dashboard/server.py` reads FlowStore and serves stdlib HTTP/static assets. Host adapters still perform actual child dispatch.
**Verification:** `python -m pytest tests/test_subagent_dispatch.py tests/test_flow_store.py tests/test_flow_script_paths.py tests/test_host_adapters.py tests/test_no_legacy_template_paths.py tests/test_patterns.py -q`; `npm run test:all`; `git diff --check`; `.\.cowork-flow\run.cmd doctor --subagent-safety`.

## Execution Strategy

Serial work. The slices share `FlowStore`, `subagent.py`, adapter contracts, template copies, and tests, so parallel edits would increase merge risk.

## Steps

1. Add family command tests.
   - Files: `tests/test_subagent_dispatch.py`, `tests/test_flow_store.py` if needed.
   - Cover: parent with completed child skipped, missing active run creates runtime context and `agent_run`, second run returns `already_running`, `check-family` exit codes for pending/done/failed.
   - Verification: `python -m pytest tests/test_subagent_dispatch.py tests/test_flow_store.py -q` initially fails for missing commands.

2. Implement `agent_run` support and family commands.
   - Files: `.cowork-flow/scripts/flow/store.py`, `.cowork-flow/scripts/subagent.py`, `template/.cowork-flow/scripts/flow/store.py`, `template/.cowork-flow/scripts/subagent.py`.
   - Preserve existing `init/bind/close` semantics.
   - Ensure JSON output is deterministic and UTF-8 safe.
   - Verification: `python -m pytest tests/test_subagent_dispatch.py tests/test_flow_store.py -q`.

3. Add dashboard API and static UI.
   - Files: `.cowork-flow/scripts/dashboard/server.py`, `.cowork-flow/scripts/dashboard/static/index.html`, `.cowork-flow/scripts/dashboard/static/app.js`, `.cowork-flow/scripts/dashboard/static/style.css`, `.cowork-flow/scripts/run.py`.
   - Endpoints: `/`, `/api/board`, `/api/task/<id>`, `/api/task/<id>/children`, `/api/patterns`, `/static/*`.
   - No POST/PUT/DELETE endpoints.
   - Verification: focused dashboard tests or subprocess smoke test proving JSON endpoints and port fallback.

4. Sync adapter contracts and workflow docs.
   - Files: `.cowork-flow/spec/adapter.schema.json`, `.cowork-flow/adapters/*/adapter.yaml`, `.cowork-flow/spec/subagent-dispatch.md`, `.cowork-flow/spec/capabilities.md`, `.cowork-flow/spec/registry.json`, `.cowork-flow/workflow.md`.
   - Add `spawnMultipleSubagents` and `waitMultipleChildren` as declared capabilities.
   - Verification: `python -m pytest tests/test_host_adapters.py -q`.

5. Sync template files.
   - Files: matching `template/.cowork-flow/...` copies for scripts, specs, workflow, adapters, and dashboard static files.
   - Verification: template parity tests and `tests/test_no_legacy_template_paths.py`.

6. Final integrated check and task closure.
   - Run focused Python tests.
   - Run `npm run test:all`.
   - Run `git diff --check`.
   - Run `.\.cowork-flow\run.cmd doctor --subagent-safety`.
   - Move task to review/complete only after all declared gates have command output evidence.

## Acceptance Mapping

- Family command idempotency: steps 1 and 2.
- Dashboard read-only board/task APIs: step 3.
- Adapter capability declaration: step 4.
- Root/template synchronization: step 5.
- Full verification: step 6.

## Remaining Risks

- Existing `agent_run` fields may need small FlowStore helper extensions for detail views.
- Dashboard API tests should avoid brittle HTML assertions and focus on JSON contracts.
