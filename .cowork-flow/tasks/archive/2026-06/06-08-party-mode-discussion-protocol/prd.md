# Clarify Party Mode 1.5 Discussion Protocol

## Goal

Make Party Mode's hosted child-agent discussion read like a real moderator-led debate without making the skill verbose or creating a separate discussion runtime.

## Scope

- Update root and template Party Mode skill copies.
- Update Claude mirror skill copies.
- Update focused tests that guard the Party Mode contract.

## Acceptance Criteria

- The skill requires the coordinator to build a compact claim table before follow-up rounds.
- Follow-up prompts must target a concrete `claim_id`, owner, counterclaim, and evidence gap.
- Challenge rounds default to scrutiny but still allow agreement when evidence compels it.
- Final synthesis must preserve a compact round/agent/claim transcript shape.
- The added text is concise and non-redundant.
- Four Party Mode skill copies remain identical.
- Focused tests and `git diff --check` pass.

## Non-Goals

- Do not create a shared discussion room runtime.
- Do not allow child agents to communicate directly or dispatch other agents.
- Do not change formal `cowork-*` gates or make Party Mode satisfy Implement/Check completion.

## Verification

```powershell
rtk python -m unittest discover -s tests -p "test_cowork_agents.py" -v
rtk git diff --check
```
