# Fix test all contracts

## Goal

Make `npm run test:all` pass without changing production/runtime code.

## Scope

- Allowed: tests and task context for this verification fix.
- Forbidden: production/runtime code under `.cowork-flow/scripts`, `src`, `bin`, or template runtime scripts.

## Acceptance

- Reproduce current `npm run test:all` failure.
- Update only stale test expectations if root cause is contract drift in tests.
- Run targeted failing template tests.
- Run full `npm run test:all`.
