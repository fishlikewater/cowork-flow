# Decision Review Protocol

> Internal protocol enforced by workflow readiness; it is not a public Skill.

## Enforcement

- L2 tasks: mandatory before task start.
- L0/L1 tasks: advisory and never blocked by missing decision review evidence.
- The runtime authority is `decision-review.jsonl`; prose notes do not satisfy the gate.

## Evidence

Write one UTF-8 JSON object per line to `<task>/decision-review.jsonl`:

```json
{"acceptanceId":"AC-007A","claim":"The selected direction is safe.","contract":"The invariant that must hold.","reviewerContext":"fresh","findings":[],"resolution":"accepted"}
```

Required fields:

- `acceptanceId`: non-empty and starts with `AC-`
- `claim`: reviewed decision
- `contract`: constraints used by the reviewer
- `reviewerContext`: exactly `fresh`
- `findings`: JSON array
- `resolution`: exactly `accepted`

Missing, malformed, stale-context, or unaccepted records block L2 task start.
