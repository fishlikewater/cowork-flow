# Changelog

## 0.0.26 - Flow Upgrade Release Candidate

### Added

- SQLite-backed Flow task runtime with migration support for legacy `task.json` projects.
- Pattern contracts for `fan_out`, `pipeline`, and `human_loop` task workflows.
- Runtime-context-based subagent dispatch helpers, Fan-out family commands, and a read-only dashboard.
- Phase 4 release validation covering full regression, fresh install acceptance, migration acceptance, package dry-run, and publish gating.

### Changed

- Templates now ship the documented `.cowork-flow/run flow migrate` command path.
- Release notes are tracked before npm publish; real registry publish remains an explicit manual action.

### Validation

- Run `npm run test:all` before publishing.
- Run `npm pack --dry-run --json` to inspect package contents.
- Do not run `npm publish` until release credentials and final approval are confirmed.
