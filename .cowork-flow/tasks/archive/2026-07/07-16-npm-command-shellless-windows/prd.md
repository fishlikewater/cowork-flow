# P2 移除 npm Windows shell warning

## Goal

Use explicit Windows npm command execution without shell:true so pack/update commands avoid DEP0190 warnings.

## Scope

- NPM command helper
- Update/package tests
- Pack check output

## Non-Goals

- Do not change package manager
- Do not alter release script semantics

## Acceptance Criteria

1. Windows npm helper no longer returns shell:true.
2. fetchLatestVersion and runGlobalInstall still use npm-compatible commands on Windows and non-Windows.
3. Focused Node tests pass.
4. pack check passes without cowork-flow-caused DEP0190 warning.

## Relevant Files

- `src/lib/package-info.js`
- `test/update.test.js`
- `test/package.test.js`
- `scripts/pack-check.js`

## Verification

- `npm test -- test/update.test.js test/package.test.js`
- `npm run pack:check`
- `git diff --check`
