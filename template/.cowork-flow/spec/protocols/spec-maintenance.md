# Spec Maintenance Protocol

> Internal protocol loaded by implement/check agents; it is not a public Skill.

## Decision

Update `.cowork-flow/spec/` when a change introduces or changes a reusable command, API, file format, state transition, validation rule, error contract, convention, or repeated failure mode.

Do not add one-off implementation narration. Prefer the narrowest existing spec and update its index when a new topic is introduced.

## Choose Location

- `backend/` or `frontend/`: implementation contracts, signatures, examples, validation behavior, and test points.
- `guides/`: short thinking checklists and pointers to deeper specs.
- `contracts/`: cross-agent, runtime, host-adapter, or persisted-state contracts.
- `runtime/` or `schemas/`: machine-readable rules, registries, and schema-owned metadata.
- `workflow.md` or `AGENTS.md`: process rules, phase gates, collaboration rules, or task routing behavior.

## Write

Keep each update concrete:

- State the trigger and scope.
- Show the contract or command shape.
- Include good/bad cases when useful.
- State tests or checks that protect the behavior.
- Update the matching `index.md` when adding a new topic.
- Check for duplicate guidance and remove stale wording before finishing.

## Output

Every Host reports `specUpdates` as one of:

- a list of changed spec paths with the preserved contract; or
- `[]` with a concise reason that no reusable contract changed.
