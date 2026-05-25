---
name: start
description: Use when beginning a development session in a project that uses the cowork-flow template
---

# Start Session

Initialize your AI development session and begin working on tasks.

Any request that changes repository files MUST go through this skill's task workflow.
Questions may be answered directly, but file edits are at least `L0` and require a task,
PRD, context initialization, task activation, verification, and session recording.
Do not use a direct-edit shortcut unless the user explicitly tells you not to use
cowork-flow for this task.

---

## Initialization

### Step 1: Understand Development Workflow

First, read the workflow guide and the project-level collaboration rules:

```bash
cat .cowork-flow/workflow.md
cat AGENTS.md
```

**Follow the instructions in `workflow.md`** - they contain:
- Core principles (Read Before Write, Follow Standards, etc.)
- File system structure
- Development process
- Best practices
- Project-specific collaboration and documentation rules

Command examples use macOS / Linux / Git Bash / WSL syntax. In native Windows
cmd or PowerShell, replace `./.cowork-flow/run <command>` with
`.\.cowork-flow\run.cmd <command>`.

### Step 2: Get Current Context

```bash
./.cowork-flow/run resume
```

This shows: developer identity, git status, current task (if any), active tasks, and
the minimal `RESUME CHECKLIST` for loading task details on demand.

### Step 3: Read Guidelines Index

```bash
for f in .cowork-flow/spec/frontend/index.md .cowork-flow/spec/backend/index.md .cowork-flow/spec/guides/index.md; do
  [ -f "$f" ] && cat "$f"
done
```

> **Important**: The index files are navigation — they list the actual guideline files (e.g., `error-handling.md`, `conventions.md`, `mock-strategies.md`).
> At this step, just read the indexes to understand what's available.
> When you start actual development, you MUST go back and read the specific guideline files relevant to your task, as listed in the index's Pre-Development Checklist.

### Step 4: Report and Ask

Report what you learned and ask: "What would you like to work on?"

---

## Complex Task - Brainstorm First

For complex or vague tasks, **automatically start the brainstorm process** — do NOT skip directly to implementation.

See `$brainstorm` for the full process. Summary:

1. **Acknowledge and classify** - State your understanding
2. **Create task directory** - Track evolving requirements in `prd.md`
3. **Ask questions one at a time** - Update PRD after each answer
4. **Propose approaches** - For architectural decisions
5. **Confirm final requirements** - Get explicit approval
6. **If behavior changes are involved, complete the Behavior Change Gate**
7. **Proceed to Task Workflow** - Reuse the brainstorm-created task directory/PRD, complete the task handoff, then continue from Phase 2 with clear requirements and plan

---

## Task Workflow (Development Tasks)

**Why this workflow?**
- Run a dedicated research pass before coding
- Configure specs in jsonl context files
- Implement using injected context
- Verify with a separate check pass
- Result: Code that follows project conventions automatically

### Overview: Two Entry Points

```
From Brainstorm (Complex Task):
  PRD confirmed → Research → Configure Context → Activate → Implement → Check → Complete

From Simple Task:
  Confirm → Create Task → Write PRD → Research → Configure Context → Activate → Implement → Check → Complete
```

**Key principle: Research happens AFTER requirements are clear (PRD exists).**

---

### Phase 1: Establish Requirements

#### Path A: From Brainstorm (skip to Phase 2)

PRD and task directory already exist from brainstorm. Skip directly to Phase 2.

#### Path B: From Simple Task

**Step 1: Confirm Understanding**

Quick confirm:
- What is the goal?
- What type of development? (frontend / backend / fullstack)
- Any specific requirements or constraints?

If unclear, ask clarifying questions.

**Step 2: Create Task Directory**

```bash
TASK_DIR=$(./.cowork-flow/run task create "<title>" --slug <name>)
```

**Step 3: Write PRD**

Create `prd.md` in the task directory with:

```markdown
# <Task Title>

## Goal
<What we're trying to achieve>

## Requirements
- <Requirement 1>
- <Requirement 2>

## Acceptance Criteria
- [ ] <Criterion 1>
- [ ] <Criterion 2>

## Technical Notes
<Any technical decisions or constraints>
```

---

### Phase 2: Prepare for Implementation (shared)

> Both paths converge here. PRD and task directory must exist before proceeding.

**Step 4: Code-Spec Depth Check**

If the task touches infra or cross-layer contracts, do not start implementation until code-spec depth is defined.

Trigger this requirement when the change includes any of:
- New or changed command/API signatures
- Database schema or migration changes
- Infra integrations (storage, queue, cache, secrets, env contracts)
- Cross-layer payload transformations

Must-have before proceeding:
- [ ] Target code-spec files to update are identified
- [ ] Concrete contract is defined (signature, fields, env keys)
- [ ] Validation and error matrix is defined
- [ ] At least one Good/Base/Bad case is defined

