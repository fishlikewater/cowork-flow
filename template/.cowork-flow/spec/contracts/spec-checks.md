# Spec Check Contract (spec-declared commands)

## What it does

User specs (the `backend/` and `frontend/` directories under `.cowork-flow/spec/`,
plus any project-owned directory) may declare check commands in frontmatter under
`checks:`. The mechanism only executes declarations and never parses spec prose —
so a rule change is a command change in the same file, and the two stay in sync by
construction.

## When to attach a declaration

A clause is worth a `checks:` declaration whenever a command exit code can decide
it (lint / tests / type check / schema validation). Two hard constraints:

- **A declared command that does not exist = `unchecked` = blocks `complete`**:
  confirm the command runs in the current repository before declaring it.
- **edit-only is not a gate**: `when: edit` is a best-effort edit-time hint only —
  Bash writes bypass PostToolUse, and hosts without an edit-time fast path
  (see Appendix A) receive none of this feedback; the closeout phase does not
  re-run it either. A check that must hard-block has to declare
  `when: lifecycle`, or the default `both`.

## Syntax

```markdown
---
checks:
  - cmd: npm run lint --silent
    files: "src/"          # optional: scope, a directory prefix or an extension ("*.ts"), comma-separated
    timeout: 60            # optional: seconds, default 30, hard cap 120
    when: both             # optional: edit | lifecycle | both (default both)
    cmd.win: npm run lint  # optional: Windows override command
---

# Spec prose (the mechanism never reads it)
```

- `files` accepts exactly two forms: a directory prefix (`src/`, ending in `/` or
  auto-completed to it) and an extension (`*.ts`). Full glob forms (`**`, `[]`)
  parse as an error, the declaration does not run, and doctor reports it — never a
  fallback to "match everything"; for multi-value declarations
  (`files: "src/", "lib/"`) each token is unquoted under the same quoting rule
  before it takes effect.
- Quoting rule: a value is unquoted only when the whole value is a single quoted
  pair; command values carrying several quoted pairs, such as
  `"python" -c "..."`, are kept verbatim and split by the executor under shell
  rules.
- `when: edit` runs at edit time (PostToolUse) on the changed files that hit
  `files`, with the timeout clamped to 2.5 seconds (spawn budget for interpreter
  startup and the cmd wrapper); slow commands should declare `when: lifecycle`.
- **The file must be UTF-8 without BOM**: frontmatter starting with a BOM is
  silently ignored by the parser (zero declarations, no parse error) — the
  declaration fails without a word. After declaring, run `spec-check` once to
  confirm it was parsed.

### From zero to the first check (copy-paste)

1. Create a spec file under `.cowork-flow/spec/` (a project-owned subdirectory, or
   directly at the root, e.g. `spec/team-gate.md`). `contracts/`, `runtime/`, and
   `schemas/` are machine directories and are not scanned; every other level and
   subdirectory is. Save the file as UTF-8 without BOM.
2. Copy the block below into it, replace `cmd` with a command that really runs in
   this repository, and narrow `files` to the layer that spec governs:

```markdown
---
checks:
  - cmd: npm run lint --silent
    files: "src/"
    when: both
---

# Team spec prose (the mechanism never reads it)
```

3. Run `./.cowork-flow/run spec-check`: you should see
   `1 passed, 0 violations, 0 unchecked` instead of `no checks declared`. Then
   break the rule once on purpose and confirm it really reports a `violation` — a
   declaration that always passes is decoration, not a check.

**The command prints violations only; the framework adds the
`spec-check[<spec>] violation:` prefix**: a `cmd` that prints that prefix itself
stacks on top of the framework's, producing
`spec-check[team-gate.md] violation: spec-check[team-gate.md] violation: ...`.
A command's only duties are an exit code (0 = pass, non-zero = violation) and
readable output; the prefix, the classification, the three-state verdict, and the
throttle all live on the framework side.

## Three states and the gate

| State | Meaning | complete gate |
| --- | --- | --- |
| `pass` | exit code 0 | passes |
| `violation` | non-zero exit code | **blocks** (status does not advance) |
| `unchecked` | command missing / interpreter missing / timeout | **blocks**; an explicit `--allow-unchecked` lets it through and records the exemption in task.json `meta.specCheckExempt` (item by item, see below) |

`unchecked` never masquerades as `pass` ("did not run" is not "passed"); malformed
frontmatter treats that spec as having no checks and lands in the doctor report
without breaking the flow. A parse failure is a signal separate from the three
states: declaration parse errors such as an illegal `files` form belong to
`parseErrors`, are not folded into `pass`/`unchecked`, and exit with code 2 like
`unchecked`. Text mode and `--json` must use the same exit code, and text mode
must print the parse-error lines (`spec-check: N parse error(s): <spec>: <error>`)
— printing only `0 passed, 0 violations, 0 unchecked` would make a malformed
declaration look like a clean pass.

Exit code contract: `0` everything passed; `1` a violation exists; `2` unchecked
entries, `parseErrors`, or an executor failure exist. `--allow-unchecked` waives
only the `unchecked` block, never a parse error.

