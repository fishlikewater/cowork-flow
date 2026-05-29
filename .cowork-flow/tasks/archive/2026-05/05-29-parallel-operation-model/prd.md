# Adopt external project Parallel Operation Model

## Goal

Adopt a clean-room parallel operation model for cowork-flow.

## Requirements

- Document that independent tasks should run as separate sessions, preferably with separate git worktrees when they may write files.
- Document that single-task internal parallelism is limited to low-conflict, explicitly scoped child work.
- Keep the fixed `cowork-*` agents as leaf executors.
- Require the main session to wait for every spawned child, inspect outputs, verify claimed files/commands, list live agents, and close children.
- Require plans to describe file ownership, dependencies, expected outputs, and verification for parallel work items.
- Keep the new default path independent of legacy `agent-team prepare/next/collect/retry/complete`.

## Scope

- Update workflow docs in root and template.
- Update plan/start skills in root and template if needed.
- Update tests that lock the fixed-agent workflow contract.

## Out of Scope

- Do not restore the old `agent-team` state machine.
- Do not add a second task state store.
- Do not copy external source, templates, or proprietary text.

## Verification

- `python -m unittest tests.test_workflow_parallel_sessions tests.test_cowork_agents tests.test_no_legacy_template_paths -v`
- `npm run test:all`
- `git diff --check`