**Step 5: Research the Codebase**

Based on the confirmed PRD, run a focused research pass and produce:

1. Relevant spec files in `.cowork-flow/spec/`
2. Existing code patterns to follow (2-3 examples)
3. Files that will likely need modification

Use this output format:

```markdown
## Relevant Specs
- <path>: <why it's relevant>

## Code Patterns Found
- <pattern>: <example file path>

## Files to Modify
- <path>: <what change>
```

**Step 6: Configure Context**

Initialize default context:

```bash
./.cowork-flow/run task init-context "$TASK_DIR" <type>
# type: backend | frontend | fullstack
```

Add specs found in your research pass:

```bash
# For each relevant spec and code pattern:
./.cowork-flow/run task add-context "$TASK_DIR" implement "<path>" "<reason>"
./.cowork-flow/run task add-context "$TASK_DIR" check "<path>" "<reason>"
```

If this task came through the Behavior Change Gate, add the approved artifacts before coding:

```bash
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/changes/<slug>/proposal.md" "Approved change proposal"
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/changes/<slug>/spec.md" "Approved behavior spec"
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/changes/<slug>/design.md" "Approved design for L2 changes"
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/plans/YYYY-MM-DD-<slug>.md" "Approved implementation plan"
./.cowork-flow/run task add-context "$TASK_DIR" check ".cowork-flow/changes/<slug>/spec.md" "Check implementation against approved spec"
./.cowork-flow/run task add-context "$TASK_DIR" check ".cowork-flow/plans/YYYY-MM-DD-<slug>.md" "Check implementation against approved plan"
```

**Step 7: Activate Task**

```bash
./.cowork-flow/run task start "$TASK_DIR"
```

This sets `.current-task` so hooks can inject context.

---

### Phase 3: Execute (shared)

**Step 8: Implement**

Implement the task described in `prd.md`.

- Follow all specs injected into implement context
- Keep changes scoped to requirements
- Run the project verification commands from `AGENTS.md` or `.cowork-flow/config.yaml` before finishing
- If executing an approved plan with independent work, use `agent-team-execution`: run `agent-team prepare`, review the dispatch plan, use `agent-team next` for ready assignments, and finish with `agent-team complete`.

**Step 9: Check Quality**

Run a quality pass against check context:

- Review all code changes against the specs
- Fix issues directly
- Ensure lint and typecheck pass

**Step 10: Complete**

1. Verify lint and typecheck pass
2. Report what was implemented
3. Follow the current session convention for completion:
   - Test the changes
   - Have the agreed executor handle business-code changes according to project policy
   - Run `$record-session` to record this session

---

## Continuing Existing Task

If `resume.py` shows a current task:

1. Read the task's `prd.md` to understand the goal
2. Check `task.json` for current status
3. Ask user: "Continue working on <task-name>?"

If yes, resume from the appropriate step (usually Step 7 or 8).

---

## Resume / Context Compression

When a conversation has many rounds, a task runs for a long time, or context was
compressed, resume with the smallest useful context:

1. Run `./.cowork-flow/run resume`.
2. Follow the `RESUME CHECKLIST` section.
3. Read the current task `prd.md`.
4. Run `./.cowork-flow/run task list-context <task-dir>` and read only the jsonl references needed for the current phase.
5. If a plan is listed, read its current execution status before continuing implementation.

Do not bulk-read `.cowork-flow/spec/`, all plans, all tasks, or workspace journals
just because context was compressed. Use the checklist as the minimal recovery
anchor, then load details on demand.

---

## Skills Reference

### User Skills `[USER]`

| Skill | When to Use |
|---------|-------------|
| `$start` | Begin a session (this skill) |
| `$finish-work` | Final verification before handoff or commit |
| `$record-session` | After task completion and project commit/handoff policy is satisfied |

### AI Scripts `[AI]`

| Script | Purpose |
|--------|---------|
| `./.cowork-flow/run resume` | Resume session with minimal context checklist |
| `./.cowork-flow/run get-context` | Get session context |
| `./.cowork-flow/run task create` | Create task directory |
| `./.cowork-flow/run task init-context` | Initialize jsonl files |
| `./.cowork-flow/run task add-context` | Add spec to jsonl |
| `./.cowork-flow/run task start` | Set current task |
| `./.cowork-flow/run task finish` | Clear current task |
| `./.cowork-flow/run task archive` | Archive completed task |

### Workflow Phases

| Phase | Purpose | Context Source |
|-------|---------|----------------|
| research | Analyze codebase | direct repo inspection |
| implement | Write code | `implement.jsonl` |
| check | Review & fix | `check.jsonl` |
| debug | Fix specific issues | `debug.jsonl` |

---

## Key Principle

> **Code-spec context is injected, not remembered.**
>
> The Task Workflow ensures agents receive relevant code-spec context automatically.
> This is more reliable than hoping the AI "remembers" conventions.
