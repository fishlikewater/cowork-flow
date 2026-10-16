# Plan Binding Contract

Plan binding brings a development plan into the implementation path without turning
the plan into a second workflow kernel.

## Authority boundaries

- `decision-anchor.md` keeps carrying the goal, acceptance criteria, and scope
  judgement.
- `implement.jsonl` keeps carrying the hard file scope for review/complete.
- `.cowork-flow/plans/*.md` carries the implementation order, file boundaries,
  verification commands, and anti-drift notes.
- `task.json.meta.planFile` records only the repo-relative plan path.

## Creation phase

- A plain task creation (`task next --title … --slug …`) may create a planning
  task with no plan.
- `task next --from-plan <path>` is an explicit binding request; `<path>` must
  exist, lie inside the repository, and lie under `.cowork-flow/plans/`.
- On a successful binding the runtime writes:

```json
{
  "meta": {
    "planFile": ".cowork-flow/plans/YYYY-MM-DD-slug.md"
  }
}
```

## Binding during planning

- A planning task not bound at creation time can bind a plan later with
  `./.cowork-flow/run task next <task-dir> --run --from-plan <path>`.
- Validation matches the creation phase: the path exists, lies inside the
  repository, is under `.cowork-flow/plans/`, and is non-empty.
- The binding writes only `task.json.meta.planFile` (keeping the other meta keys)
  and does not change task status; re-run `task next <task-dir> --run` afterwards
  to continue.
- A non-planning task carrying `--from-plan` is refused (the runner errors when the
  next action is not `edit_planning_artifacts`).

## Before starting implementation

A Normal / High-risk task must satisfy the following before moving from `planning`
into `in_progress`:

- `task.json.meta.planFile` exists.
- `planFile` is a repo-relative `.cowork-flow/plans/` path.
- The plan file exists and is non-empty.
- `decision-anchor.md` contains `## 目标` and `## 验收标准`.
- `implement.jsonl` passes the existing context validation.

A Tiny task may have no planFile, but must still satisfy the existing anchor and
implement-scope requirements.

## Implementation recovery

When the active task has a bound `meta.planFile`, the recovery checklist must point
at reading the current plan first, then `decision-anchor.md` and the JSONL context.
The recovery output lists paths only and never expands the plan prose.

## Archive phase

- When archiving a task, the runtime byte-copies the plan file pointed at by
  `meta.planFile` into the archive task directory as a `plan.md` snapshot, making
  the archive record self-contained.
- The snapshot is a copy, not a move: the original under `.cowork-flow/plans/` and
  the `meta.planFile` pointer stay unchanged.
- When `meta.planFile` is missing, empty, or points at a nonexistent file, the
  snapshot is skipped and archiving completes normally.
- A failed snapshot write rolls back under the existing archive transaction
  (TASK-ARCHIVE-PLAN-001); the rollback deletes the snapshot already written.

## v1 non-goals

- No parsing of plan step status.
- No Markdown AST or DSL.
- No comparing AC text against plan task prose.
- No matching verification commands against evidence records.
- No plan-approval data model.

These capabilities are considered only after warning noise and real payoff have been
validated.
