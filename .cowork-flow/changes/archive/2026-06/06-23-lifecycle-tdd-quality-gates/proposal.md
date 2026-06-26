# Lifecycle TDD Quality Gates

## Problem

Current workflow text asks AI to use TDD, run meaningful checks, follow coding standards, and respect agent boundaries, but several requirements still live mainly in prompts and documentation. `task review` and `task complete` do not yet require machine-readable evidence for red/green TDD, coding-standard checks, or final review completeness.

## Proposed Change

Implement the plan in `.cowork-flow/plans/2026-06-23-lifecycle-tdd-quality-gates.md`.

The change introduces:

- A shared quality gate kernel.
- A concise TDD execution skill.
- TDD evidence enforcement in `task review`.
- Completion evidence enforcement in `task complete`.
- Shallow-test rejection.
- Coding-standard scanning.
- Shared agent safety policy for `doctor` and tests.
- Workflow/spec/skill contract synchronization.

## Benefits

- Eliminates self-reported compliance by replacing prompt-only guidance with machine-readable evidence.
- Prevents untested behavior changes from entering the review and completion stages.
- Rejects shallow placeholder tests that pass without proving behavior.
- Unifies agent safety enforcement across `doctor` and test paths so advisory-agent drift is detected in both.
- Keeps root and template mirrors aligned through contract tests.

## Non-Goals

- Do not add a new workflow DSL or independent validation engine.
- Do not make git worktree double-patch replay the default evidence path.
- Do not reintroduce removed pattern types.
- Do not enforce TDD for docs-only or pure configuration tasks.

## Key Assumptions

- Implementers will record command output honestly; the gate validates evidence shape and consistency, not that every byte of captured output is authentic.
- The existing `task.py` CLI is the right surface for lifecycle enforcement; no new CLI entry points are needed.
- Template mirror tests already verify root/template synchronization and will catch copy drift.
- The advisory-agent drift in `.codex/agents/default.toml` can be fixed as part of the implementation without breaking existing workflows.

## Impact

AI implementers will receive clearer TDD guidance before coding, but lifecycle state transitions will rely on validators and recorded command evidence rather than self-reported compliance.
