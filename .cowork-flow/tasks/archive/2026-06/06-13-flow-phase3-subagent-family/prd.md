# Implement Phase 3 Subagent Family Commands

## Goal

Add `subagent spawn-family` and `subagent check-family` for Fan-out child runtime context management.

## Scope

- Extend `subagent.py` command parsing.
- Create runtime contexts for eligible children.
- Record and query `agent_run` rows.
- Add behavior tests for idempotency, skip rules, and exit codes.
- Sync template copy.

## Non-Goals

- Do not dispatch real host children from Python.
- Do not change fixed-agent binding semantics.

## Acceptance Criteria

1. `spawn-family` skips completed/archived children.
2. `spawn-family` does not duplicate active runs.
3. `check-family` classifies pending/done/failed states and returns correct exit codes.
4. Focused subagent tests pass.

## References

- `.cowork-flow/plans/2026-06-13-flow-phase3-subagent-dashboard.md`
- `.cowork-flow/spec/subagent-dispatch.md`
