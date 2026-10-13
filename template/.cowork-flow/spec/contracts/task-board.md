# Task Board Contract

**Shared board: `task next --list --json` and the MCP `task_list` are two
renderings of the same board facts — a second executor can see "who holds what,
is anything stuck, how far has the evidence come" without running `run state`.
Dependency edges turn the ordering between tasks into an adjudicable gate on
start.**

A single implementation (`services/task_board.py` + `services/task_graph.py`) is
reused by both surfaces, so field values must stay consistent from one source.

## Board fields (added to every task record)

| Field | Meaning | Boundary |
|---|---|---|
| `executor` | the currently owning executor (`task.json.executor`, `null` when unset) | written by start / `--takeover` / `--adopt` |
| `ownerSessionActive` | whether any session is bound to this task (`active_task_path` in `sessions/` points at it) | **a hint, not a verdict**: a session working with an explicit directory is never bound, so `false` only means "no binding points here" and never that the task is orphaned |
| `evidenceCoverage` | `{total, withEvidence, missing[]}`; `null` for a task with no declared AC | same source as `run state` / the injected coverage row (`ac_evidence`) |
| `blocked` | whether an unfinished dependency exists | see "dependency semantics" below |
| `blockedBy` | names of the tasks whose dependencies are unfinished | in declaration order; a missing target also counts as unfinished |

The pre-existing fields (`name`/`path`/`status`/`assignee`/`parent`/`children`/
`childrenDone`/`childrenTotal`/`depth`/`active`) keep their semantics.

## Dependency edges

**Declaration** (the only runtime entry point; fixed once at creation time):

```bash
./.cowork-flow/run task next --run --title "<title>" --slug <slug> \
  --depends-on <task-name> [--depends-on <task-name> ...]
```

- `--depends-on` takes the **full task directory name** (the `name` column of
  `task next --list`; no prefix/suffix guessing) and may be repeated.
- Declaration is fail-closed: any failed validation fails the creation and writes
  nothing:
  - `TASK-CREATE-DEPENDENCY-001` the target does not exist (not found in either
    `tasks/` or `tasks/archive/**`);
  - `TASK-CREATE-DEPENDENCY-002` self-dependency (its own directory name or slug);
  - `TASK-CREATE-DEPENDENCY-003` a cycle (following the existing `dependsOn` edges
    leads back to the new task).
- Written into `task.json` as `dependsOn` (a string array, normalized, deduplicated,
  order preserved); a missing field is equivalent to no dependency — existing tasks
  are unaffected.
- Cross-repository/cross-project dependencies are unsupported, and there is no
  runtime command to rewrite dependencies (a 1.9.x candidate); the repair path is
  editing `task.json` locally (a fact-layer file where a hand edit is legitimate —
  a cycle or dangling target introduced that way is treated as unfinished at the
  start gate).

**Gate** (it constrains exactly one transition point, entry into `in_progress`):

- Start is allowed only once every dependency is `completed`; an archived task
  keeps `completed`, so an archived dependency still counts as done.
- While unfinished, it fails closed: `LIFECYCLE-DEPENDENCY-001`, with the blocker
  text `task depends on unfinished work: <names>`; that same text appears both in
  the navigation payload of `task next <dir>` (blockers) and in the `--run` error.
- An already-started task is not affected retroactively (the check happens in the
  start preflight; an idempotent re-run does not go through it).
- `--adopt`, review, and complete are not constrained by dependencies —
  dependencies answer "can this begin", not "can this wrap up".
- Navigation shape: with a planning status and any blocker present (dependencies
  included), `task next <dir>` reports the action `edit_planning_artifacts`
  (consistent with the existing readiness-blocker semantics: do planning work while
  blocked), and the blocker text is the fact source.

## Handover receipt (adopt output)

After a successful `task next <dir> --run --adopt`, on top of the ownership rebind
and baseline reset (see `task-adopt.md`), a Handover section is printed: former
executor → new executor, former baseline → new baseline, the list and count of
remaining unchecked ACs, and the evidence coverage `n/m`. The adopter can pick up
without any further query.
