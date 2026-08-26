---
name: decision-audit
description: Use for an L2 architecture or workflow decision that needs a structured, advisory doubt cycle before implementation.
---

# Decision Audit

Use this Skill to make a non-trivial decision reviewable without turning an
agent-authored note into a lifecycle gate. The runtime only checks observable
files, links, state transitions, and scope facts; this Skill supplies the human
judgment loop.

## Doubt Cycle

1. **CLAIM**: state the decision and why being wrong would be costly.
2. **EXTRACT**: isolate the smallest artifact and its contract.
3. **DOUBT**: ask a fresh context to find problems in ARTIFACT + CONTRACT, not CLAIM.
4. **RECONCILE**: classify findings as misunderstanding, actionable, accepted trade-off, or noise.
5. **STOP**: stop after trivial findings, three cycles, or when the user says enough.

The reviewer receives ARTIFACT + CONTRACT, not CLAIM. Record the review result in
the normal task review output or discussion; do not create a pseudo-evidence
file or claim that `fresh` or `accepted` text proves a lifecycle fact.
