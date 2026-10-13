# Evidence Completion Contract

**Task completion moves from "the process ran" to "the evidence is complete": the
decision-anchor acceptance criteria (AC) are machine-queryable facts, and the
completion gate verifies that an evidence record exists for every AC.**

The machine only decides existence facts (AC declared, checkbox state, evidence
entry present or not); whether one piece of evidence really proves its AC is a
review judgement.

## Evidence records: `evidence.jsonl`

An append-only JSONL file in the task directory, written by the implementer (main
session or subagent) during implementation; the runtime only reads it:

```json
{"ac": "AC-001", "kind": "test", "ref": "tests/test_ac_evidence.py", "note": "covers the three-state assertion", "recordedAt": "2026-10-06", "by": "cwf-cli-1004"}
```

| Field | Required | Meaning |
|---|---|---|
| `ac` | yes | the corresponding AC id (`AC-xxx`, matching the decision-anchor) |
| `kind` | yes | `test` (automated test), `command` (command plus exit code), `manual` (hand-recorded verification) |
| `ref` | yes | where the evidence points: test file/case, command, or the location of the manual record; a non-empty string |
| `note` | no | the core assertion in one sentence |
| `recordedAt` | no | ISO date |
| `by` | no | writer session/actor identifier |

Malformed rows, missing fields, and unknown `kind` values are skipped by the
reader (matching the context JSONL tolerance); the gate only looks at valid
records.

## Completion gate

The completion action of `task next <dir> --run` appends four stable codes to the
direct lifecycle checks:

| code | Triggering fact | Exemption |
|---|---|---|
| `LIFECYCLE-AC-001` | an unchecked AC row exists | none — do the work, or tick the completed rows |
| `LIFECYCLE-AC-002` | a declared AC has no valid evidence record | `--allow-missing-evidence` (recorded in task.json `meta.evidenceExempt`, with `at`, `flag`, `by`, and the `missing` detail list) |
| `LIFECYCLE-AC-003` | `gateProfile=strict` and decision-anchor yields no AC row | none — a strict task was already required to declare ACs at start, so reading none at completion has only three explanations: the anchor was rewritten, the task was created wrongly, or the anchor is undecodable (corrupted encoding) |
| `LIFECYCLE-AC-004` | `gateProfile=strict` and the ac_evidence module cannot be imported | none — same family as `SPEC-CHECK-EXECUTOR-ERROR`: a broken module is not "nothing to check"; the message carries the original exception, and you rerun once the runtime install is fixed |

- The first two codes can appear together; `--allow-missing-evidence` waives
  `LIFECYCLE-AC-002` only, never `003`/`004`.
- **Compatibility path**: a legacy task with no `gateProfile` (every pre-existing
  task) triggers none of these gates when the decision-anchor is missing, declares
  no AC row, or the ac_evidence module is unreadable — item by item identical to
  the behavior before this contract.
- **Strict path**: a `gateProfile=strict` task re-verifies AC existence and
  evidence-module availability at completion — the start-time AC declaration
  requirement does not lapse because completion cannot read it.
- The `meta.evidenceExempt` trace has the same shape as spec-check's
  `specCheckExempt`: retries do not accumulate, the latest completion result wins.
- **An exemption record must name which items were waived and who approved it**:
  `meta.evidenceExempt` = `{"at", "flag": "--allow-missing-evidence",
  "by": <actor or null>, "missing": [<AC id>…]}`. `by` is the resolved session
  actor, or `null` when none resolves — **not** a stand-in borrowed from
  `creator`/`assignee`. Both the completion output and the archive output print
  this record item by item (the completion output reads the `task.json` just
  written), so "what was recorded" and "what was printed" cannot tell two different
  stories; with no exemption, no exemption rows are printed at all. The structure
  matches the `meta.specCheckExempt` detail rules on the spec-check side; see
  `spec-checks.md`.

## Injection and fact view

- Decision-anchor injection block: a task that declares ACs appends one row
  `AC evidence: <with evidence>/<total>` after the `Acceptance:` row, plus
  ` missing=<comma-separated ids, at most 5>` when any are missing; the three lines
  (Python / zcode shim / opencode plugin) render byte-identically in the same
  format, locked by matrix tests.
- `run state <task> --json` / the MCP fact view: `evidenceCoverage: {total,
  withEvidence, missing[]}`; `null` when no AC is declared.

## Boundaries

- The runtime never writes evidence for you, and never "plays out" the command
  behind an AC to fabricate a record.
- It does not parse AC prose semantics; a missing checkbox on an `AC-xxx` row
  parses as incomplete.
- This contract does not change spec-check semantics; MCP write tools still refuse
  by default (`fact-layer-access.md`).
