# Definition of Done

> Project-level completion gates. Every change must satisfy these before it is considered "done". They complement per-task ACs; they do not replace them.

## General gates (all tasks)

| # | Check | Verification |
|---|---|---|
| G1 | Implementation satisfies the decision-anchor acceptance criteria | All ACs are verified |
| G2 | Behavior changes have corresponding tests or an explicit verification command; high-risk tasks cover failure, boundary, or regression paths | `./.cowork-flow/run task next <dir> --validate` and the task verification commands pass |
| G3 | Check phase is complete with no unresolved blocker | `task-review` verdict is pass, and the completion lifecycle blocker count is 0 |
| G4 | No newly introduced lint/type/build warnings | lint / build commands pass |
| G5 | Git status snapshot contains only task-related changes, including staged, unstaged, and untracked | git status --porcelain=v1 -uall |

## L0 only (docs/format/comments only)

| # | Check |
|---|---|
| L0-1 | Change is confirmed non-behavioral (docs/format/comments only) |
| L0-2 | `git diff --check` reports no whitespace errors |

## L1 only (single-module behavior change)

| # | Check |
|---|---|
| L1-1 | Brainstorming record exists |
| L1-2 | Changes do not spread into unrelated modules (git diff range matches task.scope) |

## L2 only (cross-layer / architecture / migration)

| # | Check |
|---|---|
| L2-1 | proposal.md / spec.md / design.md are complete |
| L2-2 | Structured decision review completed per Skill guidance, or explicitly recorded as not applicable |
| L2-3 | All readiness gates pass (no blocker from `task next <dir> --run`) |
| L2-4 | spec-sync Skill confirms spec synchronization, or explicitly records that no update is needed |

## DoD vs per-task AC

| DoD | AC |
|---|---|
| Project-level invariant — this task is no exception | Completion conditions specific to the decision-anchor |
| Source: spec/references/definition-of-done | Source: <task>/decision-anchor.md |
| Satisfying both = the task is truly complete |
