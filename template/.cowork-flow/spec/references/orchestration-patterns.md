# Orchestration Patterns

> Declarative catalog of the collaboration patterns already implemented.
> This file is a human-readable summary of the `spec/contracts/` series — the contracts are authoritative.

## Core principle

**The main session is the only coordinator. Fixed subagents are leaf executors. The user is the final decision-maker.**

---

## Pattern 1: Leaf executors (implemented)

```
main session -> cowork-implement (implement) -> return -> main session verifies
main session -> cowork-check (verify)        -> return -> main session confirms
main session -> cowork-research (research)   -> return -> main session synthesizes
```

**When to use**: the plan declares parallel low-conflict slices (clean file ownership, independent verification); research that needs context isolation (cowork-research); the independent review required before completion (cowork-check).

**Constraints**:
- R-AG-001: subagents must not dispatch other subagents
- R-AG-002: subagents must not modify spec files
- R-AG-003: subagents must not operate Git
- R-AG-004: subagents must not commit/archive

**Verification**: create the runtime context with `subagent init --role` before dispatch; the child's first action must be `subagent bind`; the parent checks `status: bound`.

---

## Pattern 2: Parallel fan-out + merge (implemented, main-session managed)

```
main session ─┬─> cowork-implement (task-slice-a) ─┐
              ├─> cowork-implement (task-slice-b) ─┤─> all return ─> integrated verification ─> main session synthesizes
              └─> cowork-research (background)    ─┘
```

**When to use**: multiple low-coupling implementation slices can run in parallel.

**Verification checklist**:
1. No write conflicts between subtasks (different files or isolated through git worktree)
2. Each subagent produces a different type of finding
3. The merge step fits within the main agent's context window
4. The user's wait is long enough for parallel wall-clock gains to matter
5. Converge on a single cowork-check review and a single commit (the receipt fingerprint covers the merged change set)
6. Two tasks cannot run in parallel in one worktree (the file-scope gate reads the whole working tree); cross-task parallelism uses separate worktrees/clones and coordinates through board dependency edges

If any answer is no, fall back to Pattern 1 sequential execution.

---

## Pattern 3: Sequential skill chain (implemented, user-driven)

```
User runs: task next --run --title ... -> brainstorming -> task-planning -> task next <dir> --run -> implement -> check -> task next <dir> --run --intent review
```

**When to use**: stages depend on each other, and user judgment between stages is valuable.

**Why there is no lifecycle-orchestration agent**:
- An orchestration agent summarizes between hand-offs, losing nuance
- User checkpoints between stages catch wrong directions early
- The cost of a human check is lower than the rework cost of going the wrong way

---

## Pattern 4: Party Mode V2 Board (implemented, advisory)

```
main session ─> start Discussion (party-v2 runtime board)
              ─> subagents communicate through the board (never directly)
              ─> moderator monitors drift and does not decide
              ─> produces advice and does not change task state
```

**Constraints**:
- The board cannot advance task state
- It cannot replace the Implement/Check formal gates
- The moderator must not relay, summarize, or synthesize subagent opinions

---

## Anti-pattern A: Router persona (forbidden)

```
/workflow -> agent persona ("what role do you need?") -> sub-persona -> agent persona (restates) -> user
```

**Why not**: a pure routing layer has no domain value; double restatement loses information and costs ~2x tokens; the `<workflow-state>` routing in AGENTS.md already covers this

**Alternative**: route directly with the `<workflow-state>` block; do not use personas.

---

## Anti-pattern B: Persona calling persona (forbidden)

```
cowork-check("sees security-related code") -> cowork-security-audit
```

**Why not**: personas are designed to produce a single perspective; chaining breaks that design; summaries passed between personas lose context; failure modes multiply

**Alternative**: the current persona recommends a follow-up audit in its report; the user or main session runs the second round.

---

## Anti-pattern C: Deep nesting (forbidden)

```
/ship -> quality-coordinator -> code-reviewer -> security-auditor
```

**Why not**: each layer adds latency and tokens without decision value; deep persona context degrades after repeated summarization

**Alternative**: cowork-flow's current depth = 1 (main session -> leaf subagent). Do not introduce intermediate layers.

---

## Decision flow

```
Is the task one perspective on one artifact?
├── Yes -> call it directly. Stop.
└── No  -> can the tasks run in parallel?
          ├── No  -> sequential skill chain (user-driven)
          └── Yes -> parallel fan-out (main-session coordinated)
                     Verification checklist:
                     - subtasks have no write conflicts
                     - each persona produces a different type
                     - the merge step fits in the main context
                     Any failure -> fall back to sequential
```

## See also

- `spec/contracts/subagent-dispatch.md` — authoritative formal dispatch protocol
- `spec/contracts/party-mode-v2-board.md` — authoritative Party Mode V2 definition
- `spec/backend/`, `spec/frontend/`, `spec/guides/` — user-defined specs, read clause by clause by the review skill
- `skills/cowork-flow/SKILL.md` — workflow state routing
