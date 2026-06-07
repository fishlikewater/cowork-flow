# Clarify Party Mode Round Intent

## Goal

Clarify `party-mode` round intent so custom `max_rounds` values use phase semantics instead of fixed round-number semantics.

## Scope

- Update root/template/Claude `party-mode` skills.
- Update tests that pin Party Mode skill wording.
- Do not change runtime dispatch, task lifecycle, or Party Mode defaults.

## Acceptance Criteria

- Round intent defines Opening, Challenge, and Convergence phases.
- Default mapping states Round 1 = Opening, Round 2 = Challenge, Round 3+ = Convergence.
- Rounds after convergence may verify, narrow, or choose, but must not open new directions.
- Only the user can restart exploration after convergence begins.
- Root/template/Claude skill copies remain identical.
- Targeted skill tests and `git diff --check` pass.
