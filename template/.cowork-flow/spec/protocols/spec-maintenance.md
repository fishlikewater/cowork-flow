# Spec Maintenance Protocol

> Internal protocol loaded by implement/check agents; it is not a public Skill.

## Decision

Update `.cowork-flow/spec/` when a change introduces or changes a reusable command, API, file format, state transition, validation rule, error contract, convention, or repeated failure mode.

Do not add one-off implementation narration. Prefer the narrowest existing spec and update its index when a new topic is introduced.

## Output

Every Host reports `specUpdates` as one of:

- a list of changed spec paths with the preserved contract; or
- `[]` with a concise reason that no reusable contract changed.
