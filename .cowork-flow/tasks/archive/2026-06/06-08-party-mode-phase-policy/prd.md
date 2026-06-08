# Clarify Party Mode Phase Policy

## Goal

Clarify Party Mode round-phase behavior so `max_rounds` is only a total cap, while Challenge can continue for multiple follow-up rounds when material disagreement remains. Set the built-in default to `max_rounds=5`.

## Scope

- Update root and template Party Mode skill copies.
- Update Claude mirror skill copies.
- Update focused tests that guard the Party Mode contract.

## Acceptance Criteria

- Built-in defaults say `max_rounds=5`.
- Configurable fields avoid implying only round 2 or round 3 can be controlled.
- Round intent says Round 2+ remains Challenge while continue conditions expose material disagreement, material risk, missing evidence, or untestable acceptance criteria.
- Convergence begins only when one recommended direction is writable and no material challenge condition remains.
- Convergence does not reopen exploration without user approval or new concrete evidence.
- Four Party Mode skill copies remain identical.
- Focused tests and `git diff --check` pass.

## Non-Goals

- Do not change runtime dispatch or formal `cowork-*` behavior.
- Do not allow child-to-child direct communication.
- Do not make Party Mode satisfy Implement or Check completion.

## Verification

```powershell
rtk python -m unittest discover -s tests -p "test_cowork_agents.py" -v
rtk git diff --check
```
