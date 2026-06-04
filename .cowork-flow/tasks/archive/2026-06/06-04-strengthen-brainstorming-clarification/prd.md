# Strengthen brainstorming requirement clarification

## Goal

When a user raises a new or ambiguous requirement, cowork-flow should route the main session through an active brainstorming/clarification gate before PRD, planning, implementation, or fixed-agent dispatch.

## Scope

- Update root and template workflow docs to make requirement clarification an explicit planning gate.
- Update `start` and `brainstorming` skills so unclear requirements actively enter brainstorming instead of silently becoming vague PRDs.
- Keep the behavior lightweight: no extra agent/team runtime, no mandatory heavy story system, no implementation during brainstorming.
- Keep Claude skill mirrors synchronized with `.agent/skills`.
- Add tests that lock the new wording and synchronization expectations.

## Acceptance Criteria

1. `workflow.md` and template copy require active brainstorming when a new requirement is unclear, multi-approach, boundary-unclear, or behavior-changing.
2. `brainstorming` skill requires concrete outputs: goal, non-goals, assumptions, scope boundary, acceptance criteria, open questions, and recommended direction.
3. `start` skill routes new unclear requirements to brainstorming before writing PRD/plan or dispatching fixed agents.
4. Root/template and Claude skill mirrors remain synchronized.
5. Targeted workflow/agent tests pass.

## Verification

- `python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py"`
- `python -m unittest discover -s tests -p "test_cowork_agents.py"`
- `git diff --check`
