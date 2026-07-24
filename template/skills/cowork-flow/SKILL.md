---
name: cowork-flow
description: Route cowork-flow work through one authoritative workflow entry. Use for starting, resuming, implementing, reviewing, debugging, discussing, or finishing repository work when workflow state and the next allowed operation must be resolved.
---

# Cowork Flow

Use this Skill as the only public workflow router. Do not reproduce lifecycle
rules from other Skills.

## Resolve State

1. Use the injected `<workflow-state>` when present.
2. If state is absent, run `./.cowork-flow/run task next --json` exactly once.
3. Treat `status`, `allowedOperations`, `requiredArtifacts`,
   `recommendedSkill`, `internalProtocols`, and `blockers` as authoritative.
4. Stop repository mutations when blockers exclude the requested operation.

## Classify Intent

Classify the request into exactly one intent:

- `question`: answer or explain without changing repository state.
- `clarify`: refine goals, boundaries, or acceptance criteria.
- `plan`: create or revise an executable plan.
- `implement`: change code or task artifacts.
- `review`: verify implementation or complete review gates.
- `doubt_review`: run standalone advisory doubt review without lifecycle check dispatch.
- `debug`: diagnose a failure or repeated unsuccessful attempt.
- `discuss`: compare options without advancing task state.
- `batch`: request automated execution of a task graph.

For `question`, answer directly when `answer_questions` is allowed. Do not load
implementation or review protocols.

## Route

Use the active public Registry entry whose status and intent match the request.
Select at most one public Skill. If there is no match, follow the allowed
operation directly or report the blocker; never guess a second workflow entry.

Load only the protocols listed in `internalProtocols`. These protocols refine
execution but are not public alternatives and cannot override Runtime Gates.
