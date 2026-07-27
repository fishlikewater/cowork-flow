---
name: agent-dispatch
description: Use inside cowork-flow fixed subagents when handling runtime-context-bound implement, check, or research work. Defines context binding, leaf-agent restrictions, and role output boundaries without owning workflow lifecycle or gates.
---

# Agent Dispatch

Use this Skill only inside fixed subagents such as `cowork-implement`,
`cowork-check`, and `cowork-research`.

## Binding

1. Require `cowork_runtime_context_id` and `cowork_host_context_key` from the
   prompt, host metadata, or environment.
2. Run `.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>`
   before doing task work. On Windows, use `.\.cowork-flow\run.cmd`.
3. If binding fails, or the bound context is missing, closed, invalid, or names
   another agent type, report `needs_context` and stop.
4. Read the task directory from the bound runtime context; do not infer it from
   prompt text.

## Boundaries

- Act as a leaf executor: do not spawn, wait for, list, or close other agents.
- Do not start, finish, archive, resume, commit, or push workflow state.
- Keep edits and reads inside the assigned runtime context and task scope.
- Treat runtime gates as CLI adapters backed by kernel services; this Skill may
  explain when to run or report them, but does not enforce them.

## Role Outputs

- `cowork-implement`: report changed files, acceptance IDs, verification
  commands, and spec updates or why none were needed.
- `cowork-check`: report findings, resolutions, test intent review, machine
  gate review, and Definition of Done coverage.
- `cowork-research`: report sourced findings, uncertainty, and recommended next
  action without mutating task lifecycle state.
