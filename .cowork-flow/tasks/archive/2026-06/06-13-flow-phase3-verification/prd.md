# Verify Phase 3 Integration

## Goal

Run integrated Phase 3 verification and close the Fan-out parent only after evidence exists.

## Scope

- Run focused Python tests for family commands, FlowStore, dashboard paths, adapters, templates, and patterns.
- Run `npm run test:all`.
- Run `git diff --check`.
- Run `doctor --subagent-safety`.
- Confirm task/change state consistency before review/complete/archive.

## Non-Goals

- Do not expand implementation scope during verification except to fix in-scope failures.
- Do not archive or commit unrelated `.codegraph/` noise.

## Acceptance Criteria

1. All declared verification commands pass or failures are fixed in scope.
2. `git status --short` contains only expected Phase 3 files plus known ignored/untracked `.codegraph/`.
3. Parent and child task statuses reflect completed work.

## References

- `.cowork-flow/plans/2026-06-13-flow-phase3-subagent-dashboard.md`
