
# P2 收窄 template sync legacy allowlist

## Goal

Make template sync legacy exceptions narrow, intentional, and covered by focused tests.

## Scope

- src/lib/template-sync-gate.js allowlist
- Focused sync-gate tests

## Non-Goals

- Do not redesign the sync gate.
- Do not change template copy semantics outside allowlist handling.

## Acceptance Criteria

1. Every retained legacy flattened-path allowlist entry has a precise reason.
2. Obsolete allowlist entries are removed when tests show they are unnecessary.
3. Focused sync-gate tests pass.
4. pack check and git diff check pass.

## Relevant Files

- `src/lib/template-sync-gate.js`
- `test/template-sync-gate.test.js`
- `test/sync.test.js`
- `scripts/pack-check.js`

## Verification

- `npm test -- test/template-sync-gate.test.js test/sync.test.js`
- `npm run pack:check`
- `git diff --check`
