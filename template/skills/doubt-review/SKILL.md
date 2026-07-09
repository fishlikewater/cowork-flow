---
name: doubt-review
description: Use when making non-trivial implementation decisions, starting L2 tasks, or claiming behavioral correctness. Use when correctness matters more than speed, working in unfamiliar code, or stakes are high.
---

# Doubt Review

## Overview

Non-trivial decisions must pass doubt review before being allowed into implementation. This is not optional self-reflection — it is a sub-step of the before-dev gate for L2 tasks.

Unlike `/review` (a verdict on a completed artifact), doubt-review is an in-flight posture: non-trivial decisions are cross-examined while course-correction is still cheap.

## When to Apply

Trigger conditions (any one applies):
- L2 tasks (L1 optional but recommended)
- Introducing or modifying branching logic
- Crossing module boundaries
- Relying on properties the type system cannot verify (thread safety, idempotency, ordering invariants)
- When the user explicitly requests it

Does not apply to:
- Mechanical operations (renaming, formatting, file moves)
- Reading/summarizing existing code
- One-line changes where correctness is obvious
- When the user explicitly requests speed over verification

## The 5-Step Doubt Cycle

### Step 1: CLAIM — a clear 2-3 line statement

```
CLAIM: "<one-sentence decision>"
WHY THIS MATTERS: <why this decision being wrong would be fatal>
```

If you cannot write a CLAIM in 2-3 lines, you have a vague feeling, not a decision. The distance between feeling and decision is the research/thinking you need to do.

### Step 2: EXTRACT — minimal reviewable unit

- Code: diff or function (not an entire file)
- Decision: 3-5 sentences + constraints
- Strip reasoning — provide only the input, not the conclusion

### Step 3: DOUBT — fresh-context adversarial review

```
Find problems with this artifact. Assume the author is overconfident. Look for:
- Undeclared assumptions
- Unhandled edge cases
- Hidden coupling or shared state
- Violated contract scenarios
- Broken existing conventions
- Failure modes under unexpected input

Do not confirm. Do not summarize. Find problems, or explicitly state that no problems were found after review.

ARTIFACT: <paste artifact>
CONTRACT: <paste constraints>
```

**Critical**: pass only ARTIFACT + CONTRACT, not CLAIM. Including CLAIM biases the reviewer toward agreement.

Note: you cannot spawn a fresh-context reviewer from within a subagent context. If you encounter a situation requiring doubt while inside a subagent, surface back to the main session.

### Step 4: RECONCILE — classify each finding

By priority (first matching category wins):
1. CONTRACT misunderstanding → fix CONTRACT, then reclassify
2. Valid + actionable → modify artifact, restart doubt cycle
3. Valid but acceptable trade-off → record explicitly
4. Noise → record and exclude

### Step 5: STOP — bounded loop

Stop when any condition is met:
- Next round produces only trivial or already-considered findings
- 3 cycles complete (stop; report to the user and do not proceed to a 4th)
- User explicitly says "that's enough"

Substantive findings remaining after 3 cycles = artifact is immature. Return to Step 2 to decompose.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'm confident, skip doubt" | Confidence correlates poorly with correctness. Highest confidence is where blind spots hide. |
| "Spawning a reviewer is expensive" | Debugging a bad commit in production costs more. The doubt cycle is bounded. |
| "Review will catch it at the review stage" | Review is the final gate. Doubt catches issues in-flight while course-correction is still cheap. |
| "Doubting every step causes infinite delay" | Doubt only applies to non-trivial decisions. Re-read When NOT to Use. |
| "Reviewer disagrees means I'm wrong" | Reviewer lacks your context; disagreement is information, not a verdict. RECONCILE then decide. |

## Red Flags

- Skipping doubt steps because "I'm confident"
- Treating reviewer output as authoritative rather than informational
- Looping past 3 cycles without escalating to the user
- Reviewer prompt uses "is this good?" instead of "find problems"
- 2+ consecutive cycles with substantive findings but 0 classified as "actionable" — you are validating, not doubting
- Passing CLAIM to the reviewer (biases toward agreement)
- Doubt theater: spawning a reviewer against an unchanged artifact (getting the same finding = stalling)

## Relationship to Existing Systems

- before-dev: doubt-review is a sub-step of the before-dev gate for L2 tasks
- check: check verifies implementation correctness; doubt-review questions decision direction. Use both.
- party-mode: board discussion can produce CLAIMs, but cannot substitute for fresh-context doubt review
- TDD: the RED step of TDD is doubt made concrete — a failing test is a disproof attempt
- break-loop: when a reviewer finds a true failure mode, connect to the debugging skill to locate and fix

## Verification

- Every non-trivial decision has a CLAIM record
- Every non-trivial artifact undergoes at least one fresh-context review
- Reviewer receives ARTIFACT + CONTRACT (not CLAIM)
- Findings are classified (not rubber-stamped)
- Stop conditions are satisfied
