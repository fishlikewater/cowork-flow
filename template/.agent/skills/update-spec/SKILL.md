---
name: update-spec
description: Use when implementation lessons, contracts, conventions, or gotchas should be captured in .cowork-flow/spec.
---

# Update Spec

Use this when a change teaches something future agents need to know.

## Decide Whether To Update

Update specs when you learned:

- A command, API, file, payload, or state contract.
- A validation rule or error behavior.
- A project convention.
- A repeated failure mode or non-obvious gotcha.
- A design decision future changes must preserve.

Skip one-off implementation details that do not guide future work.

## Choose Location

- `backend/` or `frontend/`: implementation contracts, signatures, examples, validation behavior, test points.
- `guides/`: short thinking checklists and pointers to deeper specs.
- `.cowork-flow/workflow.md`: process rules, phase gates, or task routing behavior.
- `AGENTS.md`: project-level collaboration rules.

## Write

Keep each update concrete:

- State the trigger and scope.
- Show the contract or command shape.
- Include good/bad cases when useful.
- State tests or checks that protect the behavior.
- Update the matching `index.md` when adding a new topic.

Before finishing, check for duplicate guidance and remove stale wording.
