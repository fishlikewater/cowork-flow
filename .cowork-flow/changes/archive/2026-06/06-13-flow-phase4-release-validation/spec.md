# Phase 4 Release Validation Spec

## Release Gate

- `npm run test:all` is the canonical local release gate.
- Package validation must run `npm pack --dry-run --json` and inspect the returned file list.
- Generated Python caches and task backup directories must not be shipped.

## Migration CLI

- `.cowork-flow/run flow migrate` must invoke the existing `flow.migrate.run_migration()` path.
- On success, it must move the old `.cowork-flow/tasks` directory to `.cowork-flow/tasks.backup`.
- It must recreate `.cowork-flow/tasks/archive`.
- It must append `tasks.backup/` and `.cowork-flow/cowork-flow.db` to `.gitignore` when missing.
- It must return non-zero before moving directories if migration fails.

## Fresh Install Acceptance

- A freshly initialized project must support `task create` with:
  - `--pattern fan_out`
  - `--pattern pipeline --meta '{"stages":[...]}'`
  - `--pattern human_loop --meta '{"decision_points":[...]}'`
- `task next` must report a safe next action for each created task.
- No third-party dependencies may be added.

## Publish Boundary

- Phase 4 may prepare changelog, package dry-run evidence, and release commands.
- Phase 4 must not execute `npm publish` without explicit user confirmation.
