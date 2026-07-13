---
name: doubt-review
description: Use when the user asks for adversarial review, doubt review, or a fresh skeptical pass on a non-trivial implementation decision, design direction, or correctness claim. Use when correctness matters more than speed, the code is unfamiliar, or hidden assumptions could break the work.
---

# Doubt Review

Use this Skill to stress-test a decision while course correction is still cheap. It is the public, user-callable companion to the internal `decision-review` protocol; it does not replace runtime gates or final implementation review.

## Apply When

- The user explicitly asks for doubt review, adversarial review, or a skeptical pass.
- A decision changes branching logic, module boundaries, shared state, ordering, idempotency, or other invariants the type system cannot verify.
- You are about to claim behavioral correctness for unfamiliar or high-stakes code.
- An L2 task needs `decision-review.jsonl` evidence before implementation starts.

## Skip When

- The change is mechanical: formatting, file moves, or obvious one-line edits.
- You are only reading or summarizing existing code.
- The user explicitly prioritizes speed over verification.

## The 5-Step Doubt Cycle

### 1. CLAIM

Write a clear 2-3 line decision:

```text
CLAIM: "<one-sentence decision>"
WHY THIS MATTERS: <why this being wrong would be costly>
```

If you cannot state the claim briefly, keep researching until the decision is concrete.

### 2. EXTRACT

Create the smallest reviewable artifact:

- Code: a focused diff, function, or test case, not a whole file.
- Design: 3-5 sentences plus the constraints that must hold.
- Remove author reasoning; the reviewer should see the input, not the conclusion.

### 3. DOUBT

Ask for problems, not confirmation:

```text
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

Pass only ARTIFACT + CONTRACT, not CLAIM. Including CLAIM biases the reviewer toward agreement.

### 4. RECONCILE

Classify every finding in this order:

1. Contract misunderstanding: fix the contract, then reclassify.
2. Valid and actionable: modify the artifact, then restart the doubt cycle.
3. Valid but accepted trade-off: record the trade-off explicitly.
4. Noise: record and exclude it.

### 5. STOP

Stop when one condition is met:

- The next round produces only trivial or already-considered findings.
- Three cycles complete; report remaining substantive findings instead of starting a fourth cycle.
- The user says enough.

Substantive findings after three cycles mean the artifact is too large or immature. Return to EXTRACT and split it.

## Evidence

For L2 readiness, record accepted decisions in `<task>/decision-review.jsonl` using the internal `decision-review` protocol. At minimum, evidence must include `acceptanceId`, `claim`, `contract`, `reviewerContext`, `findings`, and `resolution`.

## Red Flags

- Skipping doubt because you feel confident.
- Passing CLAIM to the reviewer.
- Treating reviewer output as authoritative instead of reconciling it.
- Looping past three cycles.
- Calling the review adversarial while asking whether the artifact "looks good".