**A whole-executor failure is a separate block**: when the spec-check module fails
to import or raises, the closeout gate degrades to `summary.executorError` set plus
`classification: executor-failure` plus exit code 2, and blocks `complete` with
`SPEC-CHECK-EXECUTOR-ERROR`. It does **not** accept `--allow-unchecked` — that flag
waives "a declared command could not run", not "the checker itself broke"; the
synthetic `unchecked: 1` in the degraded report is only a counting placeholder, is
not reported as its own entry, and the block message does not mention the flag.

**An exemption record must name what it waived**: `meta.specCheckExempt` =
`{"at", "flag": "--allow-unchecked", "by": <actor or null>, "unchecked": N,
"uncheckedItems": [{"spec", "cmd"}…], "truncated"?}`; `meta.evidenceExempt` =
`{"at", "flag": "--allow-missing-evidence", "by": <actor or null>,
"missing": [<AC id>…]}`. The item list is capped at 10 entries; beyond that
`truncated: true` is set. A single command is clipped at 80 characters and **never
splits the first token** (that token is the program name — which is precisely the
answer to "what went unverified"). `by` is the resolved session actor, or `null`
when none resolves — **not** a stand-in borrowed from `creator`/`assignee`. The
completion output and the archive output print **the same rows of the same record**
(the completion output reads the `task.json` just written), so "what was recorded"
and "what was printed" cannot tell two different stories; with no exemption, no
exemption rows are printed at all.

**Every run carries one classification fact**: `summary.classification` ∈
`parse-error` / `executor-failure` / `zero-declaration` / `violation` /
`unchecked` / `pass` / `empty`, queryable directly through `--json`. `empty` is a
legitimate state: declarations exist but none ran in this phase (for example
`when: edit` declarations under a lifecycle run). Reading a report older than that
field goes through `report_classification()`, which returns `legacy` — a missing
field is itself a fact, and is never reverse-engineered from the counts (that
would promote an old report into a guess).

**Zero declarations is a legitimate state, but it must be visible**: a repository
with no effective declarations exits with code `0`, and text mode prints the
standalone fact line `spec-check: no checks declared (<N> spec files scanned)`,
distinguishable from `spec-check: <n> passed, 0 violations, 0 unchecked`; `--json`
carries `specFiles` at the top level and `declarations` in the summary. Zero
declarations ≠ clean pass — it means the spec chain currently holds no
machine-checkable constraint, a fact that needs to be seen rather than a green
that can be claimed.

## Timing and output

- **Edit time** (PostToolUse): runs only for `when: edit`/`both` when the change
  hits `files`, printing a single
  `spec-check[<spec>] violation: <first violation line>`; a missing executor or a
  timeout stays silent and never blocks the edit stream. Host differences and
  throttle details are in Appendix A.
- **Closeout** (task complete): full run, results recorded in the
  `meta.specCheckSummary` telemetry; the block message lists only a summary of the
  failing entries. Exemptions must also be **visible**: while
  `--allow-unchecked` / `--allow-missing-evidence` apply, the completion output
  prints that record item by item (an `Exempted: …` header line plus
  `  - <spec>: <cmd>` / `  - <AC id>` detail rows, naming
  `meta.specCheckExempt` / `meta.evidenceExempt` and the actor), and the archive
  output prints the same rows again — an exemption written only into task.json is a
  clean pass to whoever is watching the command.
- **Manual query**: `./.cowork-flow/run spec-check [--file <path>] [--json]
  [--verbose]` (exit codes as above).

## Declarations belong to the consumer

- **The template ships no declarations**: the spec files the template carries
  contain no effective `checks:` declaration — the template cannot know a
  project's commands, and a missing command lands in `unchecked` and blocks
  `complete`. Declare them in project-owned spec files (e.g. `spec/team-xxx.md` or
  a project-owned subdirectory); sync never touches those, and the declarations are
  maintained by the consumer alongside the spec prose.
- **sync-protected prefix and the named exceptions**: `spec/` as a whole is a
  sync-protected prefix, so existing spec files are not overwritten by `sync`
  (spec updates in the template only take effect for a fresh `init`); the named
  exceptions are the entries listed in `spec/runtime/host-assets.json`
  `syncPolicy.safeFiles` — the two `spec/contracts/` files (`this file and
  workflow-state-templates.md`) plus `spec/runtime/scope-rules.json` — which do
  track sync so contract corrections and budget defaults can reach installed
  projects. A project that tunes `scope-rules.json` locally therefore loses those
  edits on the next `sync`.
- **Recognizing clauses and attaching declarations is the main-session AI's job**:
  declarations belong to the project. During review / spec maintenance, the main
  session AI identifies machine-checkable clauses and adds the `checks:`
  declaration (it does not rewrite the clause prose on its own — a conflict between
  a clause and the implementation goes through the review flow for the user to
  decide); only the main session writes specs, and a delegated subagent only
  reports candidates without exceeding its scope. The full duty is in the
  `task-review` and `spec-sync` Skills.
