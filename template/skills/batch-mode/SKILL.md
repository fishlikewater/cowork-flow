---
name: batch-mode
description: Use when user approves a full plan and wants autonomous execution through all tasks without manual stepping. Each task still passes all gates independently.
---

# Batch Mode

## Current Status: Disabled

The public Batch entry is fail-closed until the task-graph scheduler is complete.
`task start --auto` returns `BATCH-SCHEDULER-NOT-IMPLEMENTED` and does not change
task status, active sessions, commits, or the working tree.

Do not simulate Batch execution from `implement.jsonl`. Continue tasks manually
through start, implement, review, check, complete, and commit.

## Overview

User approves the plan once (`implement.jsonl`), then the agent autonomously completes all tasks. **This does not bypass verification gates** -- each task still:
- Passes the TDD evidence gate
- Passes the check phase gates
- Gets an independent commit
- Pauses back to the user on failure or high-risk steps

Only the **manual progression between tasks** is removed.

## When to Use

- Plan is approved (`implement.jsonl` is complete and the user said "approved" + "auto" at the end of writing-plans)
- Current before-dev status is in_progress or review
- Tasks are low-coupling (different files/modules, no write conflicts)
- L0/L1 tasks dominate (L2 tasks recommended for step-by-step confirmation)

**Not applicable when**:
- Tasks are L2 (step-by-task review recommended)
- Tasks have dependencies or write conflicts
- This is a first-time exploratory implementation (implementation path is uncertain)
- The user has not explicitly requested batch mode

## Startup Conditions

```
User: "approved" + "auto"
  -> agent checks:
     1. before-dev status = in_progress / review
     2. implement.jsonl exists, non-empty, every line is valid JSON
     3. user explicitly approved
```

## Batch Loop

```
for task in implement.jsonl:
  1. task start <task>  (full readiness gate, includes L2 doubt-review)
  2. dispatch cowork-implement
  3. dispatch cowork-check
  4. if check passes: git commit + task review + task complete
  5. if check fails: cowork-implement fix (up to 3 retries)
  6. on triggering any of 5 safety valves -> pause and report
```

## 5 Safety Valves (Pause Conditions)

Any single condition below triggers a **pause**; do not proceed to the next task:

1. **TDD gate failure**: any task's tdd.jsonl evidence is invalid or missing
2. **Check gate failure**: any task's check.jsonl has an unresolved blocker (after 3 retries)
3. **Test/build breakage**: `git diff` introduces conflicts inconsistent with R-AG-005
4. **3 retries still failing**: the same task's implement + check loop has not passed after 3 rounds
5. **L2 doubt-review blocker**: an L2 decision has substantive unresolved doubt findings not reconciled

When paused, output:

```
## Batch Mode Paused

Task: <task-name>
Reason: <specific cause>
Current state: <task status + last command output>

Options:
1. Skip this task -> mark as skipped, proceed to next
2. Manual takeover -> exit batch, user resumes manually
3. Abort -> exit batch, all already-committed tasks remain intact
```

## Post-Batch Verification

After all tasks complete (or after skips/aborts), run once:

1. **Full test suite**: `python -m pytest` / `npm test` / project-defined verification command
2. **git log audit**: confirm each task has an independent commit with a message reflecting the task
3. **Spec sync check**: confirm no remaining spec synchronization needs
4. **Final report**:

```
## Batch Mode Report

- Tasks completed: N
- Tasks skipped: M (reasons: ...)
- Total commits: K
- Issues found: ...

### Per-Task Summary

| task | commits | duration | issues |
|------|---------|----------|--------|
| ...  | ...     | ...      | ...    |
```

## Relationship With Existing Systems

- writing-plans -> generates implement.jsonl (input)
- task start -> unchanged (each task has its own readiness gate)
- cowork-implement -> unchanged (dispatch one task per call)
- cowork-check -> unchanged (check one task per call)
- doubt-review -> auto-triggered for L2 tasks
- Party Mode -> does not participate in batch mode (advisory in nature)

## Relationship With Before-Dev Gate

Batch mode can only start when before-dev status is in_progress.
Before entering batch mode, the main session confirms:
- before-dev status = in_progress / review
- implement.jsonl exists and is non-empty
- the user explicitly said "approved" at the end of writing-plans
