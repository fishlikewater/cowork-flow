# Workflow navigation readiness and project context

## Goal

Improve cowork-flow's requirement-entry experience after the new brainstorming gate:
when a user raises an unclear or L2-level requirement, the main session should know
what to ask, which artifact is missing, and what the next safe workflow action is.

## Background

The current project already has a brainstorming clarification gate in
`.cowork-flow/workflow.md` and the `start` / `brainstorming` skills. That solves
the first layer: ambiguous requirements should not jump straight into PRD,
planning, implementation, or fixed-agent dispatch.

The next weakness is operational. The user and agent still need to infer the next
command from scattered docs. L2 readiness is partly enforced by `change validate`,
but it is not surfaced as a clear pre-start gate. Project facts are scattered
across `AGENTS.md`, `.cowork-flow/workflow.md`, specs, README, package metadata,
and host adapter files, with no maintained project-context artifact.

## Scope

- Add a lightweight workflow navigator:
  - `flow help` or equivalent top-level help explains current workflow routes.
  - `task next` inspects active/planning/completed task state and prints the next
    safe action without mutating state.
- Add an L2 readiness gate:
  - L2 work must expose goal, non-goals, assumptions, scope boundary, acceptance
    criteria, proposal/spec/design status, plan link, task link, and verification.
  - Starting or dispatching L2 work should fail closed or clearly report blockers.
- Add generated/maintained `project-context.md`:
  - Summarize project identity, stack, commands, workflow surfaces, host adapters,
    specs, and important local constraints.
  - Preserve a manual notes section and regenerate only managed sections.
- Keep the design host-neutral in `.cowork-flow/workflow.md`; host-specific
  wiring stays under `.codex`, `.opencode`, `.claude`, and adapters.
- Mirror template assets when root workflow assets change.

## Non-goals

- Do not reintroduce `agent-team` or a second runtime coordinator.
- Do not add a heavy story hierarchy or mandatory BMAD role system.
- Do not make brainstorming implement code directly.
- Do not require environment variables for normal use.

## Key Assumptions

- Existing task/change/plan files remain the authoritative workflow state.
- Hooks can surface state, but hooks do not own readiness truth.
- L2 readiness only blocks work linked to an L2 change; L0/L1 work keeps the
  existing lightweight path.
- Template sync remains part of each workflow asset change.

## Recommended Direction

Use small local workflow utilities, not another orchestration layer:

1. Navigator: extend runner/task command surfaces so the agent can ask "what next?"
   and get deterministic instructions based on current task/change state.
2. Readiness: make L2 gates machine-checkable and visible before task start or
   fixed-agent dispatch.
3. Project context: generate a concise project-context artifact that subagents and
   main sessions can read before planning, reducing repeated broad scans.

## Rejected Alternatives

- Full BMAD role adoption: useful ideas, too heavy for this lightweight template.
- Hook-only solution: hooks can inject state, but they should not become the source
  of workflow truth.
- Prompt-only solution: easier to add, but it cannot reliably detect missing L2
  artifacts or stale project context.

## Benefits

- Fewer vague PRDs: unclear requirements are forced into an explicit clarification
  and readiness path.
- Less workflow drift: `task next` gives one deterministic next action instead of
  relying on memory.
- Safer L2 work: design/spec/plan gaps surface before implementation or dispatch.
- Faster onboarding: `project-context.md` gives agents a compact project map.
- Lower token waste: repeated broad reads are replaced by a maintained context
  artifact plus targeted follow-up reads.
- Better template quality: downstream projects receive the same guardrails.

## Acceptance Criteria

1. A navigator command exists and documents main routes for no-task, planning,
   in-progress, completed, delegated, and blocked/unknown states.
2. `task next` or equivalent emits a concrete next action and required command for
   the current task state without mutating task state.
3. L2 readiness has a machine-checkable contract and fails closed before task start
   or formal fixed-agent dispatch when required artifacts are missing.
4. `project-context.md` can be generated and refreshed idempotently while preserving
   manual notes.
5. Root and template assets remain synchronized for workflow scripts, docs, and
   tests.
6. Tests cover navigator output, L2 readiness blockers, project-context generation,
   template sync, and existing hook/subagent safety behavior.

## Verification

- `python -m unittest discover -s tests -p "test_python_runner.py"`
- `python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py"`
- `python -m unittest discover -s tests -p "test_flow_script_paths.py"`
- `python -m unittest discover -s tests -p "test_no_legacy_template_paths.py"`
- `git diff --check`
