---
name: adversarial-review
description: Use when the user asks for adversarial review, doubt review, or a fresh skeptical pass on a non-trivial implementation decision.
---

# Adversarial Review

Use this Skill to stress-test a decision while course correction is still cheap.
It is advisory and independent from lifecycle start, completion, and archive
gates.

## Apply When

- The user explicitly asks for doubt review or an adversarial pass.
- A decision changes branching logic, module boundaries, shared state, ordering,
  idempotency, or another invariant that tests cannot fully express.
- You are about to claim behavioral correctness for unfamiliar or high-stakes code.

## Skip When

- The change is mechanical or only summarizes existing code.
- The user explicitly prioritizes speed over verification.

## Review Loop

1. **CLAIM**: write the decision and why it matters.
2. **EXTRACT**: provide the smallest focused diff, function, test, or design statement.
3. **DOUBT**: ask for undeclared assumptions, edge cases, coupling, contract violations,
   convention breaks, and failure modes.
4. **RECONCILE**: fix actionable findings, accept explicit trade-offs, and discard noise.
5. **STOP**: stop after trivial findings, three cycles, or user direction.

Pass only ARTIFACT + CONTRACT to the reviewer so the claim does not bias the
review. Keep the result in the task discussion or review output. No task-local
evidence file or self-declared acceptance record is required for readiness.
