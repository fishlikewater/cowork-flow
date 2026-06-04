# Template docs and verification sync

## Goal

Sync root/template workflow assets, update docs, and run final verification after
the navigator, readiness gate, and project-context generator land.

## Scope

- Mirror changed scripts into `template/`.
- Update README and workflow docs for new commands and project context.
- Update init/sync/package behavior if new template files require inclusion.
- Run focused and package-level tests.

## Dependencies

- Runs after readiness, navigator, and project-context child tasks.

## Acceptance

1. Root/template parity tests pass.
2. README documents new commands and generated context behavior.
3. Init/sync behavior includes new template assets when needed.
4. Final verification results are recorded in parent plan.

## Verification

- `python -m unittest discover -s tests`
- `npm test`
- `npm run pack:check`
- `git diff --check`
