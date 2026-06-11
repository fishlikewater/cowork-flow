# Party Mode V2 Runtime Hardening Spec

## Requirements

- Party Mode V2 MUST reject unsafe `discussion_id` and `agent_id` values before writing files.
- Runtime state writes MUST be safe under parallel child submissions.
- Child submissions MUST include the current round when current-round-only mode is enabled.
- A child MUST NOT respond to its own post.
- A child MUST NOT respond twice to the same target in the same round.
- A child MUST NOT exceed `max_rebuttal_targets_per_agent`.
- Stored responses MUST retain the decision-specific evidence fields required for validation.
- Child-visible views MUST include only the current round and MUST explain empty current panels.
- Publish and respond prompts MUST be phase-specific.
- Host lifecycle state MUST be recordable without the runtime calling host primitives.
- Final reports MUST distinguish current unresolved disagreements from historical disagreements.
- Action schemas MUST define required fields per action type.
- Root/template mirrors MUST remain synchronized for Party Mode V2 runtime, specs, schemas, config, skills, commands, and adapter assets.

## Out Of Scope

- Party Mode V1 behavior.
- Formal `cowork-*` dispatch contract changes.
- Host primitive execution inside the runtime.
