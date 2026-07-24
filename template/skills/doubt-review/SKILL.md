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

You cannot spawn a fresh-context reviewer from within a subagent context. If doubt is required while inside a subagent, surface back to the main session so the review can run from a genuinely fresh context.

Do not dispatch `cowork-check` for standalone doubt review. `cowork-check` is a runtime-context-bound fixed agent and requires `cowork_runtime_context_id` plus `cowork_host_context_key`; without those fields it must report `needs_context`. When no bound workflow check context exists, use a regular reviewer or generic worker for the advisory skeptical pass.

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

## Common Rationalizations

| Excuse | Why It Fails | Better Approach |
|---|---|---|
| "I'm confident, skip doubt" | Confidence is where blind spots hide. | Write a 2-line CLAIM and pass the artifact to fresh-context review. |
| "Spawning a reviewer is expensive" | Debugging a bad decision after implementation costs more. | Run one bounded doubt cycle now. |
| "Review will catch it later" | Final review catches completed artifacts; doubt catches direction errors while they are cheap. | Run doubt before committing to the direction. |
| "Doubting every step causes delay" | Doubt only applies to non-trivial decisions. | Use the Apply When / Skip When sections to decide. |
| "Reviewer disagrees, so I am wrong" | Reviewer output is information, not authority. | Classify each finding through RECONCILE. |

## Relationship to Current Workflow

- `decision-review`: internal mandatory L2 gate; write accepted evidence to `decision-review.jsonl`.
- `review-protocol`: final implementation review; it does not replace in-flight doubt.
- `cowork-flow`: public router; it decides whether to load this Skill or the internal protocol.
- `TDD`: a failing test is doubt made concrete when the risk is executable behavior.
- `break-loop`: use when doubt exposes a real failure mode but the fix path keeps looping.

## Red Flags

- Skipping doubt because you feel confident.
- Passing CLAIM to the reviewer.
- Treating reviewer output as authoritative instead of reconciling it.
- Looping past three cycles.
- Calling the review adversarial while asking whether the artifact "looks good".
- Running another cycle against an unchanged artifact.
- Getting substantive findings twice but classifying none as actionable.
- Treating this Skill as a replacement for `decision-review.jsonl` or final review.

## Verification

- Every non-trivial decision has a CLAIM record.
- Every non-trivial artifact receives at least one fresh-context review.
- Reviewer receives ARTIFACT + CONTRACT (not CLAIM).
- Findings are classified instead of rubber-stamped.
- Stop conditions are satisfied before proceeding.
