# Decision Anchor Contract

**Every task must have a `decision-anchor.md`: the single authoritative decision
source that prevents drift during execution.**

It merges and replaces the former `prd.md`, carrying both "what to do" and "why not
the alternatives", which compresses the number of task artifacts.

## Schema

These section names are machine-readable. The runtime parser accepts both the
Chinese and English heading sets, and new anchors use the language configured in
`.cowork-flow/config.yaml` (`zh-CN` is the default).

```markdown
# Decision Anchor

## Goal
<one sentence>

## Acceptance Criteria
- [ ] AC-001: <verifiable>
- [ ] AC-002: <verifiable>

## Rejected Options
- **Option B**: <summary> — rejected because: <why>

## Key Assumptions
- <assumption 1>

## Scope Boundary
- In scope: <list>
- Out of scope: <list>

## Verification Commands
- `<command>` → <expected>
- Spec check: clause-by-clause check against applicable `.cowork-flow/spec/<dev_type>/` rules → pass / not_applicable (with reason)
```

## Section requirements

Both heading columns below are accepted; the right column is the `en-US` output
and the left column the `zh-CN` output.

| Section | Required | Why |
|------|------|------|
| `## Goal` / `## 目标` | required | no goal, no acceptance baseline |
| `## Acceptance Criteria` / `## 验收标准` | required | `task_start` is blocked without acceptance criteria |
| `## Rejected Options` / `## 被拒方案` | optional | required for brainstorming tasks, so a rejected option is not reconsidered during execution |
| `## Key Assumptions` / `## 关键假设` | optional | filled in for complex tasks to surface implicit constraints; not read by the runtime parser |
| `## Scope Boundary` / `## 范围边界` | optional | prevents scope creep |
| `## Verification Commands` / `## 验证命令` | required for strict non-Tiny; optional for legacy/Tiny | filled in for complex tasks, as the basis for automated verification; a strict non-Tiny task also needs the configured-language section and a filled spec/gate check for the task's `dev_type` (deciding command, or clause-by-clause `pass` / `not_applicable` with reason) |

### Machine-readable line formats (for injection)

`## Verification Commands` and `## Scope Boundary` are parsed by stage-contract
injection and by the MCP fact view (`services/fact_view.parse_decision_anchor`).
Line-format conventions:

- `## Verification Commands`: one command per line (an optional `- ` prefix),
  truncated to 120 characters, at most 10 lines; the implementing agent runs them
  itself (self-declared, self-checked) and the reviewer verifies the execution
  evidence. A strict non-Tiny task must also carry a `Spec check:` line in the
  configured language's section, with the actual `pass` / `not_applicable` result
  and a reason. The template placeholder (`<pass / not_applicable + reason>`) does
  not satisfy the start gate. This line is a hard start gate for strict non-Tiny
  tasks, while its content remains self-declared and is reviewed by the check
  agent. The fact view recognizes the line and does not return it as a shell
  command.
- `## Scope Boundary`: only the first non-empty line is taken, truncated to 160
  characters.

## Scenarios

| Scenario | Source | What gets filled in |
|------|------|---------|
| Has brainstorming | extracted from the discussion outcome | every section |
| No brainstorming (requirements already clear) | extracted from the requirement description and the plan | the minimum: goal + acceptance criteria |

## Artifact compression

Before merging (6 files): `prd.md` + `implement.jsonl` + `check.jsonl` +
`debug.jsonl` + `task.json`

After merging (5 files): `decision-anchor.md` + `implement.jsonl` + `check.jsonl` +
`debug.jsonl` + `task.json`

**A net reduction of one file type. Related-file tracking is now owned entirely by
`implement.jsonl`.**

## Lifecycle check coupling

- The preflight for `task next <dir> --run` checks that `decision-anchor.md` is
  non-empty and requires the `## Goal` / `## 目标` and `## Acceptance Criteria` /
  `## 验收标准` sections to be present.
- **Gate profile `meta.gateProfile`**: a newly created task is written as
  `"strict"`; an unmarked task is treated as `"legacy"` — existing tasks are not
  retro-fitted with the stricter gate, and the profile is queryable through the
  fact view. On top of the section check, a strict task additionally requires: at
  least one parseable `- [ ] AC-xxx: ...` row in `## Acceptance Criteria` /
  `## 验收标准`, no duplicate AC ids, no non-AC list rows in that section, and a
  declared `dev_type` (otherwise `task specs` dev-type dispatch silently comes
  back shorter).
