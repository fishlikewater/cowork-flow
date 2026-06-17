# Task lifecycle

Tasks follow a five-stage lifecycle managed by lifecycle commands.
This document defines the status machine, commands, and fixed agent rules.
See `.cowork-flow/workflow.md` for the full workflow narrative.

## Stage machine

| Stage | Command | `task.json.status` |
| --- | --- | --- |
| Planning | `task create` | `planning` |
| In progress | `task start <task-dir>` | `in_progress` |
| Review | `task review [task-dir]` | `review` |
| Completed | `task complete [task-dir]` | `completed` |
| Archived | `task archive <task-name>` | Copy keeps `completed` |

`task finish` only clears the current-session task pointer; it does not
change `task.json.status`.

## Task levels

### L0: No external behaviour change

Applies to documentation, formatting, small refactorings, comments, script
clean-up, test additions, and anything that does not change user-observable
behaviour.

Flow: `brainstorming` → `read spec` → `implement` → `check` → `complete`

### L1: Local behaviour change

Applies to single-module features, local interface changes, local data
processing logic with clear boundaries.

Flow: `changes` → `brainstorming` → `read spec` → `plan` → `tasks` →
`implement` → `check` → `complete` → `archive` → `add session`

### L2: Cross-layer or significant behaviour change

Applies to API / DB / message / permission / file format / architecture
boundary / release migration / security policy changes.

Flow: `changes` → `brainstorming` → `read spec` → `plan` → `tasks` →
`implement` → `cross layer check` → `complete` → `archive` → `add session`

L2 tasks must pass the readiness gate before `task start`; the same blocker
list is shown by `task next`. Do not start implementation or dispatch fixed
agents when proposal/spec/design, plan, task links, key assumptions, scope
boundary, acceptance criteria, or verification commands are missing.

## Fixed agents

Fixed agents only execute leaf tasks dispatched by the main session. Children
are executors; subtasks are work units.

| Agent | Reads | Allowed | Forbidden | Output |
| --- | --- | --- | --- | --- |
| `cowork-research` | Task context and research inputs | Research only, writes to `<task>/research/` | Modify code, spec, task status, Git | Research conclusions and evidence |
| `cowork-implement` | `<task>/prd.md`, `<task>/info.md`, `<task>/implement.jsonl` and files pointed to by JSONL | Implement within task scope | Launch other agents, commit, archive, run `task start`/`task finish`/`task archive` | Modified files and verification commands |
| `cowork-check` | `<task>/prd.md`, `<task>/check.jsonl` and `git diff` | Check behaviour, tests, spec sync, and omissions; fix in-scope issues directly | Commit, archive, launch other agents | Check conclusions, fixes, and verification results |

### Fixed agent dispatch entry

Formal `cowork-*` agents use the host adapter contract; the main session owns
dispatch, wait, acceptance, and cancellation. Host-specific primitives are
declared only in `.cowork-flow/adapters/<host>/adapter.yaml`; the workflow only
concerns stage responsibilities, coordination boundaries, and acceptance
accountability.

The formal dispatch protocol is defined in
`.cowork-flow/spec/core/dispatch.md`.

- The main session must dispatch fixed agents using fresh child contexts.
- The main session completes closeout through adapter wait primitives, list
  primitives, and cancellation/close primitives.
- Fixed `cowork-*` agents are leaf executors; they must not dispatch, wait for,
  list, or cancel other agents.
- Generic `worker`, `default`, or `explorer` are advisory only and cannot
  satisfy formal Implement or Check completion.

## Task state files

| State | File |
| --- | --- |
| Developer identity | `.cowork-flow/.developer` |
| Current session task | DB `runtime_session` |
| Task objective | `.cowork-flow/tasks/<task>/prd.md` |
| Implement context | `.cowork-flow/tasks/<task>/implement.jsonl` |
| Check context | `.cowork-flow/tasks/<task>/check.jsonl` |
| Debug context | `.cowork-flow/tasks/<task>/debug.jsonl` |
| Behaviour change | `.cowork-flow/changes/<slug>/` |
| Implementation plan | `.cowork-flow/plans/*.md` |
| Project spec | `.cowork-flow/spec/` |
| Project context summary | `.cowork-flow/project-context.md` |
| Session record | `.cowork-flow/workspace/<developer>/journal-*.md` |
| Runtime context | DB `runtime_context` |
| Dashboard process | DB `dashboard_process` |

> The current task is session-level state. Do not guess the current task
> without `COWORK_FLOW_CONTEXT_ID`, `CODEX_SESSION_ID`, `CODEX_THREAD_ID`,
> `OPENCODE_SESSION_ID`, or `CLAUDE_SESSION_ID`.
