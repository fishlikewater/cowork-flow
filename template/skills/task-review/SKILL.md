---
name: task-review
description: Use before completing a cowork-flow task to review code, tests, user-defined specs, lifecycle blockers, and completion readiness.
---

# Task Review

Use this Skill during the check phase, before the `task next --run` completion action, or whenever a task needs a focused code review.

## Principles

- Review early enough that fixes are cheap; do not wait until archive/commit to discover blockers.
- Review the current diff and exact task context, not broad conversation memory.
- Separate machine-decidable lifecycle facts from human judgment: lifecycle blockers cover state/scope facts; review judgment explains spec, quality, and risk findings.
- User-defined spec markdown under `.cowork-flow/spec/backend/` and `.cowork-flow/spec/frontend/` is binding for the task: verify the current diff against every applicable requirement and fix every violation before completion. Never skip a spec file because nothing else enforces it, and never defer a violation to the user.
- Prefer fresh verification from the current checkout over stale prior output.
- Do not create task-local review artifact files. The review result and command output are the evidence.
- Use advisory helper output only as review input; it must not become a second lifecycle gate.
- Use anti-self-proof discipline: do not accept the agent's own summary, checklist, or intended test coverage as proof without exact diff, command output, or source evidence.
- Use anti-rationalization discipline: treat convenient explanations for missing tests, missing specs, or unchecked lifecycle blockers as findings until verified.
- Keep verification-before-completion explicit: completion requires current commands from this checkout, not stale logs or advisory helper confidence.

## Inputs

Read only what is needed for the current task:

1. `<task>/decision-anchor.md` and acceptance criteria.
2. The linked implementation plan, if present.
3. The check context index (`<task>/check.jsonl`) and each referenced file, if present. Treat it as context only; do not write review conclusions or readiness evidence to it.
4. Current `git diff` / `git status --short`.
5. Relevant `.cowork-flow/spec/backend/` and `.cowork-flow/spec/frontend/` files are mandatory review input, not optional references: the task context lists the spec files for the task's dev_type; read every listed file (start from `index.md`) plus any other file in those two directories that changed paths or task scope touch.
6. Advisory facts from `review-check <task-dir> --json`, when useful.
7. Lifecycle blocker output, if any, from `task next --json`, `task next <dir> --validate`, or `task next <dir> --run --intent review`.

## Task Review Checklist

- **Scope**: every changed file is planned or justified; no unrelated cleanup sneaks in.
- **Behavior**: acceptance criteria are satisfied through observable behavior, not implementation-shaped assertions.
- **Tests**: test intent is explicit; tests fail for meaningful regressions, reject shallow tests such as existence/mock/snapshot-only checks, and cover boundary/error paths when relevant.
- **Evidence coverage**: when the decision anchor declares acceptance criteria (`AC-xxx`), verify each one has an evidence record in `<task>/evidence.jsonl` — or a recorded `meta.evidenceExempt` exemption from an explicit `--allow-missing-evidence` completion. Schema and gate codes (`LIFECYCLE-AC-001..004`) are defined in `.cowork-flow/spec/contracts/evidence-completion.md`. A record must point at real proof (test, command output, or manual verification note); a record that restates the AC without evidence is a finding.
- **Receipt freshness**: a strict task's completion gate requires the latest receipt to match the current change fingerprint, which covers the changed paths' content, the anchor's goal and AC text, the bound plan, `dev_type`, the referenced spec bodies, and `implement.jsonl`. Appending a scope entry to `implement.jsonl` — or editing a referenced spec body — therefore invalidates the receipt, so the review is re-run on the final state. That is the intended cost, not a defect. Evidence appends, AC ticks, and `.cowork-flow/.runtime/**` stay fingerprint-neutral, so closeout never invalidates what it just checked.
- **User specs**: every applicable backend/frontend requirement is verified against the diff and marked `pass`, `finding`, or `not_applicable` with reason. Every `finding` is fixed during review; an unfixed spec violation blocks completion and is never accepted as-is or deferred to the user. For each requirement, also ask whether it is machine-checkable (可机检) and already declared with `checks:`; identifying checkable clauses and adding or refreshing declarations is a main-session duty (never rewrite the clause text — raise a conflict through the review instead), and a declared check must earn its place: the command passes on a clean tree, a negative case proves it can fail, `files` narrows the scope, and a `spec-check` run after declaring confirms the declaration parses. Delegated subagents do not edit specs; they report candidates up.
- **Specs**: project specs are updated when behavior/contracts changed, or the review states why no spec update is needed.
- **Code quality**: naming, layering, error handling, state boundaries, security-sensitive paths, and complexity are reviewed against applicable user specs.
- **Lifecycle blockers**: state/scope blockers are fixed before acceptance; review does not invent hard blockers for natural-language specs.
- **Delegated acceptance**: when the implementation came from a delegated subagent, run `./.cowork-flow/run spec-check` before accepting its report — delegated sessions receive no edit-phase hook feedback on some hosts (zcode), so the report can be silently non-compliant; every violation is fixed or blocks acceptance.
- **Advisory facts**: helper output is used to focus review, not to declare pass/fail or block completion.
- **Anti-self-proof**: every claimed pass maps to source, diff, test output, or lifecycle output.
- **Anti-rationalization**: every accepted gap has an explicit user decision or narrow technical reason.

