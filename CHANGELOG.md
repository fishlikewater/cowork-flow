# Changelog

## 0.0.47 - 2026-08-05

### Release readiness

- Added `npm run release:check` as the documented local release confidence gate. It currently delegates to `npm run test:all`, which runs Node full tests, template full tests, and `pack:check`.
- Added this changelog to summarize release highlights and publish-time verification notes.

### Runtime and workflow hardening

- Hardened runtime context lifecycle, recovery observability, and fixed-subagent binding diagnostics.
- Added Batch execution inspect facts, stronger Host action result validation, and documented Batch recovery behavior.
- Normalized runtime-health and task-review issue facts so review output is easier to consume.

### Host assets and integrations

- Centralized Host Asset Manifest sync policy helpers and added a Host capability matrix contract.
- Protected the ZCode multi-module scaffold boundary so plugin scaffolding does not vendor `.cowork-flow/` runtime files into module directories.

### Party Mode

- Extracted Party Mode board storage, enriched final report facts, and aligned Host action fallbacks with the capability matrix boundary.
- Preserved the advisory-only contract: Party Mode does not advance task lifecycle state and does not replace implement/check review.

### Sync, update, and support UX

- Added `sync --dry-run` readiness reports covering would-copy, protected skips, obsolete removals, Host asset refresh, pending recovery, and warnings.
- Added `update --dry-run` readiness output so CLI updates can be previewed without installing.
- Added the product support and troubleshooting playbook for task routing, runtime binding, Batch, Host asset drift, Party Mode, and release checks.

### Verification

- Release gate: `npm run release:check`
- Formatting gate: `git diff --check`
- Windows note: POSIX-shell-only release tests may be reported as skipped when POSIX shell is unavailable; skips must remain visible and must not be reported as passes.

### Publish notes

- This entry documents the current `0.0.47` release candidate. It does not tag, publish, or bump the package version by itself.
- Before publishing, confirm the version in `package.json`, `package-lock.json`, `template/.cowork-flow/.version`, and `template/.zcode/.zcode-plugin/plugin.json` matches the intended release.
