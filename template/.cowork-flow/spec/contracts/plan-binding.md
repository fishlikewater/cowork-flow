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

- A newly created strict non-Tiny task also records
  `meta.planReadyRequired: true`. Existing tasks without that marker are not
  retroactively required to have a snapshot; if they are finalized, the
  snapshot is recorded and validated, but a missing snapshot is not a new
  blocker for them.

## Skeleton generation

- `./.cowork-flow/run plan new --title <title> --slug <slug>` reads the
  installed localized `.cowork-flow/templates/plan-template.md` and writes a
  plan skeleton to `.cowork-flow/plans/YYYY-MM-DD-<slug>.md`.
- The title placeholder (`<功能>` / `<Feature>`) is replaced; the rest of the
  template shape is preserved. The file is written as UTF-8 with LF endings.
- An existing plan is never overwritten unless `--force` is explicit.
- Generation is optional; a planning agent may still fill the installed
  template directly. `plan finalize` remains the completeness gate.

## Plan finalize

- `./.cowork-flow/run plan finalize [task-dir]` is allowed only on a planning
  task. It does not edit the plan or anchor.
- It requires the bound plan, the configured-language template shape, a
  machine-readable concrete goal line, at least one concrete `AC-NNN` row,
  content in `## 目标` / `## 全局约束` / `## 文件边界` beyond the installed
  template body, complete task briefs (full fields for Normal/High-risk; file
  boundaries, verification command, and completion conditions for Tiny), a
  concrete command inside the task's fenced verification block, a non-empty
  `implement.jsonl`, anchor acceptance rows matching the plan IDs/text, an
  anchor goal matching the plan goal, and the filled anchor spec-check result.
  Template bodies are read from the installed localized template at finalize
  time, so placeholder matching follows template changes instead of a copied
  sentinel list.
- On success it writes `task.json.meta.planReady`:

```json
{
  "meta": {
    "planReady": {
      "planDigest": "<sha256>",
      "anchorDigest": "<sha256>",
      "readyAt": "2026-10-23T00:00:00Z",
      "devType": "backend"
    }
  }
}
```

- A failed finalize writes nothing. A successful finalize is the handoff point
  for human review: the reviewer sees the complete plan and anchor.
- A new strict non-Tiny task requires the snapshot at start. Start rejects a
  missing snapshot and rejects any snapshot whose digests no longer match the
  current plan or anchor; editing either file after review requires another
  finalize and another review. Unmarked old tasks remain exempt.

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
- `decision-anchor.md` contains `## Goal`/`## 目标` and
  `## Acceptance Criteria`/`## 验收标准`.
- `implement.jsonl` passes the existing context validation.
- For a strict non-Tiny task, the plan title contains the configured-language
  marker (`实施计划` / `Implementation Plan`).
- The plan contains the six configured-language `##` template headings in
  template order: `目标` / `验收标准` / `全局约束` / `文件边界` / `任务` /
  `最终验证`, or their `en-US` equivalents. Extra custom sections are allowed;
  fenced code is ignored; a known template heading from the other language is
  rejected.
- Any `### 任务` / `### Task` task heading uses the configured-language prefix.
- `## 最终验证` / `## Final Verification` contains a line starting with
  `规范核对：` / `Spec check:` and carrying an actual `pass` or
  `not_applicable` result. The template placeholder (`<pass / not_applicable +
  理由>` / `<pass / not_applicable + reason>`) does not satisfy the gate.
- The strict non-Tiny anchor carries the configured-language `## 验证命令` /
  `## Verification Commands` section with the same filled spec-check result;
  see `decision-anchor.md`.
- The plan passes `plan finalize`; the anchor acceptance IDs/text match the
  plan, and the stored plan-ready digests still match both files.

Creation and `--from-plan` binding stay permissive: a planning task may create
and bind a plan before its structure is final. The completeness checks run at
`plan finalize`; the start gate repeats the structural backstop and verifies the
reviewed snapshot.

A Tiny task may have no planFile and is exempt from the plan-shape and anchor
spec-check gates. A legacy task (no `meta.gateProfile: "strict"`) keeps the
historical checks; this contract does not retro-fit either profile.

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
- No semantic validation of plan prose beyond the completeness checks above.
- No matching verification commands against evidence records.
- No semantic validation of the spec-check result or reason; the structural
  check only requires an actual `pass` / `not_applicable` token.
- No approval record beyond the plan-ready digest snapshot; human approval is
  still a process step, not a separate workflow state.

These capabilities are considered only after warning noise and real payoff have been
validated.
