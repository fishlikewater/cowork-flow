# Task Adopt Contract

**Adoption is the explicit ownership-repair action: take over a task that another
executor holds and that is already active and unfinished — rebind the executor,
reset the review baseline to the current HEAD, keep the status, and leave audit
fields behind.**

Adoption is not a lifecycle transition: it does not advance status, it exempts no
check, and it does not chain with other actions in one invocation. It is the
prerequisite for the 1.9.0 multi-executor collaboration story (multi-executor
lifecycle ownership), and it carries the operation that had to hand-edit task.json
meta when two stale tasks were archived on 2026-10-06.

## Entry point and action boundary

```bash
./.cowork-flow/run task next <task-dir> --run --adopt
```

- `--adopt` is intercepted by the `task next --run` delivery layer
  (`task_next_runner`) before action resolution and runs the adoption action
  directly; it neither enters the navigation default action sequence nor chains
  with a review/complete/archive transition (the next step is an explicit user
  action).
- Without `--run`, `--adopt` behaves like every other execution flag: read-only
  navigation with no side effects.
- Combination refusal (fail-closed, exit code 1, state untouched): carrying
  create/plan inputs (`--title`/`--slug`/`--assignee`/`--priority`/`--description`/
  `--parent`/`--from-plan`) or batch-startup flags (`--auto`/`--approved`) —
  adoption and create/batch-startup have different semantics and need two steps.

## Preconditions (`LIFECYCLE-ADOPT-001`)

| Fact | Requirement |
|---|---|
| Task status | `in_progress` or `review` (active and unfinished; planning/completed/stale are refused) |
| Task executor | recorded and non-empty (a task with no ownership has nothing to adopt) |
| Adopter identity | resolvable and ≠ the current executor; an explicit `--executor <label>` wins, otherwise the session identity is used |
| Identity source | process-fallback (the shared process label) refuses adoption — ownership must come from a real session identity or an explicit label |
| Execution context | delegated (worker/subagent) refuses adoption (`TASK-EXECUTION-001`, consistent with every other lifecycle mutation) |

On refusal, task.json is not written, the status is not changed, and the session
binding is not touched; the blockers state the concrete reason.

## What adoption writes (one UnitOfWork)

| Field | Written value |
|---|---|
| `executor` | the adopter's identity |
| `meta.previousExecutor` | the former executor (audit: the previous owner) |
| `meta.previousBaseline` | the former `meta.baselineCommit` (`null` when there was none) |
| `meta.adoptedAt` | UTC timestamp `YYYY-MM-DDTHH:MM:SSZ` |
| `meta.baselineCommit` | **reset** to the HEAD at adoption time; `null` when there is no git/no HEAD (degraded to status-only) |
| `status` | unchanged |
| `_state.revision` / `_state.operation_id` | the revision increments, and the operation_id carries the `adopt` tag (audit-traceable) |

Result code `LIFECYCLE-EXECUTOR-ADOPTED`; `transition.changed=false` (the fact slot
that does not advance status); `check_result` is `null` (no check is exempted).

## The baseline and the "never overwrite" invariant

- The start path's write-once logic is unchanged: **a repeated start never
  overwrites an existing `meta.baselineCommit`**, and the existing tests lock that
  invariant with zero edits.
- Adoption is the only audited explicit reset path: before resetting, the original
  value is recorded in `meta.previousBaseline`.
- The review window after the reset = uncommitted changes at adoption time plus
  commits after adoption. Changes **already committed** before adoption do not
  enter this task's window (they live in git history and must be traced through the
  commit log separately) — this is the known boundary of adoption.
- After adoption the baseline returns to write-once semantics: a later start does
  not slide it again.

## Session binding

On successful adoption the CLI binds the adopter's session to that task (the same
shape as a rebind by `task next <dir>` or the binding at task creation), so a
later `task next <dir> --run` can omit the directory and continue the
review/complete/archive chain.

## Difference from `--takeover`

| | `--takeover` | `--adopt` |
|---|---|---|
| Applies to | start_task (including an idempotent re-run) | a standalone action (this contract) |
| Status requirement | any (it only takes effect at the start activation point) | `in_progress` / `review` |
| Baseline | untouched | reset to HEAD (the old value is kept for audit) |
| Audit fields | none | `previousExecutor` / `previousBaseline` / `adoptedAt` |
| Result code | `LIFECYCLE-EXECUTOR-TAKEN-OVER` | `LIFECYCLE-EXECUTOR-ADOPTED` |

`--takeover` semantics stay as they were; `--adopt` is a superset action that does
not rewrite the takeover path (invariants and existing tests unchanged).