## Review Report Format

A finding is a machine-readable fact, not prose: the completion path and `subagent check-review` both consume it. Every finding carries three keys:

- `clause`: the requirement it judges — a user-spec clause, an acceptance criterion (`AC-xxx`), or a repo convention.
- `command`: the command that decides it, run from this checkout.
- `negativeProof`: what that command reports when the clause is broken — the evidence that the check can actually fail instead of always passing.

`command` and `negativeProof` may be `null` only for a judgment no command can decide (naming, layering, design intent); a machine-checkable clause left without a command is itself a finding. Use the same three keys when recording the finding in a review receipt:

```json
{"clause": "所有源文件 UTF-8 无 BOM", "command": "python scripts/check_bom.py", "negativeProof": "写入 BOM 后该命令退出码 1 并打印 offending file"}
```

`./.cowork-flow/run subagent check-review <subagent-id> --task-dir <dir> --result pass --changed-fingerprint <fp> --finding '<json>'` (repeatable).

The receipt is only as good as its provenance: completion re-reads the runtime
context it names, so the receipt must come from a `cowork-check` context that
was bound to *this* task. When this environment resolves no host context key,
the receipt records `bindingEvidence: "declared"` — say so in the report rather
than presenting the review as session-verified.

## Severity

- `critical`: correctness, security, data loss, lifecycle bypass, or completion would be invalid. Blocks completion.
- `important`: maintainability, missing meaningful tests, spec drift, or likely future bug. Fix before completion unless explicitly accepted.
- `minor`: clarity or polish that does not invalidate completion. May be noted without blocking.
- Violations of user-defined backend/frontend specs are not eligible for acceptance at any severity; they are fixed or block completion.

## Output

Return a concise review result with:

- `acceptanceId`: covered acceptance criteria or `overall`.
- `status`: `pass`, `needs_fix`, or `blocked`.
- `findings`: severity, file, line/scope, impact, fix, plus the `clause` / `command` / `negativeProof` triple defined in Review Report Format.
- `test_intent_review`: why tests prove the intended behavior or what is missing.
- `user_spec_review`: applicable spec files, per-requirement result, findings, and the "clause → command → negative proof" list for every `checks:` declaration added or refreshed in this review (`none` when nothing became machine-checkable).
- `lifecycle_check_review`: lifecycle commands run, blocker status, and resolution.
- `verification`: exact commands run from this checkout.
- `specUpdates`: files updated or reason no update was needed.
- `resolution`: what was fixed and what remains.

Do not claim completion from checklist intent or advisory helper output alone; completion requires current verification output.
