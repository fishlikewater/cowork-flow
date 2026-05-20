---
name: start
description: Use when beginning a development session in a project that uses the cowork-flow template
---

# Start Session

Initialize your AI development session and begin working on tasks.

<HARD-GATE>
Any request that changes repository files MUST go through this skill's task workflow.
Questions may be answered directly, but file edits are at least `L0` and require a task,
PRD, context initialization, task activation, verification, and session recording.
Do not use a direct-edit shortcut unless the user explicitly tells you not to use
cowork-flow for this task.
</HARD-GATE>

---

## Operation Types

| Marker | Meaning | Executor |
|--------|---------|----------|
| `[AI]` | Bash scripts or tool calls executed by AI | You (AI) |
| `[USER]` | Skills executed by user | User |

---

## Initialization `[AI]`

### Step 1: Understand Development Workflow

First, read the workflow guide and the project-level collaboration rules:

```bash
cat .cowork-flow/workflow.md
cat AGENTS.md
```

**Follow the instructions in `workflow.md` and `AGENTS.md`** - they contain:
- Core principles (Read Before Write, Follow Standards, etc.)
- File system structure
- Development process
- Best practices
- Project-specific collaboration and documentation rules

Command examples use macOS / Linux / Git Bash / WSL syntax. In native Windows
cmd or PowerShell, replace `./.cowork-flow/run <command>` with
`.\.cowork-flow\run.cmd <command>`.

> **Important**:
> Reusable skills are already part of the template. During project onboarding, put project-specific facts in `AGENTS.md`, `.cowork-flow/workflow.md`, `.cowork-flow/config.yaml`, and `.cowork-flow/spec/` rather than editing `SKILL.md`.

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

## Task Classification

When user describes a task, classify it:

| Type | Criteria | Workflow |
|------|----------|----------|
| **Question** | User asks about code, architecture, or how something works, and no repository files need to change | Answer directly after session context is loaded |
| **L0 Change** | Docs, tests, comments, config, small refactors, or any file change without external behavior change | Task Workflow, no Behavior Change Gate |
| **L1 Change** | Bounded behavior change in one module or one interface | Behavior Change Gate → Task Workflow |
| **L2 Change** | Cross-layer, architectural, migration, permission, compatibility, release, or security-impacting change | Behavior Change Gate + `design.md` → Task Workflow |
| **Unclear / Complex** | Vague goal, multiple possible interpretations, or architectural decisions | **Brainstorm → classify L0/L1/L2 → gated workflow** |

### Decision Rule

> **Any file change must enter L0 / L1 / L2 workflow.**
>
> A typo, comment, one-line fix, or "quick" change is still a repository change.
> Do not treat small size as permission to skip PRD, context, verification, or session recording.
>
> **If in doubt, use Brainstorm + Task Workflow.**
>
> Task Workflow ensures code-specs are injected to the right context, resulting in higher quality code.
> The overhead is minimal, but the benefit is significant.

> **Subtask Decomposition**: If brainstorm reveals multiple independent work items,
> consider creating subtasks using `--parent` flag or `add-subtask` command.
> See the brainstorm skill's Step 8 for details.

### Behavior Change Gate

Before entering Task Workflow, classify the change as `L0` / `L1` / `L2` using `.cowork-flow/workflow.md`.

- `L0`: No external behavior change. Continue with the existing Task Workflow.
- `L1`: Behavior change in a bounded module. Do **not** go straight to PRD/Research. First run:
  1. `./.cowork-flow/run change create <slug>`
  2. `superpowers:brainstorming` to create or complete `proposal/spec`
  3. `./.cowork-flow/run change validate <slug>`
  4. `superpowers:writing-plans` to produce the implementation plan
- `L2`: Same as `L1`, plus required `design.md`. Multi-perspective review happens after implementation in the review gate.

Only return to the task workflow after the spec and plan gates are complete.

Before Phase 2, always complete this task handoff:

1. Create or update `.cowork-flow/plans/YYYY-MM-DD-<slug>.md` with the execution checklist
2. Create or bind a task directory
3. Ensure `prd.md` summarizes the approved `proposal/spec/design/plan`
4. Add the approved change artifacts and plan into task context
5. Treat the plan file as a living execution artifact: keep checkbox state and current execution status synced during implementation, not only at the end

- If the task came from **Simple Task**, resume with **Path B Step 2 (Create Task Directory)** and **Step 3 (Write PRD)**, then do the task handoff above and continue to Phase 2.
- If the task came from **Brainstorm**, reuse the brainstorm-created task directory and PRD, then do the same task handoff and continue with **Path A / Phase 2**.

---

## Question Only

For questions that do not modify repository files, work directly:

1. Answer the question.
2. If the answer reveals that files should change, stop and re-enter Task Classification.
3. Do not modify files from this section.

---

## L0 / Simple Task

For simple, well-defined tasks that modify files without external behavior change:

1. Clarify only if the goal, scope, or verification method is unclear.
2. Determine whether the task is `L0`, `L1`, or `L2`.
3. **If it is `L1/L2`, complete the Behavior Change Gate first. After that, execute Path B Step 2 and Step 3, complete the task handoff, then continue with Phase 2.**
4. **If it is `L0`, execute ALL steps below without stopping. Do NOT ask for additional confirmation between steps. Do NOT switch to ad hoc direct editing.**
   - Create task directory (Phase 1 Path B, Step 2)
   - Write PRD (Step 3)
   - Research codebase (Phase 2, Step 5)
   - Configure context (Step 6)
   - Activate task (Step 7)
   - Implement (Phase 3, Step 8)
   - Check quality (Step 9)
   - Complete (Step 10)

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

**Step 1: Confirm Understanding** `[AI]`

Quick confirm:
- What is the goal?
- What type of development? (frontend / backend / fullstack)
- Any specific requirements or constraints?

If unclear, ask clarifying questions.

**Step 2: Create Task Directory** `[AI]`

```bash
TASK_DIR=$(./.cowork-flow/run task create "<title>" --slug <name>)
```

**Step 3: Write PRD** `[AI]`

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

**Step 4: Code-Spec Depth Check** `[AI]`

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

**Step 5: Research the Codebase** `[AI]`

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

**Step 6: Configure Context** `[AI]`

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

**Step 7: Activate Task** `[AI]`

```bash
./.cowork-flow/run task start "$TASK_DIR"
```

This sets `.current-task` so hooks can inject context.

---

### Phase 3: Execute (shared)

**Step 8: Implement** `[AI]`

Implement the task described in `prd.md`.

- Follow all specs injected into implement context
- Keep changes scoped to requirements
- Run the project verification commands from `AGENTS.md` or `.cowork-flow/config.yaml` before finishing
- If executing an approved plan with independent work, use `agent-team-execution`: run `agent-team prepare`, review the dispatch plan, use `agent-team next` for ready assignments, and finish with `agent-team complete`.

**Step 9: Check Quality** `[AI]`

Run a quality pass against check context:

- Review all code changes against the specs
- Fix issues directly
- Ensure lint and typecheck pass

**Step 10: Complete** `[AI]`

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

### Workflow Phases `[AI]`

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