- **Four quality disciplines**: ① produce a `pass` on a clean tree; ② prove the
  check really can fail with one negative case (not an always-passing decoration);
  ③ narrow the coverage with `files`; ④ run `spec-check` once after declaring to
  confirm it was parsed (guards against silent BOM / `files`-form failures). The
  review report lists the `clause → command → negativeProof` triple: `clause` (the
  clause), `command` (the deciding command), `negativeProof` (what the command
  reports when that clause is broken) — the same key set `task-review`'s Review
  Report Format and `subagent check-review --finding` use. A clause no command can
  decide must state why (`command`/`negativeProof` are `null`) instead of leaving
  the row blank; a clause that is machine-checkable yet yields no command is itself
  a finding.

## Appendix A: host capability matrix

| Host | digest injection | edit-time fast path | closeout enforcement |
| --- | --- | --- | --- |
| zcode | yes (Specs line h2 digest) | yes (PostToolUse short path; **main session only**) | yes |
| claude-code | yes (Python single source) | yes (PostToolUse, exit 2 feedback) | yes |
| codex | yes | yes (PostToolUse, `apply_patch\|Write\|Edit` → exit 2 stderr) | yes |
| opencode | yes | yes (plugin `tool.execute.after` appends one line to the tool result) | yes |
| dsh | yes (preset injection) | yes (preset plugin `tools/post-execute` → `additionalContexts`) | yes |
| kimi-code | yes (UserPromptSubmit hook → `inject.py --host kimi-code`) | no (no PostToolUse registered; observational-event stdout is discarded) | yes |
| qoder | yes (plugin hook → `inject.py --host qoder`) | yes (`PostToolUse` non-blocking event, warning via `additionalContext`, exit 0) | yes |

zcode / codex / claude-code share `run_edit_checks` through the Python single
source; opencode pulls the same executor from inside its plugin via the CLI
(`run spec-check --phase edit --throttled`), dsh calls the same Python protocol
through its preset plugin's `tools/post-execute`, and qoder calls the same executor
through its plugin hook's `PostToolUse` (that event is not blockable on Qoder, so
the warning comes back as `additionalContext` with exit 0 rather than
claude-code/codex's stderr + exit 2) — the six hosts with an edit-time fast path
share one throttle state and one three-state semantics instead of implementing
check logic each; kimi-code only gets closeout enforcement and the subagent
self-check.

Edit-time throttle: the same file is reported at most once per 10 seconds; the
throttle state lives in `.cowork-flow/.runtime/spec-edit-throttle.json`, and the
window is written only after the check ran to completion — a crashing executor
does not consume the window and a retry still executes. Delegated subagent sessions
receive spec-violation feedback too (subagents are the main code writers); scope
warnings stay main-only. The zcode main session's hook identity (the conversation's
own session id) is never bound — activation happens under an explicit identity on
the Bash side — so display and edit-time warnings fall back to the latest main
session; claude/codex keep a strict session identity (their Bash env carries the
same session id). zcode forwards through a shim to the single-source entrypoint
(`inject.py`), merging scope warnings and spec warnings into one additionalContext
payload; claude uses exit 2 stderr feedback.

## Appendix B: the delegated edit-time gap and its compensation

**Delegated subagent edit-time gap (measured on zcode, two rounds on 2026-09-09)**:
the ZCode plugin hook only dispatches on the main-session tool stream (all seven
event types attach to the main session; a subagent is a separate internal session
stream, `sess_subagent_agent_*`), so an Agent child's Edit/Write never receives the
`spec-check[...] violation` line — runtime binding and check logic are both fine;
what is missing is the host dispatch. The compensating mechanisms (frozen in the
subagent-dispatch.md contract):

1. Self-check before a subagent finishes: run `./.cowork-flow/run spec-check` in
   full and fix everything (the pull path; verified to work);
2. A second check before the parent session accepts: violations count as acceptance
   blockers (feedback moves from closeout up to return);
3. Implementation tasks' Verify commands include the spec-check self-check by
   default;
4. The closeout hard gate still backstops everything unchanged (a violation blocks
   `complete`).

Governance direction: ask the host to extend hook dispatch to the subagent tool
stream; once delivered, item 1 degrades automatically into a redundant safety net.

## Appendix C: digest injection

After entering `in_progress`, the stage-contract Specs line upgrades to
`Specs: <spec>(<h2 heading tree>); …`: at most 6 h2 entries, each truncated to 24
characters with `();` characters stripped; a missing file adds no annotation. The
digest is an entry-name index, not the prose, and is hard-capped by
scope-rules.json `stageContract.budget`; over budget, the whole line yields
(Scope/Gates lines are never dropped). The python/zcode output comes from a single
Python entrypoint, locked by the `test/stage-contract.test.js` matrix; opencode
transports that same entrypoint's output, so byte-exact equality holds by
construction.

## Appendix D: open decision

**Closeout aggregation budget**: a closeout runs everything with no aggregation
budget — repositories with many slow declarations get linearly slower at
`complete`. Whether to give closeout parallelism or a budget ceiling is left to a
later product decision; today it stays simple and serial.
