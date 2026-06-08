# Protect Party Mode Live Child Opinions

## Goal

Ensure Party Mode does not lose a still-running child agent's opinion merely because a wait call timed out.

## Scope

- Update root and template Party Mode skill copies.
- Update Claude mirror skill copies.
- Update focused tests that guard the Party Mode contract.

## Acceptance Criteria

- The skill states that a wait timeout is not a child timeout.
- If a child remains live after a wait timeout, the coordinator must wait again or report the pending child.
- The coordinator must not close, cancel, omit, or synthesize around a still-running child unless the user explicitly asks to close it.
- Four Party Mode skill copies remain identical.
- Focused tests and `git diff --check` pass.

## Non-Goals

- Do not add a scheduler, runner, or shared discussion room.
- Do not change formal `cowork-*` dispatch or host adapter behavior.
- Do not allow child agents to coordinate or directly message each other.

## Verification

```powershell
rtk python -m unittest discover -s tests -p "test_cowork_agents.py" -v
rtk git diff --check
```
