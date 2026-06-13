# Phase 4 Release Validation Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Close Phase 4 with release-grade validation for full tests, fresh install workflow, old-project migration, package dry-run, and changelog.
**Architecture:** Keep the runtime behavior from Phases 1-3. Add CLI-level migration exposure and automated acceptance tests around installed-template behavior; publish remains a manual external action.
**Verification:** `python -m pytest tests/test_flow_migrate.py -q`; `npm test`; `npm run test:all`; `git diff --check`; `npm pack --dry-run --json`.

## Execution Strategy

Serial work. The release gate shares `package.json`, template runner files, migration CLI, README/changelog, and tests, so serial edits reduce cross-file drift.

## Steps

1. Add failing acceptance coverage for Phase 4 gaps.
   - Files: `tests/test_flow_migrate.py`, `test/init.test.js`, `test/package.test.js`.
   - Cover: documented `flow migrate` CLI, fresh P1/P2/P5 task creation from `init`, package/changelog inclusion.
   - Verification: focused tests fail before implementation where CLI/changelog are missing.

2. Expose `flow migrate` through root and template command groups.
   - Files: `.cowork-flow/scripts/flow/store.py`, `template/.cowork-flow/scripts/flow/store.py`.
   - Delegate to `flow.migrate` without duplicating migration logic.
   - Verification: `python -m pytest tests/test_flow_migrate.py -q`.

3. Prepare release documentation artifacts.
   - Files: `CHANGELOG.md`, `README.md` if release instructions need precision, `FLOW-UPGRADE-DESIGN.md` if Phase 4 notes need current status.
   - Record Phase 1-4 scope and publish boundary.
   - Verification: `npm pack --dry-run --json` includes `CHANGELOG.md` if package metadata includes it, or README documents external changelog if not shipped.

4. Run integrated gates.
   - Commands: `npm test`, `npm run test:all`, `git diff --check`, `npm pack --dry-run --json`.
   - Expected result: all local gates pass; no `npm publish` executed.

5. Move task to review/complete only after evidence exists.
   - Commands: `.\.cowork-flow\run.cmd task review .cowork-flow/tasks/06-13-flow-phase4-release-validation`, then final check, then `task complete`.
   - Expected result: task complete, pending only human-approved publish.

## Acceptance Mapping

- Full regression: step 4.
- Fresh install P1/P2/P5: step 1.
- Old project migration: steps 1 and 2.
- Release artifacts/changelog: step 3.
- Publish boundary: steps 3 and 4.

## Remaining Risks

- Real npm credentials and registry publish are intentionally unverified until the user approves publish.

## Execution Evidence

- Added CLI acceptance for `.cowork-flow/run flow migrate` against a temp old-style project.
- Added fresh install acceptance that initializes a new project and starts `fan_out`, `pipeline`, and `human_loop` workflows.
- Added package coverage for `CHANGELOG.md` and included it in npm package files.
- Ran `python -m pytest tests/test_flow_migrate.py -q`: 6 passed.
- Ran `npm test`: 44 passed, 4 skipped on Windows because POSIX shell is unavailable.
- Ran `npm run test:template`: 225 passed, 6 skipped on Windows POSIX-runner cases.
- Ran `npm run pack:check`: package dry-run includes `CHANGELOG.md`.
- Ran `npm run test:all`: passed.
- Ran `git diff --check`: passed.
- Ran `.\.cowork-flow\run.cmd doctor --subagent-safety`: passed.
- Did not run `npm publish`; publish remains gated by explicit user confirmation.
