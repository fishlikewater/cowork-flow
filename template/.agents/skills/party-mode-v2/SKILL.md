---
name: party-mode-v2
description: Use when the user requests a runtime-controlled multi-agent board discussion where children communicate through Party Mode V2 board APIs and the moderator only monitors or corrects drift.
---

# Party Mode V2

Use this skill as a thin entrypoint for the Party Mode V2 runtime board. The Python runtime is the source of truth for discussion state, board visibility, validation, round limits, and final reports.

## Boundaries

- Party Mode V2 is advisory only.
- It cannot mutate task status, start/review/complete/archive tasks, add sessions, commit, push, or satisfy formal workflow gates.
- It cannot satisfy formal Implement or Check completion. Use `cowork-implement` and `cowork-check` for formal phases.
- Discussion children are leaf executors. They do not dispatch, wait for, list, or close other agents.
- The moderator does not forward, summarize, rewrite, or synthesize child opinions for other child agents.

## Runtime First

Always use the runtime controller:

```text
.cowork-flow/run party-v2 init
.cowork-flow/run party-v2 monitor
.cowork-flow/run party-v2 view
.cowork-flow/run party-v2 post
.cowork-flow/run party-v2 respond
.cowork-flow/run party-v2 advance
.cowork-flow/run party-v2 finalize
```

Do not bypass a runtime rejection by manually accepting child output. Runtime validation failures must be fixed by a corrected child submission or by ending the discussion.

## Board Rules

- Child agents communicate through the board API.
- Child-visible board output must be current-round only.
- Historical board state is runtime-private and may be used only for audit or final reports.
- Use at least three child agents unless the effective runtime config explicitly allows a different value.
- The runtime emits host-neutral next actions. The active Host Adapter or moderator executes them for Codex, Claude Code, or OpenCode.

## Child Response Rules

When a child sees a different position, it must choose exactly one:

```text
maintain
revise
concede
```

`concede` requires accepted evidence and why the prior position failed.
`revise` requires the accepted part, rejected part, and updated position.
`maintain` requires counter evidence or counter reasoning.

Unsupported agreement, vague revision, and evidence-free rebuttal are invalid.

## Moderator Role

The moderator may:

- run runtime commands,
- execute host-neutral next actions through the active host,
- record off-topic warnings through the runtime,
- close children only when the runtime asks for closeout,
- show runtime status or final reports to the user.

The moderator must not:

- forward one child opinion to another child,
- create a claim table for child prompts,
- vote-count as validation,
- decide which child is correct.
