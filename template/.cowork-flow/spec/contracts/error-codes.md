# Runtime Error Codes

Every `LIFECYCLE-*` error code the runtime can put in a result's `code` field, with
the condition that produces it. A code is a stable contract: consumers match on the
code, never on the message text.

Codes are defined in `scripts/services/*.py` and surface in CLI output, `--json`
results, and the closeout blockers.

## Codes

| Code | Raised when | Defined at |
|---|---|---|
| `LIFECYCLE-AC-001` | At completion the decision-anchor still has at least one unchecked acceptance row — the work is unfinished, not unproven. | `services/lifecycle_checks.py:269` |
| `LIFECYCLE-AC-002` | At completion a declared acceptance criterion has no valid record in `evidence.jsonl` and `--allow-missing-evidence` was not passed. | `services/lifecycle_checks.py:288` |
| `LIFECYCLE-AC-003` | A `strict` task reaches completion with no readable acceptance row, which is impossible unless the anchor was rewritten, the task was created wrong, or the anchor is undecodable. | `services/lifecycle_checks.py:246` |
| `LIFECYCLE-AC-004` | A `strict` task reaches completion while `services.ac_evidence` cannot be imported, so the acceptance gate cannot run at all. | `services/lifecycle_checks.py:232` |
| `LIFECYCLE-ADOPT-001` | An `--adopt` request fails the fail-closed adoption preconditions: status is not `in_progress`/`review`, the task records no executor, no adopter identity resolves, the identity is a process-fallback (shared) label, or the adopter already is the current executor. | `services/task_lifecycle.py:820` (also `:838`, `:859`, `:871`, `:882`) |
| `LIFECYCLE-CHECK-001` | The lifecycle check for the stage being entered reports blockers, so review or complete cannot proceed. | `services/task_lifecycle.py:684` |
| `LIFECYCLE-CONTEXT-001` | A session-activating stage (start/activate) cannot build the active-task session state, so the activation has no session to bind. | `services/task_lifecycle.py:716` |
| `LIFECYCLE-DEPENDENCY-001` | The start preflight finds a `dependsOn` target that is not `completed`; the blocker text is `task depends on unfinished work: <names>`. | `services/lifecycle_policy.py:93` |
| `LIFECYCLE-EXECUTOR-001` | The start activation point finds the task already owned by a different executor and no `--takeover` was passed, including the foreign-session idempotent re-run. | `services/task_lifecycle.py:577` (also `:1028`) |
| `LIFECYCLE-RECOVERY-001` | An interrupted transaction from an earlier run cannot be replayed by `UnitOfWork.recover_all`, so the task is never loaded. | `services/task_lifecycle.py:538` |
| `LIFECYCLE-REVIEW-001` | A `strict`, non-light task reaches completion with no independent review receipt at all. | `services/lifecycle_checks.py:658` |
| `LIFECYCLE-REVIEW-002` | The latest review receipt does not have `result: "pass"`, so the newest review stands as a failure. | `services/lifecycle_checks.py:670` |
| `LIFECYCLE-REVIEW-003` | The latest receipt's `changedFingerprint` differs from the fingerprint recomputed now — the change set, plan, goal, acceptance text, or applicable specs moved after the review. | `services/lifecycle_checks.py:681` |
| `LIFECYCLE-REVIEW-004` | The latest receipt is not backed by a runtime binding: its `contextId` does not resolve to a `cowork-check` subagent context bound to this task, or its binding evidence contradicts the submitting session. | `services/lifecycle_checks.py:693` |
| `LIFECYCLE-TASK-001` | The task directory passed to a lifecycle command does not exist. | `services/task_lifecycle.py:529` |
| `LIFECYCLE-TRANSITION-001` | The task's current status cannot transition to the target status of the stage being run. | `services/task_lifecycle.py:641` |
| `LIFECYCLE-UOW-001` | The `UnitOfWork` write fails: task metadata cannot be re-read before commit/takeover, changed under it (optimistic-concurrency conflict), or `unit.commit()` raises. | `services/task_lifecycle.py:942` (also `:949`, `:998`, `:1051`, `:1059`, `:1095`) |

## Non-error `LIFECYCLE-*` codes

These carry the same prefix but are not error codes, so no condition above applies
to them:

- `LIFECYCLE-OK` — a stage completed successfully.
- `LIFECYCLE-IDEMPOTENT` / `LIFECYCLE-IDEMPOTENT-VALIDATED` — the requested stage
  was already satisfied, so the call is a validated no-op.
- `LIFECYCLE-EXECUTOR-TAKEN-OVER` / `LIFECYCLE-EXECUTOR-ADOPTED` — ownership was
  reassigned by `--takeover` / `--adopt`.

## Exemptions

`LIFECYCLE-AC-002` is the only code in this set a flag can waive
(`--allow-missing-evidence`); spec-check's `--allow-unchecked` waives `unchecked`
declarations, not a `LIFECYCLE-*` code. Details are in `evidence-completion.md` and
`spec-checks.md`.
