# Party Mode V2 Debate Rules And Convergence PRD

## Goal

Implement Party Mode V2 debate submissions, anti-shallow-concession validation, round advancement, convergence checks, and final reporting.

## Scope

Build on the runtime foundation. Add `post`, `respond`, `advance`, and `finalize` behavior. Enforce evidence-backed `maintain`, `revise`, and `concede` rules.

## Files

- `.cowork-flow/scripts/party_mode_v2.py`
- `template/.cowork-flow/scripts/party_mode_v2.py`
- `tests/test_party_mode_v2.py`
- `.cowork-flow/plans/2026-06-10-party-mode-v2-runtime-board.md`
- `.cowork-flow/tasks/06-10-party-mode-v2-runtime-board-design/design.md`

## Requirements

- `post` accepts only valid current-round submissions from active agents.
- `respond` accepts only current-round target posts.
- `concede` requires accepted evidence and explanation of why the previous position failed.
- `revise` requires accepted and rejected parts.
- `maintain` requires counter evidence or counter reasoning.
- `advance` must prevent incomplete phase transitions.
- `finalize` must output converged or max-rounds-unconverged reports.

## Acceptance Criteria

- Invalid submissions return deterministic errors such as `shallow_concession`, `vague_revision`, `unsupported_rebuttal`, and `target_not_in_current_round`.
- Runtime does not accept free-form child output as a board post.
- Max-rounds-unconverged output includes pro/con sides, evidence, changed positions, maintained positions, unresolved disagreements, and `stop_reason`.
- Tests simulate at least three agents.
- `rtk git diff --check` passes.

## Verification

```powershell
rtk proxy powershell -NoProfile -Command '& { python -m unittest discover -s tests -p ''test_party_mode_v2.py'' -v }'
rtk git diff --check
```
