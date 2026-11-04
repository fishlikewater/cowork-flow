---
name: adversarial-review
description: Use when the user asks for adversarial review, doubt review, or a fresh skeptical pass on a non-trivial implementation decision.
---

# Adversarial Review

Use this Skill to stress-test a decision while course correction is still cheap.
It is advisory and independent from lifecycle start, completion, and archive
gates.

Prefer precise context over broad narrative: pass only the smallest artifact,
the contract it must satisfy, and the decision claim under review.

## Apply When

- The user explicitly asks for doubt review or an adversarial pass.
- A decision changes branching logic, module boundaries, shared state, ordering,
  idempotency, or another invariant that tests cannot fully express.
- You are about to claim behavioral correctness for unfamiliar or high-stakes code.

## Skip When

- The change is mechanical or only summarizes existing code.
- The user explicitly prioritizes speed over verification.

## Review Loop

1. **CLAIM**: write the decision and the observable behavior it promises.
2. **EXTRACT**: read the smallest focused diff, function, test, or design statement.
3. **DOUBT**: try to break the claim with a concrete input, call path, or state;
   ask for undeclared assumptions, edge cases, coupling, contract violations,
   convention breaks, and failure modes.
4. **RECONCILE**: fix actionable findings, accept explicit trade-offs, and
   discard noise.
5. **STOP**: stop after no surviving finding, three cycles, or user direction.

## Report Only Real Problems

A finding is real only when all three parts exist. If any part is missing,
discard the finding; do not downgrade it, hedge it, or rephrase it as a concern.

1. **Location**: file:line, a quoted line, or an identifiable symbol or statement.
2. **Trigger**: a concrete input, call path, state, or sequence that reaches the problem.
3. **Consequence**: the observable wrong behavior, broken contract, or decision
   that can no longer be trusted.

Report nothing when nothing qualifies. "no real problems found" is a complete
result. Do not pad the report to look thorough, and do not invent findings to
prove the review ran.

Do not report:

- style, naming, or formatting preferences with no failure consequence;
- restatements of what the artifact already says or does;
- hypothetical risk with no reachable trigger ("could break if...");
- a problem the supplied contract already covers, or a trade-off the author
  explicitly accepted;
- the same finding twice under a different label.

If a possible problem has no concrete trigger, it is an open question, not a
finding. Ask it only when the answer would change the conclusion.

## Severity

Use severity to keep doubt actionable instead of theatrical.

Severity labels follow the report language: Chinese `致命` / `重要` / `次要`;
English `critical` / `important` / `minor`.

- 致命 / `critical`: invalidates correctness, safety, lifecycle boundaries, data integrity, or completion readiness.
- 重要 / `important`: likely bug, missing meaningful verification, spec drift, or maintainability risk that should be fixed before completion.
- 次要 / `minor`: clarity, naming, or polish that should be noted but does not block progress.

Every level still needs the three-part evidence. Cosmetic observations that fail
it stay out of the report.

## Output

Keep the report short and use the language of the surrounding conversation for
the body, headings, severity labels, and field labels.
Do not mix languages inside one heading.

- Chinese response: `## 结论`, `## 发现`, `## 待确认`; severity `致命` / `重要` / `次要`.
- English response: `## Verdict`, `## Findings`, `## Open questions`; severity `critical` / `important` / `minor`.

Each section:

- **结论 / Verdict**: one or two sentences with the outcome and the number of
  real findings.
- **发现 / Findings**: one short block per finding, ordered by severity. Start
  each block with a numbered one-line problem statement, then give location,
  trigger, consequence, and fix one per line.
- **待确认 / Open questions**: only questions whose answer changes the verdict.

Finding block shape (Chinese example; in an English report use `Location` /
`Trigger` / `Consequence` / `Fix`):

```markdown
### 1. `parse([])` 抛 IndexError（重要）
- 位置：`parser.py:42`
- 触发：`parse([])`
- 后果：调用方无法区分空输入与错误
- 修复：入口处返回空结果
```

Omit any section that would be empty. Do not restate the artifact, walk through
areas with no findings, or repeat the findings in a summary list.

## Verification Discipline

- Use verification-before-completion: do not accept behavioral correctness until current source or command output supports it.
- Use anti-rationalization: challenge convenient explanations for missing edge cases, tests, or scope checks.
- State what evidence would change the conclusion; do not turn advisory doubt into a hidden gate.

Pass only ARTIFACT + CONTRACT to the reviewer so the claim does not bias the
review. Keep the result in the task discussion or review output. No task-local
evidence file or self-declared acceptance record is required for readiness.
