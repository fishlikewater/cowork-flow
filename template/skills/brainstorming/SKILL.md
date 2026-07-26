---
name: brainstorming
description: Use when requirements are unclear, a requested change has multiple valid approaches, or the user wants to shape an idea before implementation.
---

# Brainstorming

Use this skill as the active clarification gate for new requirements. Turn an idea into a clear change request before decision-anchor, planning, fixed-agent dispatch, or code changes begin.

## Flow

1. Read only the context needed to understand the project area: `AGENTS.md`, `task next --json`, Skill command manifests, and relevant spec indexes.
2. State the goal, non-goals, assumptions, scope boundary, success criteria, and the smallest useful scope.
3. Ask one high-value question only when the answer cannot be inferred safely; otherwise proceed with explicit assumptions.
4. Present 2-3 viable approaches when trade-offs matter, with a concrete recommended direction.
5. Do not write decision-anchor, planning, or fixed-agent dispatch input until the direction and acceptance criteria are clear.
6. For L1/L2 work, create or update change/task artifacts required by runtime gates and `.cowork-flow/spec/` after the clarification output is stable.
7. Hand off to `task-planning` when the requested behavior and acceptance criteria are clear.

## Output

Keep the result practical:

- Goal.
- Non-goals.
- Key assumptions.
- Scope boundary, including in-scope and out-of-scope work.
- Recommended direction and rejected alternatives.
- Acceptance criteria.
- Open questions, risks, or blockers, with their impact on the next step.

Do not implement during brainstorming unless the user explicitly changes the request to a direct edit.
