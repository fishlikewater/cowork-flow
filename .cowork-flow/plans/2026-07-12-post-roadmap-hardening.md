
# Post-roadmap Hardening Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Resolve the remaining post-roadmap ambiguity around historical docs, legacy sync-gate exceptions, and roadmap task archive consistency.
**Architecture:** Execute three small serial tasks. First clarify historical design-document boundaries, then review sync-gate allowlist behavior with tests, then align baseline task archive status or document the reason it remains completed.
**Verification:** Each task has focused validation; final closeout runs `git diff --check`, relevant Node/Python tests, `doctor --release-health`, `doctor --subagent-safety`, `change validate`, and task status checks.

Execution strategy: serial. The tasks are small, but they all touch workflow trust surfaces; serial execution avoids overlapping state/archive changes and keeps review simple.

## Task 1 — Historical design document boundaries

- [ ] Task: `07-12-followup-historical-doc-boundaries`
- Priority / level: P2 / L0
- Goal: Make historical migration docs clearly non-authoritative for current runtime state.
- Files:
  - `FLOW-UPGRADE-DESIGN.md`
  - `README.md`
  - `.cowork-flow/workflow.md`
  - `.cowork-flow/spec/core/dispatch.md`
  - `.cowork-flow/spec/core/lifecycle.md`
- Steps:
  1. Add a short status note near the top of `FLOW-UPGRADE-DESIGN.md` that identifies it as historical migration design.
  2. Link or name the current authority docs for runtime state.
  3. Confirm old state references in `FLOW-UPGRADE-DESIGN.md` remain framed as migration/compatibility context.
  4. Scan current authority docs for old runtime-state wording.
- Verification:
  - `rg -n "workflow-state-templates\.md|task\.json\.status|\.runtime/subagents|\.runtime/sessions" README.md .cowork-flow/workflow.md .cowork-flow/spec/core/dispatch.md .cowork-flow/spec/core/lifecycle.md`
  - `git diff --check`

## Task 2 — Template sync legacy allowlist review

- [ ] Task: `07-12-followup-sync-gate-legacy-allowlist`
- Priority / level: P2 / L1
- Goal: Ensure sync-gate legacy allowlist entries are intentional, tested, and as narrow as possible.
- Files:
  - `src/lib/template-sync-gate.js`
  - `test/template-sync-gate.test.js`
  - `test/sync.test.js`
- Steps:
  1. Inspect every `legacy flattened` allowlist entry and map it to the current template path.
  2. Remove entries whose legacy root path no longer exists or no longer needs exemption.
  3. For retained entries, make the reason precise and add/adjust tests that fail on unintentional current-asset drift.
  4. Run focused sync-gate/package tests.
- Verification:
  - `npm test -- test/template-sync-gate.test.js test/sync.test.js`
  - `npm run pack:check`
  - `git diff --check`

## Task 3 — Baseline archive consistency

- [ ] Task: `07-12-followup-baseline-archive-consistency`
- Priority / level: P3 / L0
- Goal: Resolve or document the only remaining 07-11 roadmap status inconsistency.
- Files:
  - `.cowork-flow/tasks/07-11-opt-baseline-risk-map/`
  - `.cowork-flow/tasks/archive/2026-07/`
  - `.cowork-flow/plans/2026-07-11-workflow-optimization-roadmap.md`
  - `.cowork-flow/workspace/codex/index.md`
  - `.cowork-flow/workspace/codex/journal-*.md`
- Steps:
  1. Verify `07-11-opt-baseline-risk-map` has no active dependency and the roadmap change is archived.
  2. Run `task next 07-11-opt-baseline-risk-map` and inspect blockers.
  3. If safe, archive the task and record a session; if not safe, document the reason in the plan/task quality evidence.
  4. Confirm active task remains empty and all 07-11 tasks have expected status.
- Verification:
  - `.cowork-flow/run.cmd task next 07-11-opt-baseline-risk-map`
  - `.cowork-flow/run.cmd task list`
  - `.cowork-flow/run.cmd task current`
  - `git diff --check`

## Final integration

- [ ] `git status --short` shows only expected plan/change/task/archive/session files.
- [ ] `git diff --check`.
- [ ] `npm test -- test/template-sync-gate.test.js test/sync.test.js`.
- [ ] `npm run pack:check`.
- [ ] `.cowork-flow/run.cmd doctor --release-health`.
- [ ] `.cowork-flow/run.cmd doctor --subagent-safety`.
- [ ] `.cowork-flow/run.cmd change validate 07-12-post-roadmap-hardening`.
