---
name: cowork-flow-maintenance
description: Use when modifying cowork-flow itself .cowork-flow runtime, template files, .codex hooks/agents, .agents skills, workflow docs, or generated project structure.
---

# Cowork Flow Maintenance

Use this for changes to the cowork-flow operating model.

## Scope

Meta changes often touch both:

- Root project files used by this repository.
- `template/` files installed into downstream projects.

Keep those copies aligned unless there is a documented reason not to.

## Rules

- Prefer the current fixed-agent model: main session coordinates through the active Host Adapter, child agents execute bounded tasks with fresh context.
- Do not add compatibility fallback paths for removed workflow models unless the user explicitly asks.
- Delete stale skills, prompts, tests, and docs when their behavior is no longer valid.
- Update tests that guard template contents, packaging, hooks, and task context generation.
- Keep reusable skills generic; put project-specific lessons in `.cowork-flow/spec/`, `AGENTS.md`, or a project-owned Skill. Do not restore a second process-authority document.
- Check Windows command paths and UTF-8 behavior when editing runtime scripts.

## Verification

Run focused tests for the changed subsystem, then `npm run test:all` when template/runtime behavior changed.
