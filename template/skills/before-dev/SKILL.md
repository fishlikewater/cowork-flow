---
name: before-dev
description: MANDATORY GATE — call before ANY code change, file edit, or subagent dispatch. Checks workflow state and either allows or blocks the action.
---

# Before Dev — Pre-Development Workflow Gate

This skill is the enforcement point for the cowork-flow workflow. You MUST invoke it
before any file edit, code change, or subagent dispatch. It reads the current
`<workflow-state>` block and decides whether to allow or block.

This skill is NOT a checklist or context loader — it is a gate. Do not proceed to
code changes without passing through this gate.

**Exemptions**: read-only Q&A, pure query commands (`git status`, `task next`, `task current`),
user explicitly says "just make the change, skip the workflow".

---

## Step 1: Read Current Workflow State

Read the `<workflow-state>` block from context. Pay attention to the `Status` and `Source` fields.

If there is **no** `<workflow-state>` block in context, the current platform's hook/plugin has not injected state into this context.
In that case, check whether the user prompt contains `cowork_runtime_context_id`:

- **Has `cowork_runtime_context_id`** → you are a subagent receiving runtime context via prompt transport, but the platform hook did not inject workflow-state. Skip directly to the `delegated_subtask` branch below — execute bind, load the task, and complete the leaf work.
- **No `cowork_runtime_context_id`** → unable to determine the current context identity.

Reply:
```
Cannot determine workflow state from context (no <workflow-state> block, no runtime context ID).
Please run resume to restore task state, or run task start to create a new task.
```

This is a fail-closed fallback — only triggers when the Codex/OpenCode hook is not functioning normally.

## Step 2: Act by Status

### Status = `no_task`

**⛔ BLOCK.** No active task exists.

You **must refuse** to perform any code changes, file edits, or subagent dispatches. Reply to the user:

```
No active task exists. Implementation, refactoring, or behavior changes require creating a task first.

Suggestions:
1. New requirement direction unclear → brainstorm first to clarify direction
2. Requirements already clear → writing-plans → task create → task start
3. Resume an existing task → continue

Which direction would you like to go?
```

Read-only Q&A may be answered directly, but do not modify any files.

### Status = `delegated_subtask`

You are a subagent. Execute according to the bound runtime context:
- Run `./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>` to bind
- Load task directory and assigned content
- Do not execute start/resume/task start/task archive/commit/spawn
- Complete the assigned leaf work

### Status = `planning`

**⛔ BLOCK implementation.** The task is in the planning phase and not yet ready.

Reply to the user:

```
The task is still in the planning phase and not yet ready for implementation.

Need to:
1. Finalize decision-anchor.md (goals, scope, acceptance criteria)
2. Organize implement.jsonl and check.jsonl
3. Run task next to confirm readiness
4. Run task start to enter the implementation phase

Continue planning work now?
```

**Exception**: if the user explicitly requests "planning work" (writing decision-anchor.md, organizing jsonl files), you may proceed, but only edit task planning files — do not start implementing code.

### Status = `in_progress`

**✅ ALLOW.** Task is in progress.

Load task context and continue:
1. Read `<task>/decision-anchor.md`
2. Read task-associated plan files (found via `<task>/task.json` relatedFiles, or search `.cowork-flow/plans/` for files referencing this task), execute according to plan steps
3. Read `<task>/implement.jsonl`
4. Read relevant spec files
5. Behavior-change tasks: confirm `<task>/tdd.jsonl` red evidence exists
6. State confirmed hypotheses, success criteria, files involved, and verification commands
7. Continue implementation

**L2 tasks must complete doubt-review before entering implementation:**
- Decisions recorded in `<task>/doubt-review.md`
- Each decision has CLAIM + ARTIFACT + CONTRACT + RECONCILE records
- Non-trivial decisions without records are treated as "unreviewed" — the check stage should flag them as blockers
- See skills/doubt-review/SKILL.md for the 5-step cycle

When the main session dispatches a fixed agent, you must use the runtime context dispatch protocol.

### Status = `review`

**⚠️ Task is in the review phase.** Implementation should be complete.

Reply to the user:

```
The task is in the review phase; implementation should be complete.

Suggestions:
1. Run cowork-check to verify
2. After check passes, run task complete
3. If minor fixes are needed, fix directly within the review scope

Run checks or make fixes now?
```

Do not start new implementation work unless it is a minor fix.

### Status = `completed`

**⛔ BLOCK.** Task is complete.

Reply to the user:

```
Task is complete. Do not dispatch new implementation work against a completed task.

If something was missed:
1. task archive to archive the old task
2. Create a new task
3. Go through the full workflow

Create a new task?
```

### Status = `stale` or `unknown`

Task state is abnormal. Reply to the user:

```
Task state is abnormal (<status>). Please run task next and resume to confirm current state before proceeding.
```
