# Implement Phase 4 Release Validation

## Goal

Close Phase 4 of `FLOW-UPGRADE-DESIGN.md` by making the release validation path repeatable and resolving any local blockers found during validation.

## Scope

- Full local regression gate through `npm run test:all`.
- Fresh install acceptance for P1/Fan-out, P2/Pipeline, and P5/Human-loop task creation.
- CLI-level old-project migration acceptance from legacy `task.json` directories.
- Package dry-run and changelog readiness.
- Root/template parity for any runtime command changes.

## Non-Goals

- No real `npm publish` without explicit confirmation.
- No version bump, tag creation, or release commit from the release script.
- No new third-party dependencies.
- No unrelated workflow redesign.

## Key Assumptions

- Phase 1-3 behavior is the baseline and should remain stable.
- `FlowStore` remains the sole SQLite write boundary.
- Test temp projects are safe places to run migration because migration renames `.cowork-flow/tasks`.
- Windows host validation should avoid relying on POSIX shell availability.

## Acceptance Criteria

1. `npm run test:all` passes.
2. Fresh `cowork-flow init` project can create `fan_out`, `pipeline`, and `human_loop` tasks and run `task next` for each.
3. `.cowork-flow/run flow migrate` works in a temp old-style project and creates DB rows, task backup, fresh tasks dir, and gitignore entries.
4. Root and template copies stay synchronized for migration command changes.
5. Release artifacts include an updated `CHANGELOG.md` and a successful package dry-run.
6. Real `npm publish` is not executed in this task.

## Relevant Files

- `FLOW-UPGRADE-DESIGN.md`
- `package.json`
- `scripts/pack-check.js`
- `scripts/release.sh`
- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/flow/migrate.py`
- `template/.cowork-flow/scripts/flow/store.py`
- `template/.cowork-flow/scripts/flow/migrate.py`
- `test/init.test.js`
- `test/package.test.js`
- `tests/test_flow_migrate.py`
- `README.md`
- `CHANGELOG.md`

## Verification

- `python -m pytest tests/test_flow_migrate.py -q`
- `npm test`
- `npm run test:all`
- `git diff --check`
- `npm pack --dry-run --json`
