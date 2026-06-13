# Phase 4 Release Validation Design

## Architecture

Phase 4 is a release gate, not a new runtime subsystem. The main implementation surface is automated validation around the installed CLI/template, plus a small CLI contract fix so the documented migration command maps to the existing `flow.migrate.run_migration()` implementation.

`FlowStore` remains the only SQLite writer. Migration keeps its current transaction behavior and backup flow; the CLI layer only exposes the existing behavior through `.cowork-flow/run flow migrate`.

## Validation Flow

1. Run the Node CLI test suite, template Python suite, and package dry-run through `npm run test:all`.
2. Create a fresh temp project with `cowork-flow init --platform codex`.
3. Use the installed template runner to create one `fan_out`, one `pipeline`, and one `human_loop` task, then advance each far enough to prove lifecycle commands and pattern metadata are wired.
4. Create an old-style temp project with only `task.json` task directories, run `.cowork-flow/run flow migrate`, then verify:
   - SQLite rows were created.
   - `.cowork-flow/tasks` was replaced with a new empty task root.
   - `.cowork-flow/tasks.backup` contains the old task dirs.
   - `.gitignore` excludes `tasks.backup/` and `.cowork-flow/cowork-flow.db`.
5. Run `npm pack --dry-run --json` through the existing pack checker.
6. Prepare changelog notes. Publish is intentionally a manual external action.

## CLI Contract

`store.py` owns the `flow` command group today. Add a `migrate` subcommand there that delegates to the existing migration module. This preserves `.cowork-flow/run flow init-db` and makes the documented `.cowork-flow/run flow migrate` command available in root and template copies.

## Release Boundary

Phase 4 may create release notes and dry-run package evidence. It must not mutate npm registry state or create tags unless the user explicitly approves release execution.

## Risks

- Running migration tests in the real repository would rename live task directories, so acceptance tests must run only in temp projects.
- Package dry-run can be slow on Windows; keep it as the release gate because it proves npm `files` behavior.
- The shell release script may be unavailable on Windows hosts; Phase 4 validates release behavior without invoking real publish.
