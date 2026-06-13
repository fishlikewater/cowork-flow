# 06-13-flow-phase4-release-validation

## Goal

Close Phase 4 of `FLOW-UPGRADE-DESIGN.md` with repeatable release validation, fresh install acceptance, old project migration acceptance, and release artifacts ready for a human-approved npm publish.

## Problem

Phase 1-3 implemented the Flow runtime, patterns, subagent family helpers, and dashboard, but Phase 4 still needs release-grade evidence. The design also references `.cowork-flow/run flow migrate`, while the current `flow` command only exposes `init-db`, so the old-project migration path is not executable through the documented CLI.

## Benefits

- Users get a documented release gate with local evidence before npm publish.
- Existing projects get a reliable migration command instead of a Python-module-only path.
- Fresh installs prove the P1/P2/P5 pattern flows are usable from a clean template.

## User Value

The release can be shipped with confidence because install, migration, package contents, and changelog are verified before any external publish action.

## Scope

- Add or fix automated checks for the documented Phase 4 acceptance paths.
- Make the documented `flow migrate` command executable from installed templates.
- Verify fresh `cowork-flow init` projects can create and advance P1/P2/P5-style tasks.
- Verify old `task.json` projects can migrate through the CLI with backup and gitignore safeguards.
- Prepare changelog/release notes and package dry-run evidence.

## Non-Goals

- Do not run `npm publish` without explicit user confirmation.
- Do not change package version as part of validation.
- Do not add third-party npm or Python dependencies.
- Do not redesign Phase 1-3 runtime behavior beyond fixing release-blocking gaps.

## Acceptance

1. `npm run test:all` passes.
2. A fresh install/init acceptance test covers task creation for `fan_out`, `pipeline`, and `human_loop` patterns.
3. A CLI-level old-project migration test covers `flow migrate`, task backup, `.gitignore` update, and migrated DB rows.
4. Package dry-run includes required CLI/template assets and excludes generated caches.
5. `CHANGELOG.md` records the Phase 1-4 upgrade scope and release notes.
6. Real `npm publish` remains gated on explicit human confirmation.
