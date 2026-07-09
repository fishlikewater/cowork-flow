---
name: before-dev
description: MANDATORY GATE — call before ANY code change, file edit, or subagent dispatch. Checks workflow state and either allows or blocks the action.
---

# Before Dev — Pre-Development Workflow Gate

MUST invoke before any file edit, code change, or subagent dispatch. Reads the current `<workflow-state>` block and decides: allow or block.

This skill is NOT a checklist or context loader — it is a gate. Do not proceed to code changes without passing through this gate.

**Exemptions**: read-only Q&A, pure query commands (`git status`, `task next`, `task current`), user explicitly says "just make the change, skip the workflow".

---

## Step 1: Read Workflow State

Read the `<workflow-state>` block (Status, Source). If absent, check for `cowork_runtime_context_id` in the user prompt:
- **Has it** → subagent without injected state. Skip directly to the `delegated_subtask` branch below.
- **No `cowork_runtime_context_id`** → no context identity. Fail-closed: block and direct the user to `task start` or `continue`.

## Step 2: Act by Status

| Status | Action |
|--------|--------|
| `no_task` | BLOCK. Direct to `brainstorming` / `writing-plans` / `continue`. Allow read-only Q&A. |
| `delegated_subtask` | Execute. `subagent bind <id> <key>`, load task dir, complete leaf work. No start/resume/commit. |
| `planning` | BLOCK implementation. Allow planning files only (`decision-anchor.md`, `*.jsonl`). |
| `in_progress` | ALLOW. Load context (below). L2 tasks require `doubt-review` before implementing. |
| `review` | Verify with `cowork-check`. Minor fixes only — no new implementation. |
| `completed` | BLOCK. Create a new task via `task archive` → `task create`. |
| `stale` / `unknown` | BLOCK. Run `resume` to restore state first. |

### Context loading for `in_progress`

1. Read `<task>/decision-anchor.md` (goals, scope, acceptance criteria).
2. Read `<task>/implement.jsonl` + plan steps (from `<task>/task.json` relatedFiles or `.cowork-flow/plans/`).
3. Confirm success criteria, files involved, and verification commands. Begin implementation.

---

**Fail-closed fallback**: if `<workflow-state>` is absent AND no `cowork_runtime_context_id` is present, block all changes and direct to `task start` or `continue`. This indicates the hook is not injecting state.