- A strict non-Tiny task also requires the configured-language
  `## Verification Commands` / `## 验证命令` section with a filled
  `Spec check:` / `规范核对：` line. A missing section, the other-language
  heading, or the template placeholder blocks start. Tiny tasks and legacy tasks
  are exempt. The bound plan's `## Final Verification` / `## 最终验证` section
  carries the same filled check; plan structure and language are covered by
  `plan-binding.md`.
- An acceptance row's checkbox state (`- [ ]` / `- [x]`) and the evidence records
  (the task directory's `evidence.jsonl`) are the fact source of the completion
  gate: completion is blocked when an unchecked AC exists (`LIFECYCLE-AC-001`), a
  declared AC has no evidence (`LIFECYCLE-AC-002`), a strict task cannot read any
  AC row (`LIFECYCLE-AC-003`), or the AC-evidence module is unavailable
  (`LIFECYCLE-AC-004`). Schema and exemptions are in `evidence-completion.md`.
- **Review receipt change fingerprint** (a strict task requires its latest receipt
  to match the current state at completion, `LIFECYCLE-REVIEW-003`). Input = the
  git-visible change set (paths + content digests) + this anchor's goal and AC text
  + the content digest of the bound plan + `dev_type` + the **content digest** of
  every referenced spec + the content digest of `implement.jsonl`. Both `spec/**`
  and `tasks/**` are gitignored, which is why the last two must enter the
  fingerprint explicitly — otherwise rewriting a referenced spec's prose, or
  widening the declared scope, would leave a stale receipt valid.
- Fingerprint **exclusions** (mechanism): the change set excludes the whole
  `.cowork-flow/tasks/**` tree, `.cowork-flow/.runtime/**`, and
  `.cowork-flow/logs/**` — task-directory artifacts (`task.json`,
  `evidence.jsonl`, `review.jsonl`, `check.jsonl`, `debug.jsonl`, and the anchor's
  **path entry**) and runtime metadata are not counted, or a receipt would
  invalidate itself the moment it was recorded. `implement.jsonl`'s path entry is
  excluded the same way; its **content** is counted instead through the `scope`
  component.
  A **consequence** (expected cost, not a defect): **any byte change in
  `implement.jsonl`** (appending or removing a scope entry, rewording a `reason`,
  a domain-guide entry) **or a rewrite of a
  referenced spec's prose invalidates an existing receipt**, requiring one more
  review run against the final state. Appending evidence, ticking ACs, and runtime
  metadata are not in that set.
- **Light profile `meta.taskType: "tiny"`**: applies to `strict` tasks only
  (`legacy` + `tiny` stays a compatibility path). A light task **is still strict**
  — what it waives are three things: the review receipt, AC evidence, and
  `dev_type`. It does **not** waive the file-scope gate or "AC rows
  are non-empty" (`LIFECYCLE-AC-003`/`004` still apply). Plan-file binding is not
  among the three, but the pre-existing field-level exemption for tiny applies, so
  a light task does not require `planFile` either. `tiny` **can only be declared at
  creation time** (`task next --run --task-type tiny`) with no later edit path; the
  light profile is visible in `task next --list` (a `[light]` text marker and
  `lightProfile` in `--json`) and in doctor's task-hygiene output. The single
  decision source is `task_gate_profiles.is_light_task` (`strict` + the field is
  `tiny`); the start-preflight plan-file exemption still uses the field-level
  `declares_light_profile` so existing pre-strict tiny tasks keep behaving as
  before. The light profile **must not** be used for a task touching runtime /
  gates / specs — that rule rests on visibility and review, not on a machine gate.
- Read by `cowork-implement`: see .cowork-flow/spec/contracts/subagent-dispatch.md
- Read by `cowork-check`: same as above
- `debug.jsonl` reference: optional; on deviation diagnosis it records the anchor
  delta

## Formal-release behavior

The formal release does not auto-migrate a legacy `prd.md`. When a task is
started, only `decision-anchor.md` is recognized as the authoritative decision
source; if a task directory has only `prd.md` and no `decision-anchor.md`,
`task next <dir> --run` must fail-closed and report
`decision-anchor.md is missing or empty`.

An existing legacy task needs a human to convert the `prd.md` content into
`decision-anchor.md`, fill in `## Goal` / `## 目标` and
`## Acceptance Criteria` / `## 验收标准`, and only then start.
