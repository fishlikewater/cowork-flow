# Decision Review Protocol

> Internal protocol enforced by workflow readiness; it is not a public Skill.

## Purpose

`decision-review` is the mandatory L2 evidence gate for non-trivial decisions.
It preserves the adversarial doubt cycle from `doubt-review` while keeping the
runtime authority in `decision-review.jsonl`.

## Enforcement

- L2 tasks: mandatory before task start.
- L0/L1 tasks: advisory and never blocked by missing decision review evidence.
- The runtime authority is `decision-review.jsonl`; prose notes do not satisfy the gate.

## Doubt Cycle

Every accepted L2 decision review must be derived from this bounded cycle:

1. CLAIM: state the decision and why being wrong would be costly.
2. EXTRACT: isolate the minimal reviewable artifact or design statement.
3. DOUBT: ask a fresh context to find problems in ARTIFACT + CONTRACT, not CLAIM.
4. RECONCILE: classify each finding as contract misunderstanding, actionable,
   accepted trade-off, or noise.
5. STOP: stop after trivial or already-considered findings, three cycles, or the
   user explicitly says enough.

The reviewer receives ARTIFACT + CONTRACT, not CLAIM. CLAIM is recorded for
traceability, but it must not bias the adversarial review prompt.

## Evidence

Write one UTF-8 JSON object per line to `<task>/decision-review.jsonl`:

```json
{"acceptanceId":"AC-007A","claim":"The selected direction is safe.","contract":"The invariant that must hold.","reviewerContext":"fresh","findings":[],"resolution":"accepted","artifact":"Focused diff or design statement reviewed via ARTIFACT + CONTRACT.","reconciliation":[],"cycleCount":1}
```

Required fields:

- `acceptanceId`: non-empty and starts with `AC-`
- `claim`: reviewed decision
- `contract`: constraints used by the reviewer
- `reviewerContext`: exactly `fresh`
- `findings`: JSON array
- `resolution`: exactly `accepted`

Recommended fields:

- `artifact`: minimal EXTRACT artifact reviewed.
- `reconciliation`: how each finding was classified.
- `cycleCount`: number of completed doubt cycles, never greater than 3.

Missing, malformed, stale-context, or unaccepted records block L2 task start.
