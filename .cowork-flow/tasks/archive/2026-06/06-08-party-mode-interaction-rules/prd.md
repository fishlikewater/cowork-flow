# Clarify Party Mode Interaction Rules

## Goal

Improve the Party Mode skill description so real child-agent discussions feel like traceable roundtable interaction, not parallel reports or vote counting.

## Scope

- Update root and template Party Mode skill copies for Codex-style agents.
- Update root and template Claude mirror skill copies.
- Update focused tests that guard the skill contract.

## Acceptance Criteria

- The skill requires coordinator-visible agent or lens selection reasons.
- Follow-up rounds prefer the same live child agent for the relevant position and ask it to respond to evidence-backed disagreement.
- Child output schema supports follow-up-only response/delta fields without removing core fields.
- Coordinator output includes effective config and round-use fields so custom `max_agents` and `max_rounds` remain clear.
- Four Party Mode skill copies remain identical.
- Focused agent skill tests and `git diff --check` pass.

## Non-Goals

- Do not change runtime dispatch, task lifecycle, archive, commit, or formal `cowork-*` gates.
- Do not allow child agents to communicate directly or dispatch other agents.
- Do not make Party Mode satisfy Implement or Check completion.

## Verification

```powershell
rtk python -m unittest discover -s tests -p "test_cowork_agents.py" -v
rtk git diff --check
```
