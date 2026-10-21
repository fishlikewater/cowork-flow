# Cowork Flow Spec Index

This directory holds project specs, runtime contracts, and runtime configuration schemas. Layers by responsibility:

| Directory | Purpose |
| --- | --- |
| `contracts/` | Human-readable contracts for the workflow, host adapters, and subagent protocol. |
| `runtime/` | Machine configuration read by the runtime, including the contract registry and host asset manifest. |
| `schemas/` | JSON Schemas for runtime configuration and host contracts. |
| `backend/` | Backend implementation specs; the review skill reads them on demand and checks each clause. |
| `frontend/` | Frontend implementation specs; the review skill reads them on demand and checks each clause. |
| `guides/` | Pre-implementation thinking, cross-layer design, and reuse guidance for brainstorming/task-planning. |
| `references/` | On-demand reference material (DoD, testing checklist, security checklist, orchestration patterns); never auto-loaded. Load conditions are in the `references` array of contract-registry.json. |

Sync ownership: `contracts/`, `runtime/`, `schemas/`, and this file are framework-maintained and follow `cwf project sync`; `backend/`, `frontend/`, `guides/`, and `references/` are project-maintained, and `sync` never overwrites or deletes files there.

The workflow kernel only owns machine-checkable facts: task state, file scope, runtime context, and archive consistency.
Actions, stage guidance, and dedicated runtimes are declared by each Skill's `manifest.json`; there is no centralized Skill registry.
Natural-language specs under `backend/` and `frontend/` are not registered as runtime gates; the `task-review` skill reads them according to the current diff and task scope and checks each clause.
`guides/` is pre-implementation clarification and planning reference; selected conclusions belong in `decision-anchor.md` or the task plan.

## references/

> On-demand reference material. **Never auto-loaded in the main session** — read only when a skill entry or agent judges it necessary.

Reference files:
1. Provide supplemental context for skill entries (the main skill is the entry point; references supplement it).
2. Reduce what each session must load (narrow-domain specs such as `spec/backend/` are read only when needed).
3. Provide quick checklists during planning, check, or review.

Loading rules:
- Read when one of the `loadWhen` conditions in contract-registry matches.
- Read when a skill body explicitly references a reference ID.
- Read when the user requests a specific check in the main session.
- **Never auto-loaded** — that is the difference from `contracts/`.
